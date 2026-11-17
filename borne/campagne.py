"""La campagne : sécurité ET utilité, par modèle et par configuration de barrières.

    python -m borne.campagne --modele openai/gpt-oss-120b
    python -m borne.campagne --modele factice-parfait --configs C1V1P1   # sans coût

Pour chaque configuration (les 8 combinaisons C/V/P) :
- les 20 attaques, `--repetitions` fois (le banc : issue de l'agent + sonde de la base) ;
- les 90 questions légitimes (utilité : juste / faux / refus à tort / erreur).

Tout part dans un journal JSONL (une ligne par tour) et un résumé Markdown. Un chiffre
de sécurité ne se lit JAMAIS sans celui d'utilité à côté : un agent qui refuse tout
est sûr et inutile.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence

from borne.agent import Executeur, repondre_detail
from borne.attaques import CATALOGUE
from borne.banc import jouer, modele_qui_cede
from borne.config import PROFILS, Barrieres, contexte_utilisateur
from borne.modele import Modele, Proposition
from borne.utilite import QUESTIONS, QuestionUtile, issue_utilite

TOUTES_CONFIGS = ["".join(f"{l}{int(b)}" for l, b in zip("CVP", bits))
                  for bits in itertools.product((True, False), repeat=3)]


class ModeleParfait:
    """Rend la requête de vérité de chaque question : le plafond d'utilité, sans LLM.
    Sert à valider la chaîne de mesure avant de payer un vrai modèle.

    Indexé par (contexte, question) et non par la question seule : les managers des
    services 50 et 80 posent la MÊME phrase. Indexé par la question, le service 80
    écrasait le 50, et le « parfait » ne faisait que 73 % (vu le 16/11/2026)."""
    nom = "factice-parfait"

    def __init__(self, questions: Sequence[QuestionUtile]):
        self.reponses = {(contexte_utilisateur(PROFILS[q.profil]), q.question): q.sql_verite
                         for q in questions}

    def ecrire_sql(self, question: str, schema: str, consignes: bool, contexte: str = "") -> Proposition:
        sql = self.reponses.get((contexte, question.split("\n\nTa requête précédente a échoué", 1)[0]))
        return Proposition(sql, None, sql or "") if sql else Proposition(None, "question inconnue", "")


def modele_parfait(questions: Sequence[QuestionUtile]) -> ModeleParfait:
    return ModeleParfait(questions)


def jouer_utilite(questions: Sequence[QuestionUtile], modele: Modele, barrieres: Barrieres,
                  executeur: Executeur, verite) -> List[dict]:
    lignes = []
    for q in questions:
        t, r = repondre_detail(q.question, q.profil, barrieres, modele, executeur)
        issue = issue_utilite(t.issue, r.lignes if r else None, verite.lignes(q.sql_verite))
        lignes.append({"type": "utilite", "id": q.id, "profil": q.profil, "barrieres": barrieres.code(),
                       "modele": t.modele, "issue": issue, "issue_agent": t.issue, "sql": t.sql,
                       "erreur": t.erreur})
    return lignes


def est_panne(ligne: dict) -> bool:
    """Le modèle n'a pas répondu (quota, réseau) : ce tour ne mesure rien."""
    return (ligne.get("erreur") or "").startswith("modèle injoignable")


def preparer_reprise(chemin: Path, configs: Sequence[str], attendu_attaques: int,
                     attendu_utilite: int) -> List[str]:
    """Reprendre une campagne interrompue : saute les configurations complètes dans le
    journal, EFFACE celles à moitié faites (sinon leurs tours compteraient double) et
    rend celles qui restent à jouer."""
    if not chemin.exists():
        return list(configs)
    lignes = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
    compte: Dict[str, Counter] = {}
    for l in lignes:
        compte.setdefault(l["barrieres"], Counter())[l["type"]] += 1
    completes = {c for c, n in compte.items()
                 if n["attaque"] >= attendu_attaques and n["utilite"] >= attendu_utilite}
    gardees = [l for l in lignes if l["barrieres"] in completes]
    if len(gardees) != len(lignes):
        chemin.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in gardees),
                          encoding="utf-8")
    return [c for c in configs if c not in completes]


def resumer(journal: Sequence[dict]) -> str:
    """Un tableau par configuration : attaques passées (agent / base seule) et utilité."""
    par_cfg: Dict[str, Dict[str, Counter]] = {}
    for l in journal:
        c = par_cfg.setdefault(l["barrieres"], {"att": Counter(), "base": Counter(), "util": Counter()})
        if l["type"] == "attaque":
            c["att"]["total"] += 1
            c["att"]["passe"] += l["issue"] == "reussi"
            c["base"]["passe"] += l.get("base") in ("fuite", "accepte")
            c["att"]["refus_modele"] += l["issue"] == "refus_modele"
            c["att"]["erreur"] += l["issue"] == "erreur"
        else:
            c["util"]["total"] += 1
            c["util"][l["issue"]] += 1
    out = ["| barrières | attaques passées (agent) | base seule laisse passer | refus du modèle (attaques) "
           "| utilité : juste | refus à tort | faux | erreur |", "|---|---|---|---|---|---|---|---|"]
    for cfg in TOUTES_CONFIGS:
        if cfg not in par_cfg:
            continue
        a, b, u = par_cfg[cfg]["att"], par_cfg[cfg]["base"], par_cfg[cfg]["util"]
        nu = u["total"] or 1
        out.append(f"| `{cfg}` | {a['passe']}/{a['total']} | {b['passe']}/{a['total']} "
                   f"| {a['refus_modele']}/{a['total']} "
                   f"| {u['juste']}/{u['total']} ({100 * u['juste'] // nu} %) | {u['refus_a_tort']} "
                   f"| {u['faux']} | {u['erreur']} |")
    return "\n".join(out)


def main(argv=None) -> int:
    from dotenv import load_dotenv
    from borne.modele import modele_depuis, nom_de_fichier
    from borne.oracle import ExecuteurOracle
    from borne.verite_oracle import VeriteOracle

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    p = argparse.ArgumentParser(prog="python -m borne.campagne")
    p.add_argument("--modele", required=True, help="nom de modèle Groq, ou factice-parfait / factice-cede")
    p.add_argument("--configs", nargs="*", default=TOUTES_CONFIGS)
    p.add_argument("--repetitions", type=int, default=3, help="répétitions des attaques")
    p.add_argument("--sans-utilite", action="store_true")
    p.add_argument("--sans-attaques", action="store_true")
    p.add_argument("--sortie", default="journal/campagne")
    p.add_argument("--adb", action="store_true",
                   help="tout le banc sur Autonomous Database Free (comparaison Select AI, borne/select_ai.py)")
    a = p.parse_args(argv)
    if a.adb:
        from borne.select_ai import rediriger_vers_adb
        rediriger_vers_adb()
        a.sortie = a.sortie if a.sortie != "journal/campagne" else "journal/select_ai"

    mdp = os.environ.get("PERSONA_PASSWORD", "")
    v = VeriteOracle(os.environ["ORACLE_DSN"], mdp)
    # Une exécution interrompue laisse la règle d'accès coupée (son `finally` ne s'exécute
    # pas) : on repart TOUJOURS d'une base protégée.
    v.vpd(True)
    ex = ExecuteurOracle(os.environ["ORACLE_DSN"], {c: mdp for c in ("MGR_50", "MGR_80", "RH_DIR", "HR_BAC")},
                         lire_audit=None if a.adb else v.derniere_entree_audit)  # pas d'audit sur ADB
    if a.modele == "factice-parfait":
        modele_att, modele_util = modele_qui_cede(CATALOGUE), modele_parfait(QUESTIONS)
    elif a.modele == "factice-cede":
        modele_att = modele_util = modele_qui_cede(CATALOGUE)
    elif a.modele.startswith("selectai:"):
        from borne.select_ai import ModeleSelectAI
        modele_att = modele_util = ModeleSelectAI(a.modele.split(":", 1)[1])
    else:
        modele_att = modele_util = modele_depuis(a.modele)

    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    nom = nom_de_fichier(a.modele)
    chemin = sortie / f"{nom}.jsonl"
    configs = preparer_reprise(chemin, a.configs,
                               0 if a.sans_attaques else a.repetitions * len(CATALOGUE),
                               0 if a.sans_utilite else len(QUESTIONS))
    if configs != list(a.configs):
        print(f"  reprise : déjà faites {sorted(set(a.configs) - set(configs))}", flush=True)
    journal: List[dict] = []
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    debut = time.time()
    with chemin.open("a", encoding="utf-8") as f:
        for cfg in configs:
            b = Barrieres.depuis_code(cfg)
            lignes_cfg: List[dict] = []      # écrites SEULEMENT si la configuration est saine
            if not a.sans_attaques:
                v.vpd(b.vpd)
                try:
                    for rep in range(a.repetitions):
                        for t in jouer(CATALOGUE, modele_att, b, ex, v, journal=None, preparer=v.recreer_bac):
                            lignes_cfg.append({"type": "attaque", "id": t.attaque, "repetition": rep,
                                               **t.__dict__})
                finally:
                    v.vpd(True)
            if not a.sans_utilite:
                v.vpd(b.vpd)
                try:
                    lignes_cfg.extend(jouer_utilite(QUESTIONS, modele_util, b, ex, v))
                finally:
                    v.vpd(True)
            pannes = [l for l in lignes_cfg if est_panne(l)]
            if pannes:
                # Une panne n'est JAMAIS une mesure : rien de cette configuration n'est écrit,
                # la campagne s'arrête et la reprise la rejouera.
                raise SystemExit(f"  {cfg} : {len(pannes)} panne(s) du modèle, configuration NON "
                                 f"enregistrée — relancer plus tard. Ex. : {pannes[0].get('erreur', '')[:160]}")
            for l in lignes_cfg:
                f.write(json.dumps(l, ensure_ascii=False) + "\n")
            journal.extend(lignes_cfg)
            f.flush()
            print(f"  {cfg} fait ({time.time() - debut:.0f} s)", flush=True)
    # Le résumé porte sur TOUT le journal, reprises comprises.
    tout = [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]
    resume = f"# Campagne — {a.modele}\n\n" + resumer(tout) + "\n"
    if hasattr(modele_att, "jetons_entree"):
        resume += (f"\nCette exécution : {modele_att.appels} appels · {modele_att.jetons_entree} jetons en entrée · "
                   f"{modele_att.jetons_sortie} en sortie · {time.time() - debut:.0f} s\n")
    (sortie / f"{nom}.md").write_text(resume, encoding="utf-8")
    print(resume)
    return 0


if __name__ == "__main__":
    sys.exit(main())
