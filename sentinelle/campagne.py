"""Remplir le cache des intentions : chaque question unique est posée UNE fois au modèle.

Questions : les 90 légitimes du banc d'utilité, et les questions des attaques du journal.
Le cache (`journal/sentinelle/intentions-<modele>.jsonl`) rend le rejeu gratuit et rejouable ;
une intention illisible y est gardée illisible (`null`), jamais redemandée en douce.

    python -m sentinelle.campagne --modele openai/gpt-oss-20b --pilote 5   # coût mesuré d'abord
    python -m sentinelle.campagne --modele openai/gpt-oss-20b              # tout
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sentinelle.catalogue import CATALOGUE_HR
from sentinelle.intention import Intention, demander_intention

DOSSIER = Path("journal/sentinelle")
BANC = Path("bancs/hr/banc.yaml")


class Cache:
    def __init__(self, chemin: Path, modele, consigne: str = "v1"):
        self.chemin, self.modele, self.consigne = Path(chemin), modele, consigne
        self.valeurs: Dict[Tuple[str, str], Optional[Intention]] = {}
        if self.chemin.exists():
            for l in self.chemin.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    d = json.loads(l)
                    i = d["intention"]
                    self.valeurs[(d["profil"], d["question"])] = None if i is None else Intention(
                        frozenset(i["colonnes"]), i["forme"], i["perimetre"])

    def intention(self, profil: str, contexte: str, question: str) -> Optional[Intention]:
        cle = (profil, question)
        if cle not in self.valeurs:
            i = demander_intention(self.modele, question, contexte, CATALOGUE_HR, self.consigne)
            self.valeurs[cle] = i
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"profil": profil, "question": question, "intention": None if i is None else
                                    {"colonnes": sorted(i.colonnes), "forme": i.forme,
                                     "perimetre": i.perimetre}}, ensure_ascii=False) + "\n")
        return self.valeurs[cle]


def profils() -> Dict[str, dict]:
    from borne.generique import lire
    return lire(str(BANC)).profils


def questions_a_poser(journaux: Iterable[str]) -> List[Tuple[str, str]]:
    """(profil, question) uniques : légitimes d'abord, puis attaques du journal."""
    from borne.utilite import QUESTIONS
    vues = {}
    for q in QUESTIONS:
        vues.setdefault((q.profil, q.question), None)
    for chemin in journaux:
        for l in Path(chemin).read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                if d.get("type") == "attaque" and d.get("question"):
                    vues.setdefault((d["profil"], d["question"]), None)
    return list(vues)


def separer_consigne(nom: str) -> Tuple[str, str]:
    """« modele@v2 » → (« modele », « v2 ») ; sans « @ », la consigne v1."""
    modele, _, consigne = nom.partition("@")
    return modele, consigne or "v1"


def suffixe_consigne(nom: str) -> str:
    """« -v3 » pour `modele@v3`, rien pour v1 : les sorties d'une consigne n'écrasent pas celles d'une autre."""
    consigne = separer_consigne(nom)[1]
    return "" if consigne == "v1" else f"-{consigne}"


def chemin_cache(nom: str) -> Path:
    """Un cache par modèle ET par consigne : `modele@v2` n'écrase jamais le cache de v1."""
    from borne.modele import nom_de_fichier
    return DOSSIER / f"intentions-{nom_de_fichier(separer_consigne(nom)[0])}{suffixe_consigne(nom)}.jsonl"


def main() -> int:
    from dotenv import load_dotenv
    from borne.modele import modele_depuis
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", default="openai/gpt-oss-20b")
    ap.add_argument("--pilote", type=int, default=0)
    ap.add_argument("journaux", nargs="*", default=[str(p) for p in Path("journal/campagne").glob("*.jsonl")])
    a = ap.parse_args()
    nom, consigne = separer_consigne(a.modele)
    modele = modele_depuis(nom)
    cache = Cache(chemin_cache(a.modele), modele, consigne)
    ctx = profils()
    a_faire = [qp for qp in questions_a_poser(a.journaux) if qp not in cache.valeurs]
    if a.pilote:
        a_faire = a_faire[:a.pilote]
    print(f"{len(a_faire)} questions à poser ({len(cache.valeurs)} déjà en cache)")
    for profil, question in a_faire:
        cache.intention(profil, ctx[profil]["contexte"], question)
    print(f"appels {modele.appels}, jetons entrée {modele.jetons_entree}, sortie {modele.jetons_sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
