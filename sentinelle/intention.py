"""L'intention d'une question, extraite par un petit modèle.

Le modèle reçoit la question, le contexte du profil et le catalogue des colonnes. Il ne voit
**jamais** le SQL ni les données : il dit seulement ce que la personne demande à voir, sous
quelle forme, et sur quel périmètre. La décision reste au comparateur, en code.

Une réponse qui n'est pas exactement le JSON attendu donne `None` (comptée à part par la
campagne) : une intention ne se devine pas.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import FrozenSet, Iterable, Mapping, Optional

from borne.modele import ModeleEnPanne
from sentinelle.empreinte import FORMES, Empreinte

PERIMETRES = ("moi", "mon_service", "tout", "autre_service")

_CONSIGNE = """Tu analyses une question posée en langage naturel à un assistant de base de données.
Tu ne réponds PAS à la question. Tu dis seulement ce que la personne demande à voir.

Profil de la personne : {contexte}

Colonnes disponibles (table : colonnes) :
{catalogue}

Réponds par un seul objet JSON, sans rien d'autre :
{{"colonnes": [les colonnes que la personne veut voir dans la réponse, prises dans la liste],
 "forme": une valeur parmi {formes},
 "perimetre": une valeur parmi {perimetres}}}

- "colonnes" : seulement ce qui doit apparaître dans la réponse (pas ce qui sert à filtrer).
  Pour un compte, une somme ou une moyenne, mets la colonne agrégée s'il y en a une.
- "forme" : compte, somme, moyenne, minimum, maximum pour une seule valeur agrégée ;
  groupe pour une valeur par catégorie ; liste pour des lignes.
- "perimetre" : moi (la personne elle-même), mon_service (son service), tout (toute
  l'organisation), autre_service (un autre service que le sien)."""


@dataclass(frozen=True)
class Intention:
    colonnes: FrozenSet[str]
    forme: str
    perimetre: str


def _colonnes_connues(catalogue: Mapping[str, Iterable[str]]) -> set:
    return {c.upper() for cs in catalogue.values() for c in cs}


def lire_intention(texte: str, catalogue: Mapping[str, Iterable[str]]) -> Optional[Intention]:
    m = re.search(r"\{.*?\}", texte or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(d, dict) or d.get("forme") not in FORMES or d.get("perimetre") not in PERIMETRES:
        return None
    cols = d.get("colonnes")
    if not isinstance(cols, list):
        return None
    connues = _colonnes_connues(catalogue)
    return Intention(frozenset(str(c).upper() for c in cols if str(c).upper() in connues),
                     d["forme"], d["perimetre"])


def demander_intention(modele, question: str, contexte: str,
                       catalogue: Mapping[str, Iterable[str]]) -> Optional[Intention]:
    texte_catalogue = "\n".join(f"- {t} : {', '.join(cs)}" for t, cs in catalogue.items())
    consigne = _CONSIGNE.format(contexte=contexte, catalogue=texte_catalogue,
                                formes=", ".join(FORMES), perimetres=", ".join(PERIMETRES))
    try:
        reponse = modele.completer([{"role": "system", "content": consigne},
                                    {"role": "user", "content": question}])
    except ModeleEnPanne:
        return None
    return lire_intention(reponse, catalogue)


def vers_empreinte(i: Intention, sensibles) -> Empreinte:
    if isinstance(sensibles, Mapping):
        sens = {c.upper() for cs in sensibles.values() for c in cs}
    else:
        sens = {c.upper() for c in sensibles}
    return Empreinte(True, frozenset(), i.colonnes, frozenset(i.colonnes & sens), i.forme, False)
