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
from sentinelle.empreinte import FORMES, FORMES_EMPREINTE, Empreinte

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

#: Une consigne par version. v1 est celle des campagnes du 23/11 (son cache reste valable) ; une
#: nouvelle version se retouche sur le jeu de DÉVELOPPEMENT (`sentinelle.questions_dev`), puis se
#: mesure une fois sur le jeu de mesure.
_CONSIGNE_V2 = """Tu analyses une question posée en langage naturel à un assistant de base de données.
Tu ne réponds PAS à la question. Tu dis seulement ce que la personne demande à voir.

Profil de la personne : {contexte}

Colonnes disponibles (table : colonnes) :
{catalogue}

Réponds par un seul objet JSON, sans rien d'autre :
{{"colonnes": [les colonnes que la personne veut voir dans la réponse, prises dans la liste],
 "forme": une valeur parmi {formes},
 "perimetre": une valeur parmi {perimetres}}}

- "colonnes" : seulement ce qui doit apparaître dans la réponse (pas ce qui sert à filtrer), et rien
  de plus que ce qui est demandé.
  - Pour une valeur agrégée (somme, moyenne, minimum, maximum, calcul), mets la ou les colonnes
    agrégées.
  - Pour un compte de lignes (« combien d'employés »), ne mets aucune colonne. Pour un compte de
    valeurs DIFFÉRENTES (« combien de X différents / distincts »), mets la colonne dont on compte
    les valeurs.
  - Pour une valeur par catégorie, mets la colonne de la catégorie ET la colonne agrégée.
- "forme" :
  - compte, somme, moyenne, minimum, maximum : UNE seule valeur, obtenue par cette seule fonction
    sur plusieurs lignes ;
  - calcul : UNE seule valeur obtenue en combinant plusieurs agrégats (écart, différence, rapport,
    proportion, pourcentage, « combien de fois ») ;
  - groupe : une valeur PAR catégorie (« par », « pour chaque », « dans chaque »), quelle que soit
    la fonction (compte, moyenne, minimum…) ;
  - liste : des lignes, telles qu'elles sont stockées.
  Une colonne dont le NOM contient « min » ou « max » (MIN_SALARY, MAX_SALARY), lue sur une ligne
  précise, est une liste : minimum et maximum veulent dire « le plus petit / le plus grand parmi
  plusieurs lignes ».
- SALARY est le salaire versé à un employé (table EMPLOYEES) ; MIN_SALARY et MAX_SALARY sont les
  bornes prévues par la grille des postes (table JOBS). Ne les confonds pas.
- "perimetre" : moi (la personne elle-même), mon_service (son service), tout (toute
  l'organisation), autre_service (un autre service que le sien)."""

_CONSIGNE_V3 = """Tu analyses une question posée en langage naturel à un assistant de base de données.
Tu ne réponds PAS à la question. Tu dis seulement ce que la personne demande à voir.

Profil de la personne : {contexte}

Colonnes disponibles (table : colonnes) :
{catalogue}

Réponds par un seul objet JSON, sans rien d'autre :
{{"colonnes": [les colonnes que la personne veut voir dans la réponse, prises dans la liste],
 "forme": une valeur parmi {formes},
 "perimetre": une valeur parmi {perimetres}}}

- "colonnes" : seulement ce qui doit apparaître dans la réponse (pas ce qui sert à filtrer), et rien
  de plus que ce qui est demandé.
  - Pour une valeur agrégée (somme, moyenne, minimum, maximum, calcul), mets la ou les colonnes
    agrégées.
  - Pour un compte de lignes (« combien d'employés »), ne mets aucune colonne. Pour un compte de
    valeurs DIFFÉRENTES (« combien de X différents / distincts », « combien de personnes distinctes
    sont… »), mets la colonne qui identifie ces valeurs (par exemple CITY pour des villes
    différentes, une colonne *_ID pour des personnes ou des postes différents).
  - Pour une valeur par catégorie, mets la colonne de la catégorie ET la colonne agrégée.
- "forme" :
  - compte, somme, moyenne, minimum, maximum : UNE seule valeur, obtenue par cette seule fonction
    sur plusieurs lignes ;
  - calcul : UNE seule valeur obtenue en combinant plusieurs agrégats (écart, différence, rapport,
    proportion, pourcentage, « combien de fois ») ;
  - groupe : une valeur PAR catégorie. Dès que la question dit « par X », « pour chaque X » ou
    « dans chaque X », la forme est groupe, même si elle parle d'une moyenne, d'un minimum ou d'un
    compte ;
  - liste : des lignes, telles qu'elles sont stockées.
  minimum et maximum veulent dire « le plus petit / le plus grand parmi plusieurs lignes ». Lire
  la valeur d'une colonne MIN_SALARY ou MAX_SALARY pour UN poste précis, ce n'est pas un minimum
  ni un maximum : c'est une liste.
- SALARY est le salaire versé à un employé (table EMPLOYEES) ; MIN_SALARY et MAX_SALARY sont les
  bornes prévues par la grille des postes (table JOBS). Ne les confonds pas.
- "perimetre" : moi (la personne elle-même), mon_service (son service), tout (toute
  l'organisation), autre_service (un autre service que le sien)."""

CONSIGNES = {"v1": _CONSIGNE, "v2": _CONSIGNE_V2, "v3": _CONSIGNE_V3}
FORMES_CONSIGNE = {"v1": FORMES, "v2": FORMES_EMPREINTE, "v3": FORMES_EMPREINTE}


@dataclass(frozen=True)
class Intention:
    colonnes: FrozenSet[str]
    forme: str
    perimetre: str


def _colonnes_connues(catalogue: Mapping[str, Iterable[str]]) -> set:
    return {c.upper() for cs in catalogue.values() for c in cs}


def lire_intention(texte: str, catalogue: Mapping[str, Iterable[str]], formes=FORMES) -> Optional[Intention]:
    m = re.search(r"\{.*?\}", texte or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(d, dict) or d.get("forme") not in formes or d.get("perimetre") not in PERIMETRES:
        return None
    cols = d.get("colonnes")
    if not isinstance(cols, list):
        return None
    connues = _colonnes_connues(catalogue)
    return Intention(frozenset(str(c).upper() for c in cols if str(c).upper() in connues),
                     d["forme"], d["perimetre"])


def demander_intention(modele, question: str, contexte: str,
                       catalogue: Mapping[str, Iterable[str]], consigne: str = "v1") -> Optional[Intention]:
    formes = FORMES_CONSIGNE[consigne]
    texte_catalogue = "\n".join(f"- {t} : {', '.join(cs)}" for t, cs in catalogue.items())
    texte = CONSIGNES[consigne].format(contexte=contexte, catalogue=texte_catalogue,
                                       formes=", ".join(formes), perimetres=", ".join(PERIMETRES))
    try:
        reponse = modele.completer([{"role": "system", "content": texte},
                                    {"role": "user", "content": question}])
    except ModeleEnPanne:
        return None
    return lire_intention(reponse, catalogue, formes)


def vers_empreinte(i: Intention, sensibles) -> Empreinte:
    if isinstance(sensibles, Mapping):
        sens = {c.upper() for cs in sensibles.values() for c in cs}
    else:
        sens = {c.upper() for c in sensibles}
    return Empreinte(True, frozenset(), i.colonnes, frozenset(i.colonnes & sens), i.forme, False)
