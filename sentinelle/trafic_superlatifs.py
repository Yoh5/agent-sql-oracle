"""Le trafic légitime du jeu neuf des superlatifs : l'agent répond, la réponse est journalisée.

    python -m sentinelle.trafic_superlatifs --modele openrouter:openai/gpt-oss-120b
    python -m sentinelle.mesure_intention --modele openai/gpt-oss-20b@v3 --jeu superlatifs
    python -m sentinelle.mesure_enquete journal/sentinelle/superlatifs-*.jsonl \
        --intention openai/gpt-oss-20b@v3 --avis openrouter:mistralai/mistral-small-3.2-24b-instruct@v3 \
        --sortie journal/sentinelle/enquete-superlatifs.md

Même format que le journal de campagne (`type: utilite`), pour que `mesure_enquete` et `actions` le
lisent tel quel. Deux configurations : la production (`C1V1P1`) et l'agent sans barrières de base
(`C0V0P1`, ce que voit la sentinelle quand la base ne filtre pas). Un journal déjà complet n'est pas
rejoué.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main(argv=None) -> int:
    from dotenv import load_dotenv
    from borne.campagne import est_panne, jouer_utilite
    from borne.config import Barrieres
    from borne.modele import modele_depuis, nom_de_fichier
    from borne.oracle import ExecuteurOracle
    from borne.verite_oracle import VeriteOracle
    from sentinelle.questions_superlatifs import QUESTIONS_SUPERLATIFS

    load_dotenv(".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", default="openrouter:openai/gpt-oss-120b")
    ap.add_argument("--configs", nargs="*", default=["C1V1P1", "C0V0P1"])
    ap.add_argument("--repetitions", type=int, default=2)
    a = ap.parse_args(argv)

    chemin = Path("journal/sentinelle", f"superlatifs-{nom_de_fichier(a.modele)}.jsonl")
    attendu = len(a.configs) * a.repetitions * len(QUESTIONS_SUPERLATIFS)
    if chemin.exists() and sum(1 for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()) >= attendu:
        print(f"{chemin} déjà complet")
        return 0
    mdp = os.environ.get("PERSONA_PASSWORD", "")
    v = VeriteOracle(os.environ["ORACLE_DSN"], mdp)
    v.vpd(True)
    ex = ExecuteurOracle(os.environ["ORACLE_DSN"], {c: mdp for c in ("MGR_50", "MGR_80", "RH_DIR", "HR_BAC")},
                         lire_audit=v.derniere_entree_audit)
    modele = modele_depuis(a.modele)
    lignes = []
    for cfg in a.configs:
        b = Barrieres.depuis_code(cfg)
        v.vpd(b.vpd)
        try:
            for rep in range(a.repetitions):
                for l in jouer_utilite(QUESTIONS_SUPERLATIFS, modele, b, ex, v):
                    lignes.append({**l, "repetition": rep})
        finally:
            v.vpd(True)
    pannes = [l for l in lignes if est_panne(l)]
    if pannes:
        raise SystemExit(f"{len(pannes)} panne(s) du modèle, rien d'écrit. Ex. : {pannes[0].get('erreur', '')[:160]}")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    juste = sum(l["issue"] == "juste" for l in lignes)
    print(f"{chemin} : {len(lignes)} réponses, {juste} justes ; appels {getattr(modele, 'appels', '?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
