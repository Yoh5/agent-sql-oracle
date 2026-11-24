"""L'empreinte d'un SQL : ce qu'il touche et ce qu'il fait sortir, lu par sqlglot, jamais exécuté.

On ne cherche pas des mots dans le texte (un alias, une sous-requête ou un commentaire
suffiraient à tromper une recherche de « salary ») : on lit l'arbre de la requête.

Ce qui « sort », c'est ce que l'utilisateur reçoit :
- les colonnes de la liste SELECT la plus extérieure, y compris celles d'une sous-requête
  scalaire placée dans cette liste (sa valeur part directement à l'utilisateur) ;
- un nom venu d'une table dérivée ou d'une CTE est ramené à ses colonnes d'origine
  (`salary AS s` puis `SELECT s` sort SALARY) ;
- un UNION / INTERSECT / MINUS sort l'union de ses branches.
Une colonne seulement utilisée dans un filtre ou dans une sous-requête du WHERE ne sort pas.

`sensibles` est soit un ensemble (valable pour toutes les tables), soit un dictionnaire
table → colonnes (lu dans le banc YAML) : un `SELECT *` n'expose alors que les colonnes
sensibles des tables réellement présentes.

Un SQL que sqlglot ne sait pas lire (PL/SQL, plusieurs instructions) donne une empreinte
`valide=False` et jamais une exception : la sentinelle le signale, elle ne plante pas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Union

import sqlglot
from sqlglot import exp

FORMES = ("compte", "somme", "moyenne", "minimum", "maximum", "groupe", "liste")
#: Ce que l'empreinte d'un SQL peut dire en plus de ce qu'on demande au modèle d'intention.
FORMES_EMPREINTE = FORMES + ("calcul",)

_AGREGATS = {exp.Count: "compte", exp.Sum: "somme", exp.Avg: "moyenne",
             exp.Min: "minimum", exp.Max: "maximum"}
_CLASSES_AGREGAT = tuple(_AGREGATS)

Sensibles = Union[Mapping[str, Iterable[str]], Iterable[str]]


@dataclass(frozen=True)
class Empreinte:
    valide: bool
    tables: FrozenSet[str]
    colonnes: FrozenSet[str]
    sensibles: FrozenSet[str]
    forme: str
    etoile: bool


_VIDE: FrozenSet[str] = frozenset()


def _illisible() -> Empreinte:
    return Empreinte(False, _VIDE, _VIDE, _VIDE, "liste", False)


class _Lecteur:
    def __init__(self, sensibles: Sensibles):
        if isinstance(sensibles, Mapping):
            self.par_table: Optional[Dict[str, Set[str]]] = {
                t.upper(): {c.upper() for c in cs} for t, cs in sensibles.items()}
            self.toutes = set().union(*self.par_table.values()) if self.par_table else set()
        else:
            self.par_table = None
            self.toutes = {c.upper() for c in sensibles}
        self.ctes: Dict[str, exp.Expression] = {}

    # -- les sources d'une requête : tables de base, ou requêtes dérivées / CTE --------------
    def _sources(self, select: exp.Select):
        """(nom ou alias → requête dérivée) et l'ensemble des tables de base du FROM/JOIN."""
        derivees: Dict[str, exp.Expression] = {}
        base: Set[str] = set()
        froms = []
        # La clé est « from_ » dans les sqlglot récents, « from » dans les anciens.
        depuis = select.args.get("from_") or select.args.get("from")
        if depuis is not None:
            froms.append(depuis.this)
        froms += [j.this for j in select.args.get("joins") or []]
        for f in froms:
            if isinstance(f, exp.Subquery):
                derivees[(f.alias or "").upper()] = f.this
            elif isinstance(f, exp.Table):
                nom = f.name.upper()
                if nom in self.ctes:
                    derivees[(f.alias or f.name).upper()] = self.ctes[nom]
                else:
                    base.add(nom)
        return derivees, base

    def _sorties_derivee(self, requete: exp.Expression) -> Dict[str, Set[str]]:
        """Nom exposé → colonnes d'origine, pour une requête dérivée ou une CTE."""
        out: Dict[str, Set[str]] = {}
        for branche in self._branches(requete):
            derivees, base = self._sources(branche)
            for item in branche.expressions:
                nom = (item.alias_or_name or "").upper()
                out.setdefault(nom, set()).update(self._colonnes_item(item, derivees))
                if self._est_etoile(item):
                    out.setdefault("*", set()).update(self._etoile_sensibles(derivees, base))
        return out

    def _resoudre(self, col: exp.Column, derivees: Dict[str, exp.Expression]) -> Set[str]:
        nom = col.name.upper()
        cibles = [derivees[col.table.upper()]] if col.table and col.table.upper() in derivees \
            else list(derivees.values())
        for requete in cibles:
            sorties = self._sorties_derivee(requete)
            if nom in sorties:
                return sorties[nom]
        return {nom}

    def _colonnes_item(self, item: exp.Expression, derivees: Dict[str, exp.Expression]) -> Set[str]:
        """Ce qu'un item du SELECT rend : ses colonnes, plus la sortie de ses sous-requêtes scalaires."""
        cols: Set[str] = set()
        for col in item.find_all(exp.Column):
            if not isinstance(col.this, exp.Star) and self._dans_sous_requete(col, item) is None:
                cols |= self._resoudre(col, derivees)
        for sous in item.find_all(exp.Subquery):
            if self._dans_sous_requete(sous, item) is None:   # la plus extérieure seulement
                cols |= self._lire(sous.this).colonnes
        return cols

    @staticmethod
    def _dans_sous_requete(noeud: exp.Expression, item: exp.Expression) -> Optional[exp.Expression]:
        """La première sous-requête entre `noeud` (exclu) et `item`, ou None."""
        n = noeud.parent
        while n is not None and n is not item:
            if isinstance(n, exp.Subquery):
                return n
            n = n.parent
        return None

    @staticmethod
    def _est_etoile(item: exp.Expression) -> bool:
        return isinstance(item, exp.Star) or (isinstance(item, exp.Column) and isinstance(item.this, exp.Star))

    def _etoile_sensibles(self, derivees: Dict[str, exp.Expression], base: Set[str]) -> Set[str]:
        if self.par_table is None:
            exposees = set(self.toutes) if base else set()
        else:
            exposees = {c for t in base for c in self.par_table.get(t, set())}
        for requete in derivees.values():
            for cs in self._sorties_derivee(requete).values():
                exposees |= cs
        return exposees

    @staticmethod
    def _forme_item(item: exp.Expression) -> Optional[str]:
        """La forme d'un item agrégé : la première fonction d'agrégat rencontrée, à condition
        qu'aucune colonne ne soit hors d'un agrégat (ROUND(AVG(x),2) → moyenne). Plusieurs agrégats
        dans un même item (MAX(x) - MIN(x)) : « calcul » — l'empreinte ne prétend plus que c'est un
        maximum (24/11 : la réécriture rendait MAX seul pour un écart)."""
        noeud = item.this if isinstance(item, exp.Alias) else item
        agregats = [n for n in noeud.walk() if isinstance(n, _CLASSES_AGREGAT)
                    and n.find_ancestor(*_CLASSES_AGREGAT) is None]
        if not agregats:
            return None
        premiere = agregats[0]
        for col in noeud.find_all(exp.Column):
            if col.find_ancestor(*_CLASSES_AGREGAT) is None:
                return None
        return "calcul" if len(agregats) > 1 else _AGREGATS[type(premiere)]

    @staticmethod
    def _branches(requete: exp.Expression) -> List[exp.Select]:
        if isinstance(requete, exp.Select):
            return [requete]
        if isinstance(requete, exp.SetOperation):
            return _Lecteur._branches(requete.left) + _Lecteur._branches(requete.right)
        if isinstance(requete, exp.Subquery):
            return _Lecteur._branches(requete.this)
        return []

    def _lire(self, requete: exp.Expression) -> Empreinte:
        branches = self._branches(requete)
        if not branches:
            return _illisible()
        colonnes: Set[str] = set()
        sensibles: Set[str] = set()
        etoile = False
        formes = []
        for select in branches:
            derivees, _ = self._sources(select)
            items = list(select.expressions)
            for item in items:
                colonnes |= self._colonnes_item(item, derivees)
            if any(self._est_etoile(i) for i in items):
                etoile = True
                sensibles |= self._etoile_sensibles(*self._sources(select))
            if select.args.get("group"):
                formes.append("groupe")
            else:
                fs = [self._forme_item(i) for i in items]
                formes.append(fs[0] if fs and all(fs) and len(set(fs)) == 1 else "liste")
        forme = formes[0] if len(set(formes)) == 1 else "liste"
        sensibles |= colonnes & self.toutes
        return Empreinte(True, _VIDE, frozenset(colonnes), frozenset(sensibles), forme or "liste", etoile)


def empreinte(sql: str, sensibles: Sensibles) -> Empreinte:
    try:
        arbres = [a for a in sqlglot.parse(sql, read="oracle") if a is not None]
    except Exception:  # noqa: BLE001 — toute erreur de lecture = SQL illisible
        return _illisible()
    if len(arbres) != 1:
        return _illisible()
    arbre = arbres[0]
    lecteur = _Lecteur(sensibles)
    with_ = arbre.args.get("with_") or arbre.args.get("with")   # « with_ » dans les sqlglot récents
    if with_ is not None:
        lecteur.ctes = {c.alias.upper(): c.this for c in with_.expressions}
    e = lecteur._lire(arbre)
    if not e.valide:
        return e
    noms_cte = set(lecteur.ctes)
    tables = frozenset(t.name.upper() for t in arbre.find_all(exp.Table) if t.name.upper() not in noms_cte)
    return Empreinte(True, tables, e.colonnes, e.sensibles, e.forme, e.etoile)
