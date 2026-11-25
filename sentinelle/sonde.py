"""La sonde de périmètre : une ligne hors du service de l'utilisateur serait-elle touchée ?

Construite par le CODE depuis le SQL de l'agent : mêmes FROM, jointures et WHERE ; sortie, GROUP BY,
HAVING et ORDER BY retirés (une moyenne calculée sur le service 80 est une fuite : on regarde les lignes
sous-jacentes) ; un filtre « hors de la règle » ajouté sur chaque table partitionnée de la requête
extérieure. Elle ne rend qu'UN bit (`FETCH FIRST 1 ROW ONLY`).

Elle exécute un WHERE écrit sous l'influence de l'attaquant avec un compte qui voit tout : tout ce qu'on
ne sait pas lire est refusé AVANT exécution (UNION, CTE, table dérivée, fonction hors liste blanche —
une fonction PL/SQL ou réseau n'est jamais appelée). Refus → l'enquêteur passe la main à un humain.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import sqlglot
from sqlglot import exp

from sentinelle.perimetre import _non_filtrees, _partition

# Fonctions SQL usuelles, par classe sqlglot (lecture oracle). Tout le reste (dont `exp.Anonymous`,
# qui couvre les fonctions inconnues et les appels pointés `paquet.fonction`) est refusé.
FONCTIONS_PERMISES = frozenset({
    "Abs", "AddMonths", "Avg", "Case", "Cast", "Ceil", "Coalesce", "Concat", "Count", "CurrentDate",
    "CurrentTimestamp", "DateTrunc", "DecodeCase", "Extract", "Floor", "Greatest", "GroupConcat", "If",
    "Initcap", "Least", "Length", "Lower", "Max", "Median", "Min", "MonthsBetween", "Nullif", "Pad",
    "Rank", "Replace", "Round", "RowNumber", "Stddev", "StrPosition", "StrToDate", "Substring", "Sum",
    "ToChar", "ToNumber", "Trim", "Upper",
    # des OPÉRATEURS que sqlglot range parmi les fonctions (vu le 24/11 : `AND` refusé, John Russell
    # envoyé à un humain au lieu d'être coupé) :
    "And", "Or", "Exists", "Pow", "RegexpLike",
})
_ANONYMES_PERMISES = frozenset({"TRUNC"})


def _fonction_refusee(arbre: exp.Expression) -> bool:
    for n in arbre.walk():
        if isinstance(n, exp.Anonymous):
            if str(n.name).upper() not in _ANONYMES_PERMISES or isinstance(n.parent, exp.Dot):
                return True
        elif isinstance(n, exp.Func) and type(n).__name__ not in FONCTIONS_PERMISES:
            return True
    return False


def _arg(n: exp.Expression, *cles):
    for c in cles:
        v = n.args.get(c)
        if v is not None:
            return v
    return None


def construire_sonde(sql: str, regle: str, partitionnees: Iterable[str]) -> Tuple[Optional[str], Optional[str]]:
    part = _partition(regle)
    if part is None:
        return None, "sans_partition"
    try:
        arbres = [a for a in sqlglot.parse(sql, read="oracle") if a is not None]
    except Exception:  # noqa: BLE001
        return None, "illisible"
    if len(arbres) != 1:
        return None, "illisible"
    a = arbres[0]
    if isinstance(a, exp.SetOperation):
        # UNION / INTERSECT / MINUS : chaque branche sondée ; une branche refusée refuse tout
        # (24/11 : « mon service, puis tous les autres » était un UNION ALL).
        if _arg(a, "with_", "with") is not None:
            return None, "cte"
        branches = []
        for b in _branches(a):
            s, motif = _sonde_select(b, part, partitionnees) if isinstance(b, exp.Select) else (None, "illisible")
            if motif == "aucune_table_partitionnee":
                continue
            if s is None:
                return None, motif
            branches.append(s)
        if not branches:
            return None, "aucune_table_partitionnee"
        return "SELECT 1 FROM dual WHERE " + " OR ".join(f"EXISTS ({b})" for b in branches), None
    if not isinstance(a, exp.Select):
        return None, "illisible"
    s, motif = _sonde_select(a, part, partitionnees)
    return (None, motif) if s is None else (f"{s} FETCH FIRST 1 ROWS ONLY", None)


def _branches(n: exp.Expression) -> List[exp.Expression]:
    if isinstance(n, exp.SetOperation):
        return _branches(n.this) + _branches(n.expression)
    return [n.this if isinstance(n, exp.Subquery) else n]


def _sonde_select(a: exp.Select, part: Tuple[str, str], partitionnees: Iterable[str]
                  ) -> Tuple[Optional[str], Optional[str]]:
    colonne, valeur = part
    if _arg(a, "with_", "with") is not None:
        return None, "cte"
    source = _arg(a, "from_", "from")
    jointures = a.args.get("joins") or []
    if source is None:
        return None, "illisible"
    tables: List[exp.Expression] = [source.this] + [j.this for j in jointures]
    if any(not isinstance(t, exp.Table) for t in tables):
        return None, "derivee"
    if _fonction_refusee(a):
        return None, "fonction"
    parts = {p.upper() for p in partitionnees}
    # Une sous-requête (liste SELECT, WHERE, HAVING…) qui lit une table partitionnée sans filtre sur le
    # service : la sonde ne la couvre pas — elle ne sonde que les tables du FROM. Refus → humain.
    # (25/11 : `(SELECT email FROM employees WHERE employee_id = 150)` dans la liste SELECT, libéré.)
    if any(sous is not a and _non_filtrees(sous, colonne, valeur, parts) for sous in a.find_all(exp.Select)):
        return None, "sous_requete"
    refs = [(t.alias_or_name) for t in tables if t.name.upper() in parts]
    if not refs:
        return None, "aucune_table_partitionnee"
    hors = exp.or_(*[sqlglot.parse_one(f"{r}.{colonne} <> {valeur} OR {r}.{colonne} IS NULL", read="oracle")
                     for r in refs])
    s = exp.select("1")
    s.set("from_" if "from_" in a.args else "from", source.copy())
    if jointures:
        s.set("joins", [j.copy() for j in jointures])
    where = a.args.get("where")
    condition = exp.and_(exp.paren(where.this.copy()), exp.paren(hors)) if where is not None else hors
    return s.where(condition).sql(dialect="oracle"), None


class Sonde:
    """Exécute une sonde avec le compte SENT_SONDE. Rend True (une ligne hors périmètre existe),
    False (aucune), ou None (erreur, délai dépassé, droit manquant) : l'enquêteur ne libère jamais
    sur un None."""

    def __init__(self, dsn: str, mot_de_passe: str, delai_ms: int = 2000):
        import oracledb
        self._erreur = oracledb.Error
        self.cnx = oracledb.connect(user="SENT_SONDE", password=mot_de_passe, dsn=dsn, tcp_connect_timeout=3)
        self.cnx.call_timeout = delai_ms
        with self.cnx.cursor() as c:
            c.execute("ALTER SESSION SET CURRENT_SCHEMA = HR")

    def hors_perimetre(self, sql_sonde: str) -> Optional[bool]:
        try:
            with self.cnx.cursor() as c:
                c.execute(sql_sonde)
                return c.fetchone() is not None
        except self._erreur:
            return None
