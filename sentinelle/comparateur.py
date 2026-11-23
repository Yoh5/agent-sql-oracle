"""Le comparateur : ce que la question demandait contre ce que le SQL fait sortir.

C'est le cœur de la sentinelle, et il est en code exprès : il ne lit jamais le texte de
l'attaquant, seulement deux empreintes. Une injection peut tromper ce qui écrit le SQL ou
ce qui traduit la question en intention ; elle ne peut pas convaincre cette comparaison.

Barème de la phase 1, à recalibrer par le rejeu (les seuils se lisent sur le trafic
légitime, ils ne se choisissent pas a priori).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sentinelle.empreinte import Empreinte

POIDS_ILLISIBLE = 5
POIDS_SENSIBLE = 4
POIDS_FORME = 4
POIDS_ETOILE = 3
POIDS_TABLE = 2
POIDS_COLONNE = 1
POIDS_PERIMETRE = 4
_HORS_PERIMETRE = {"tout", "autre_service"}

_LISTES = {"liste", "groupe"}


@dataclass(frozen=True)
class Verdict:
    score: int
    raisons: Tuple[str, ...]


def comparer(intention: Empreinte, reelle: Empreinte, perimetre: Optional[str] = None,
             acces_total: bool = False) -> Verdict:
    """`perimetre` vient de l'intention extraite par le modèle ; une intention lue dans une
    requête de vérité n'en a pas. `intention.tables` vide (intention d'un modèle) : la règle des
    tables ne s'applique pas, faute de savoir quelles tables la question vise."""
    if not reelle.valide:
        return Verdict(POIDS_ILLISIBLE, ("SQL illisible pour la sentinelle",))
    score, raisons = 0, []
    for c in sorted(reelle.sensibles - intention.sensibles):
        score += POIDS_SENSIBLE
        raisons.append(f"colonne sensible {c} non demandée")
    if intention.forme not in _LISTES and reelle.forme == "liste":
        score += POIDS_FORME
        raisons.append(f"liste rendue pour une question de {intention.forme}")
    if reelle.etoile and not intention.etoile:
        score += POIDS_ETOILE
        raisons.append("SELECT *")
    if perimetre in _HORS_PERIMETRE and not acces_total:
        score += POIDS_PERIMETRE
        raisons.append("question hors du périmètre du profil")
    for t in (sorted(reelle.tables - intention.tables) if intention.tables else []):
        score += POIDS_TABLE
        raisons.append(f"table {t} non demandée")
    for c in sorted(reelle.colonnes - intention.colonnes - reelle.sensibles):
        score += POIDS_COLONNE
        raisons.append(f"colonne {c} en plus")
    return Verdict(score, tuple(raisons))
