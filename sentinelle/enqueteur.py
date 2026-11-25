"""L'enquêteur : trancher les cas « enquêter » de la sentinelle, sans croire le texte de l'attaquant.

Un workflow en code, pas un orchestrateur : l'ordre des étapes est fixe, et aucun modèle ne décide seul.
1. sonde de périmètre (code + Oracle) : une ligne hors du service → couper ; sonde impossible → humain ;
2. historique de session : déjà 2 coupures ou enquêtes → humain (l'attaquant qui insiste) ;
3. raisons levées une à une : « … lue sans filtre » par la sonde ; « colonne … non demandée / en plus »
   par un second avis d'une autre famille (qui lit la question : il ne peut lever que ça) ;
   « intention illisible » (25/11) : le second avis lit la question en entier, et la chaîne est rejouée
   avec son intention (`rejuger`) ; les raisons de ce rejeu remplacent l'illisible ;
   « liste rendue pour une question de … » (25/11) : levée si la réponse que l'agent a REÇUE (compte de
   l'utilisateur, VPD) tient en une ligne au plus — « le nom de la dernière embauche » est une liste
   bornée par `FETCH FIRST 1` ou `= (SELECT MAX…)`, pas une fuite en masse ;
4. libérer seulement si plus aucune raison ne reste. Toute autre raison → humain, avec le dossier.

Une libération à tort ne peut rendre que des lignes du service de l'utilisateur (la sonde l'a prouvé),
avec une colonne qu'il a le droit de voir mais n'a peut-être pas demandée — jamais un autre service.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence, Tuple

from sentinelle.intention import Intention
from sentinelle.sonde import construire_sonde

ILLISIBLE = "intention illisible"   # même texte que sentinelle.chaine.INTENTION_ILLISIBLE

ACTIONS_ENQUETE = ("liberer", "couper", "humain")
SUSPECTES = ("couper", "enqueter", "humain")
SEUIL_SESSION = 2

_ACCES_TOTAL = re.compile(r"^\s*1\s*=\s*1\s*$")
_SANS_FILTRE = re.compile(r"^\S+ lue sans filtre sur \S+$")
_LISTE = re.compile(r"^liste rendue pour une question de \S+$")
_COLONNE = re.compile(r"^colonne (?:sensible )?(\S+) (?:non demandée|en plus)$")


@dataclass(frozen=True)
class Dossier:
    action: str
    raisons_levees: Tuple[str, ...]
    raisons_restantes: Tuple[str, ...]
    sonde: Optional[str]
    hors: Optional[bool]
    avis: Optional[Tuple[str, ...]]
    historique: int


def enqueter(sql: str, raisons: Sequence[str], regle: str, partitionnees: Iterable[str],
             sonder: Callable[[str], Optional[bool]], second_avis: Callable[[], Optional[Intention]],
             historique: Sequence[str],
             rejuger: Optional[Callable[[Intention], Sequence[str]]] = None,
             lignes: Optional[int] = None) -> Dossier:
    """`lignes` : le nombre de lignes de la réponse que l'agent a reçue (None : inconnu, rien n'est levé)."""
    n_suspects = sum(a in SUSPECTES for a in historique)
    sonde, motif = construire_sonde(sql, regle, partitionnees)
    if sonde is None and _ACCES_TOTAL.match(regle or ""):
        # Règle « 1 = 1 » (la RH) : tout le schéma est permis, aucune ligne ne peut être hors périmètre.
        hors, motif = False, None
    else:
        hors = sonder(sonde) if sonde is not None else None

    def dossier(action, levees=(), restantes=(), avis=None):
        return Dossier(action, tuple(levees), tuple(restantes), sonde, hors, avis, n_suspects)

    if hors is True:
        return dossier("couper", restantes=raisons)
    if sonde is None and motif is not None:
        return dossier("humain", restantes=(f"sonde impossible : {motif}",) + tuple(raisons))
    if hors is None:
        return dossier("humain", restantes=("sonde en erreur",) + tuple(raisons))
    if n_suspects >= SEUIL_SESSION:
        return dossier("humain", restantes=(f"session suspecte ({n_suspects} décisions)",) + tuple(raisons))

    levees, restantes, colonnes_avis = [], [], None
    if ILLISIBLE in raisons and rejuger is not None:
        i = second_avis()
        if i is None:
            return dossier("humain", restantes=raisons)
        # Les raisons « colonne … » du rejeu viennent de l'intention du second avis lui-même : elles ne
        # peuvent pas être levées par lui (la colonne n'est pas dans ce qu'il a lu).
        colonnes_avis = tuple(sorted(c.upper() for c in i.colonnes))
        nouvelles = tuple(r for r in rejuger(i) if r not in raisons)
        levees.append(ILLISIBLE)
        raisons = tuple(r for r in raisons if r != ILLISIBLE) + nouvelles
    for r in raisons:
        m = _COLONNE.match(r)
        if _SANS_FILTRE.match(r):
            levees.append(r)
        elif _LISTE.match(r):
            (levees if lignes is not None and lignes <= 1 else restantes).append(r)
        elif m:
            if colonnes_avis is None:
                i = second_avis()
                colonnes_avis = tuple(sorted(c.upper() for c in i.colonnes)) if i is not None else ()
            (levees if m.group(1).upper() in colonnes_avis else restantes).append(r)
        else:
            restantes.append(r)
    return dossier("humain" if restantes else "liberer", levees, restantes, colonnes_avis)
