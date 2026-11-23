"""La décision par paliers : une action dans une liste FERMÉE, choisie par du code.

- couper    : le SQL filtre hors de la règle du profil (lu par le code) — on ne réécrit pas une
              demande hors périmètre (case A de la méthode : règle en code seulement) ;
- laisser   : score sous le seuil ;
- reecrire  : une réécriture minimale existe et le comparateur l'a validée (case C) ;
- enqueter  : tout le reste — c'est là que l'agent enquêteur interviendra (case D).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from sentinelle.comparateur import Verdict

ACTIONS = ("laisser", "reecrire", "enqueter", "couper")


@dataclass(frozen=True)
class Decision:
    action: str
    sql: Optional[str] = None


def decider(verdict: Verdict, hors: Sequence[str], reecriture: Optional[str], seuil: int) -> Decision:
    if hors:
        return Decision("couper")
    if verdict.score < seuil:
        return Decision("laisser")
    if reecriture is not None:
        return Decision("reecrire", reecriture)
    return Decision("enqueter")
