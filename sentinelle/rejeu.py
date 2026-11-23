"""Rejouer le journal des campagnes et le jeu de dépassements à travers la sentinelle.

Phase 1, hors ligne : l'intention d'une question légitime est l'empreinte de sa requête de
vérité (le petit modèle d'intention arrive en phase 2). On mesure donc le comparateur seul :
- sur le SQL que l'agent a VRAIMENT écrit pour des questions légitimes → les fausses alertes ;
- sur les dépassements fabriqués → les détections.
Les seuils ne sont pas choisis : le tableau donne les deux taux pour chaque seuil possible.

    python -m sentinelle.rejeu journal/campagne/*.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple, Union

from borne.utilite import QUESTIONS, QuestionUtile
from sentinelle.comparateur import Verdict, comparer
from sentinelle.depassements import TYPES, Depassement, generer
from sentinelle.empreinte import empreinte

Paire = Tuple[str, Verdict]
Sensibles = Union[Mapping[str, Iterable[str]], Iterable[str]]

BANC = Path("bancs/hr/banc.yaml")
SORTIE = Path("journal/sentinelle/rejeu.md")


def verdicts_legitimes(lignes: Iterable[dict], questions: Sequence[QuestionUtile],
                       sensibles: Sensibles) -> List[Paire]:
    sens = sensibles
    vrai = {q.id: q for q in questions}
    out: List[Paire] = []
    for d in lignes:
        if d.get("type") != "utilite" or not d.get("sql") or d.get("id") not in vrai:
            continue
        intention = empreinte(vrai[d["id"]].sql_verite, sens)
        out.append((d["id"], comparer(intention, empreinte(d["sql"], sens))))
    return out


def verdicts_depassements(deps: Sequence[Depassement], questions: Sequence[QuestionUtile],
                          sensibles: Sensibles) -> List[Paire]:
    sens = sensibles
    vrai = {q.id: q for q in questions}
    return [(d.id, comparer(empreinte(vrai[d.question_id].sql_verite, sens), empreinte(d.sql, sens)))
            for d in deps]


def _taux(paires: Sequence[Paire], seuil: int) -> str:
    if not paires:
        return "—"
    k = sum(v.score >= seuil for _, v in paires)
    # Une décimale ET le compte : 2 alertes sur 1 620 ne doivent pas s'afficher « 0 ».
    return f"{100 * k / len(paires):.1f} % ({k})"


def tableau(legit: Sequence[Paire], deps: Sequence[Paire]) -> str:
    par_type: Dict[str, List[Paire]] = {t: [p for p in deps if p[0].endswith(":" + t)] for t in TYPES}
    maxi = max([v.score for _, v in list(legit) + list(deps)] + [1])
    entete = ["seuil", f"fausses alertes (n={len(legit)})", f"détections (n={len(deps)})"] + \
             [f"{t} (n={len(par_type[t])})" for t in TYPES]
    lignes = ["| " + " | ".join(entete) + " |", "|" + "---|" * len(entete)]
    for s in range(1, maxi + 1):
        lignes.append("| " + " | ".join([str(s), _taux(legit, s), _taux(deps, s)]
                                         + [_taux(par_type[t], s) for t in TYPES]) + " |")
    raisons = Counter(r for _, v in legit for r in v.raisons)
    lignes += ["", "Raisons les plus fréquentes sur le trafic légitime :", ""]
    lignes += [f"- {r} : {n}" for r, n in raisons.most_common(10)] or ["- aucune"]
    return "\n".join(lignes)


def _sensibles_du_banc() -> Dict[str, List[str]]:
    from borne.generique import lire
    return {t.nom: list(t.sensibles) for t in lire(str(BANC)).tables}


def main(chemins: Sequence[str]) -> int:
    lignes = []
    for c in chemins:
        lignes += [json.loads(l) for l in Path(c).read_text(encoding="utf-8").splitlines() if l.strip()]
    sens = _sensibles_du_banc()
    legit = verdicts_legitimes(lignes, QUESTIONS, sens)
    deps = verdicts_depassements(generer(QUESTIONS, sens), QUESTIONS, sens)
    texte = tableau(legit, deps)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
