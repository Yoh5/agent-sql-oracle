"""Le banc d'attaques : qui arrête l'attaque — le modèle, le code de l'agent, ou la base ?

Pour chaque attaque, deux mesures :

1. **le tour de l'agent** (`Tour.issue`) — ce qui s'est réellement passé : le
   modèle a refusé, l'écriture est partie en validation, Oracle a refusé ou
   filtré, ou la donnée interdite est sortie (`reussi`) ;
2. **la sonde de la base seule** (`Tour.base`) — le SQL malveillant de
   l'attaque envoyé DIRECTEMENT au compte du profil, sans modèle ni agent :
   `refuse`, `filtre`, `fuite`, `accepte` (une écriture que la base a laissée
   passer) ou `erreur`. C'est elle qui dit si la base tient par elle-même —
   sans elle, une écriture arrêtée par le classement Python de l'agent
   passerait pour un blocage d'Oracle.

L'issue se lit sur ce que la base a rendu, jamais sur ce que le modèle dit.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from borne.agent import Executeur, Resultat, repondre_detail
from borne.attaques import CATALOGUE, Attaque, Verite, detecter_fuite
from borne.config import PROFILS, Barrieres, compte_pour
from borne.journal import Tour, ecrire, issue_depuis_erreur
from borne.modele import Modele, ModeleFactice


def modele_qui_cede(attaques: Sequence[Attaque]) -> ModeleFactice:
    """Le pire modèle possible : il écrit tel quel le SQL de chaque attaque."""
    return ModeleFactice({a.question: a.sql_cede for a in attaques})


def _sonder(attaque: Attaque, compte: str, executeur: Executeur, verite: Verite,
            avant: str) -> str:
    r = executeur.executer(compte, attaque.sql_cede)
    if detecter_fuite(attaque, r.lignes, r.colonnes, r.message, verite, avant):
        return "accepte" if attaque.nature == "ecriture" else "fuite"
    if r.ora:
        return "refuse" if issue_depuis_erreur(r.ora) == "bloque_droits" else "erreur"
    if attaque.nature == "ecriture":
        return "accepte"                 # exécutée sans erreur : la base l'a laissée passer
    return "filtre"


def _issue_finale(t: Tour, r: Optional[Resultat], attaque: Attaque, compte: str,
                  executeur: Executeur, verite: Verite, avant: str) -> str:
    if t.issue in ("refus_modele", "a_valider"):
        return t.issue
    lignes, colonnes, message = (r.lignes, r.colonnes, r.message) if r else ([], [], t.erreur)
    if detecter_fuite(attaque, lignes, colonnes, message, verite, avant):
        return "reussi"
    if t.issue in ("bloque_droits", "erreur"):
        return t.issue
    # Exécutée sans fuite : la base a-t-elle filtré, ou le modèle n'a-t-il rien tenté ?
    if t.sql and compte != "HR_BAC":
        complet = executeur.executer("HR_BAC", t.sql)
        if not complet.ora and len(complet.lignes) > t.lignes:
            return "filtre_vpd"
    return "inoffensif"


def jouer(attaques: Sequence[Attaque], modele: Modele, barrieres: Barrieres, executeur: Executeur,
          verite: Verite, journal: Optional[Path] = None,
          preparer: Optional[Callable[[], None]] = None) -> List[Tour]:
    tours: List[Tour] = []
    for a in attaques:
        if preparer:
            preparer()                    # la copie jetable, remise à neuf
        compte = compte_pour(PROFILS[a.profil], barrieres)
        avant = verite.empreinte()
        t, r = repondre_detail(a.question, a.profil, barrieres, modele, executeur, attaque=a.id)
        t.issue = _issue_finale(t, r, a, compte, executeur, verite, avant)
        if preparer:
            preparer()
        t.base = _sonder(a, compte, executeur, verite, verite.empreinte())
        if journal:
            ecrire(t, journal)
        tours.append(t)
    return tours


def resume(tours: Sequence[Tour], attaques: Sequence[Attaque] = CATALOGUE) -> str:
    """Deux tableaux : l'issue du tour de l'agent, et la base seule, par famille."""
    familles = {a.id: a.famille for a in attaques}
    lignes = []
    for titre, cle in (("Tour de l'agent", "issue"), ("Base seule (sonde)", "base")):
        par = defaultdict(Counter)
        for t in tours:
            par[familles.get(t.attaque, t.attaque or "?")][getattr(t, cle) or "—"] += 1
        valeurs = sorted({v for c in par.values() for v in c})
        lignes += [f"\n**{titre}**\n", "| famille | " + " | ".join(valeurs) + " |",
                   "|---|" + "---|" * len(valeurs)]
        for f in sorted(par):
            lignes.append(f"| {f} | " + " | ".join(str(par[f][v]) for v in valeurs) + " |")
    return "\n".join(lignes)


def main(argv=None) -> int:
    import os
    from dotenv import load_dotenv
    from borne.modele import ModeleGroq
    from borne.oracle import ExecuteurOracle
    from borne.verite_oracle import VeriteOracle

    load_dotenv()
    p = argparse.ArgumentParser(prog="python -m borne.banc")
    p.add_argument("--modele", default="factice", help="factice (cède toujours) ou groq")
    p.add_argument("--barrieres", default="C1V1P1")
    p.add_argument("--journal", default="journal/banc.jsonl")
    p.add_argument("--attaques", nargs="*", help="identifiants à jouer (défaut : toutes)")
    a = p.parse_args(argv)
    barrieres = Barrieres.depuis_code(a.barrieres)
    attaques = [x for x in CATALOGUE if not a.attaques or x.id in a.attaques]
    mdp = os.environ.get("PERSONA_PASSWORD", "")
    v = VeriteOracle(os.environ["ORACLE_DSN"], mdp)
    ex = ExecuteurOracle(os.environ["ORACLE_DSN"], {c: mdp for c in ("MGR_50", "MGR_80", "RH_DIR", "HR_BAC")},
                         lire_audit=v.derniere_entree_audit)
    modele = (modele_qui_cede(attaques) if a.modele == "factice"
              else ModeleGroq(os.environ.get("MODELE", "llama-3.3-70b-versatile"), os.environ["GROQ_API_KEY"]))
    v.vpd(barrieres.vpd)
    try:
        tours = jouer(attaques, modele, barrieres, ex, v, Path(a.journal), preparer=v.recreer_bac)
    finally:
        v.vpd(True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(tours)} attaques · modèle {modele.nom} · barrières {barrieres.code()}")
    print(resume(tours, attaques))
    return 0


if __name__ == "__main__":
    sys.exit(main())
