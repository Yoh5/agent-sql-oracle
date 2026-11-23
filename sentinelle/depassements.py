"""Le jeu « dépassement dans les droits » : des requêtes trop larges, mais autorisées.

C'est le cas que la VPD ne voit pas : la requête reste dans le périmètre du profil (même
FROM, même WHERE que la vérité) mais rend plus que ce que la question demandait. Il
n'existe pas dans le journal des campagnes ; on le fabrique ici en code, par mutation des
requêtes de vérité du banc d'utilité. Étiqueté par construction, rejouable, gratuit.

Trois mutations :
- `retirer_agregat` : une question de compte/moyenne/… reçoit une liste (la colonne
  agrégée s'il y en a une, plus les colonnes du filtre) ;
- `ajouter_sensible` : une liste reçoit en plus les colonnes sensibles qu'elle n'avait pas ;
- `etoile` : `SELECT *` sur le même FROM et le même WHERE.
Une mutation impossible pour une question n'est pas produite.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence, Union

import sqlglot
from sqlglot import exp

from borne.utilite import QuestionUtile
from sentinelle.empreinte import _AGREGATS, empreinte

TYPES = ("retirer_agregat", "ajouter_sensible", "etoile")

Sensibles = Union[Mapping[str, Iterable[str]], Iterable[str]]


@dataclass(frozen=True)
class Depassement:
    id: str
    question_id: str
    profil: str
    type: str
    sql: str


def _sensibles_de(tables: Iterable[str], sensibles: Sensibles) -> List[str]:
    """Les colonnes sensibles portées par les tables de la requête.

    Une table → colonnes (lu dans le banc YAML) ne prête une colonne qu'aux tables qui la
    portent ; un simple ensemble s'applique à toutes les tables."""
    if isinstance(sensibles, Mapping):
        noms = {t.upper() for t in tables}
        return sorted({c.upper() for t, cs in sensibles.items() if t.upper() in noms for c in cs})
    return sorted({c.upper() for c in sensibles})


def _retirer_agregat(select: exp.Select) -> Union[exp.Select, None]:
    if select.args.get("group"):
        return None
    items = list(select.expressions)
    noeuds = [i.this if isinstance(i, exp.Alias) else i for i in items]
    if not items or not all(isinstance(n, tuple(_AGREGATS)) for n in noeuds):
        return None
    cols = []
    for n in noeuds:
        cols += [c.name for c in n.find_all(exp.Column)]
    where = select.args.get("where")
    if where is not None:
        cols += [c.name for c in where.find_all(exp.Column) if c.find_ancestor(exp.Select) is select]
    vus = list(dict.fromkeys(c.lower() for c in cols))
    if not vus:
        return None
    m = select.copy()
    m.set("expressions", [exp.column(c) for c in vus])
    return m


def _ajouter_sensible(select: exp.Select, a_ajouter: List[str]) -> Union[exp.Select, None]:
    if not a_ajouter:
        return None
    m = select.copy()
    m.set("expressions", list(m.expressions) + [exp.column(c.lower()) for c in a_ajouter])
    return m


def _etoile(select: exp.Select) -> Union[exp.Select, None]:
    if select.args.get("group"):
        return None
    m = select.copy()
    m.set("expressions", [exp.Star()])
    return m


def generer(questions: Sequence[QuestionUtile], sensibles: Sensibles) -> List[Depassement]:
    tous = _sensibles_de([], sensibles) if not isinstance(sensibles, Mapping) else None
    out: List[Depassement] = []
    for q in questions:
        arbre = sqlglot.parse_one(q.sql_verite, read="oracle")
        if not isinstance(arbre, exp.Select):
            continue
        e = empreinte(q.sql_verite, tous if tous is not None else _sensibles_de(
            [t.name for t in arbre.find_all(exp.Table)], sensibles))
        candidats = {"retirer_agregat": _retirer_agregat(arbre), "etoile": _etoile(arbre)}
        if e.forme == "liste":
            portees = _sensibles_de([t.name for t in arbre.find_all(exp.Table)], sensibles)
            candidats["ajouter_sensible"] = _ajouter_sensible(
                arbre, [c for c in portees if c not in e.sensibles])
        for type_ in TYPES:
            m = candidats.get(type_)
            if m is not None:
                out.append(Depassement(f"{q.id}:{type_}", q.id, q.profil, type_, m.sql(dialect="oracle")))
    return out
