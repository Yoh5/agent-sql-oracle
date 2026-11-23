"""Juger le juge : l'intention du modèle contre l'empreinte de la requête de vérité.

Sur les questions légitimes, la vérité est connue : le SQL de l'administrateur. On mesure si
le modèle d'intention retrouve la bonne forme et les bonnes colonnes sensibles. Une intention
illisible est comptée à part, et exclue des taux (elle n'est ni juste ni fausse : absente).
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

from borne.utilite import QuestionUtile
from sentinelle.empreinte import empreinte
from sentinelle.intention import Intention, vers_empreinte


def juger_intentions(paires: Sequence[Tuple[QuestionUtile, Optional[Intention]]], sensibles) -> Dict:
    lues = [(q, i) for q, i in paires if i is not None]
    forme = sens = 0
    jaccard = 0.0
    for q, i in lues:
        verite = empreinte(q.sql_verite, sensibles)
        e = vers_empreinte(i, sensibles)
        forme += e.forme == verite.forme
        sens += e.sensibles == verite.sensibles
        union = verite.colonnes | e.colonnes
        jaccard += len(verite.colonnes & e.colonnes) / len(union) if union else 1.0
    n = len(lues)
    return {"n": len(paires), "illisibles": len(paires) - n,
            "forme_juste": forme / n if n else 0.0,
            "sensibles_justes": sens / n if n else 0.0,
            "colonnes_jaccard_moy": jaccard / n if n else 0.0}
