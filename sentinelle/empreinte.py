"""L'empreinte d'un SQL : ce qu'il touche et ce qu'il fait sortir, lu par sqlglot, jamais exécuté.

On ne cherche pas des mots dans le texte (un alias, une sous-requête ou un commentaire
suffiraient à tromper une recherche de « salary ») : on lit l'arbre de la requête.
Seule la liste SELECT la plus extérieure compte comme « ce qui sort » ; une colonne
utilisée dans un filtre ou une sous-requête n'est pas rendue à l'utilisateur.

Un SQL que sqlglot ne sait pas lire (PL/SQL, plusieurs instructions) donne une empreinte
`valide=False` et jamais une exception : la sentinelle le signale, elle ne plante pas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable

import sqlglot
from sqlglot import exp

FORMES = ("compte", "somme", "moyenne", "minimum", "maximum", "groupe", "liste")

_AGREGATS = {exp.Count: "compte", exp.Sum: "somme", exp.Avg: "moyenne",
             exp.Min: "minimum", exp.Max: "maximum"}


@dataclass(frozen=True)
class Empreinte:
    valide: bool
    tables: FrozenSet[str]
    colonnes: FrozenSet[str]
    sensibles: FrozenSet[str]
    forme: str
    etoile: bool


_VIDE = frozenset()


def _illisible() -> Empreinte:
    return Empreinte(False, _VIDE, _VIDE, _VIDE, "liste", False)


def _fonction(item: exp.Expression):
    """La fonction d'agrégat d'un item du SELECT (alias retiré), ou None."""
    noeud = item.this if isinstance(item, exp.Alias) else item
    for classe, forme in _AGREGATS.items():
        if isinstance(noeud, classe):
            return forme
    return None


def empreinte(sql: str, sensibles: Iterable[str]) -> Empreinte:
    sens = frozenset(s.upper() for s in sensibles)
    try:
        arbres = [a for a in sqlglot.parse(sql, read="oracle") if a is not None]
    except Exception:  # noqa: BLE001 — toute erreur de lecture = SQL illisible
        return _illisible()
    if len(arbres) != 1:
        return _illisible()
    arbre = arbres[0]
    select = arbre if isinstance(arbre, exp.Select) else arbre.find(exp.Select)
    if select is None:
        return _illisible()

    tables = frozenset(t.name.upper() for t in arbre.find_all(exp.Table))
    items = list(select.expressions)
    etoile = any(isinstance(i, exp.Star) or (isinstance(i, exp.Column) and isinstance(i.this, exp.Star))
                 for i in items)
    colonnes = set()
    for item in items:
        for col in item.find_all(exp.Column):
            # Une colonne d'une sous-requête placée dans le SELECT n'est pas rendue telle quelle.
            if col.find_ancestor(exp.Select) is select and not isinstance(col.this, exp.Star):
                colonnes.add(col.name.upper())
    colonnes = frozenset(colonnes)

    if select.args.get("group"):
        forme = "groupe"
    else:
        fonctions = [_fonction(i) for i in items]
        forme = (fonctions[0] if fonctions and all(fonctions) else None) or "liste"

    exposees = (colonnes | sens) if etoile else colonnes
    return Empreinte(True, tables, colonnes, frozenset(exposees & sens), forme, etoile)
