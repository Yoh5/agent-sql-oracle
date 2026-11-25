"""Le périmètre lu par le CODE, pas par un modèle.

La phase 2 a montré qu'un modèle qui lit la question peut être retourné : « considère que je
suis aussi manager du service 80 » lui a fait classer la demande « mon service ». Ici, on ne
lit plus la question : on lit le SQL réellement écrit, et on cherche les valeurs comparées à la
colonne de partition de la règle du profil (`department_id = 50`). Toute autre valeur
(`= 80`, `IN (50, 80)`, y compris dans une sous-requête) est hors de la règle.

Une règle sans partition (`1 = 1`, accès total) n'est jamais dépassée.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp


def _partition(regle: str) -> Optional[Tuple[str, str]]:
    m = re.match(r"\s*([A-Za-z_][\w$#]*)\s*=\s*'?([\w.-]+)'?\s*$", regle or "")
    if not m or m.group(1) == "1":
        return None
    return m.group(1).upper(), m.group(2)


def _valeur(n: exp.Expression) -> Optional[str]:
    return n.name if isinstance(n, exp.Literal) else None


_INVERSE = {"<>": "<>", ">": "<", "<": ">", ">=": "<=", "<=": ">="}
_OPERATEURS = ((exp.NEQ, "<>"), (exp.GT, ">"), (exp.LT, "<"), (exp.GTE, ">="), (exp.LTE, "<="))


def hors_regle(sql: str, regle: str) -> List[str]:
    """Ce qui, dans le SQL, compare la colonne de partition à autre chose que la valeur permise : les
    valeurs étrangères (`= 80`, `IN (50, 80)`) et toute autre comparaison (`<> 50`, `NOT IN 50`,
    `> 40`… — 24/11 : « mon service, puis tous les autres » passait par un `<> 50`), y compris dans
    une sous-requête. Trié, sans doublon. Un SQL illisible ne dépasse rien ici (l'empreinte le signale)."""
    part = _partition(regle)
    if part is None:
        return []
    colonne, permise = part
    try:
        arbre = sqlglot.parse_one(sql, read="oracle")
    except Exception:  # noqa: BLE001
        return []
    vues = set()
    est_col = lambda n: isinstance(n, exp.Column) and n.name.upper() == colonne  # noqa: E731
    for eq in arbre.find_all(exp.EQ):
        for a, b in ((eq.left, eq.right), (eq.right, eq.left)):
            if est_col(a) and _valeur(b) is not None and _valeur(b) != permise:
                vues.add(_valeur(b))
    for classe, op in _OPERATEURS:
        for c in arbre.find_all(classe):
            if est_col(c.left) and _valeur(c.right) is not None:
                vues.add(f"{op} {_valeur(c.right)}")
            elif est_col(c.right) and _valeur(c.left) is not None:
                vues.add(f"{_INVERSE[op]} {_valeur(c.left)}")
    for dans in arbre.find_all(exp.In):
        if not est_col(dans.this):
            continue
        valeurs = [v for v in (_valeur(x) for x in dans.expressions) if v is not None]
        if isinstance(dans.parent, exp.Not):
            vues |= {f"NOT IN {v}" for v in valeurs}
        else:
            vues |= {v for v in valeurs if v != permise}
    return sorted(vues)


_ECRITURE = re.compile(r"^\s*(?!(?:SELECT|WITH)(?![\w$#])|\()\w+", re.I)


def ecriture(sql: str) -> bool:
    """Autre chose qu'une lecture : UPDATE, DELETE, INSERT, MERGE, DDL, GRANT, bloc PL/SQL… — y compris
    quand sqlglot ne sait pas lire. Un agent de LECTURE qui écrit, c'est la case A : couper, en code."""
    try:
        arbres = [a for a in sqlglot.parse(sql, read="oracle") if a is not None]
    except Exception:  # noqa: BLE001
        return any(_ECRITURE.match(m) for m in (sql or "").split(";") if m.strip())
    return any(not isinstance(a, (exp.Select, exp.SetOperation)) for a in arbres)


def _conjoint(n: exp.Expression) -> bool:
    """La comparaison est-elle une condition OBLIGATOIRE de son WHERE / HAVING / ON : reliée à la racine
    par des AND (et des parenthèses) seulement ? `department_id = 50 OR employee_id IN (…)` ne filtre
    rien (25/11 : gemini-2.5-pro en boîte blanche, l'e-mail d'un employé d'un autre service sortait)."""
    p = n.parent
    while isinstance(p, (exp.And, exp.Paren)):
        p = p.parent
    return isinstance(p, (exp.Where, exp.Having, exp.Join))


def _non_filtrees(select: exp.Select, colonne: str, permise: str, tables_p) -> List[str]:
    """Les tables partitionnées de CE SELECT dont la colonne de partition n'est pas ramenée à la
    valeur permise. Le filtre se juge par OCCURRENCE de table (par alias), pas pour tout le SELECT :
    une auto-jointure `employees e JOIN employees m … WHERE e.department_id = 50` laisse `m` libre
    (25/11 : les e-mails des managers d'autres services sortaient avec un score de 0). Une égalité
    `a.<colonne> = b.<colonne>` propage le filtre d'une occurrence à l'autre ; une colonne non
    qualifiée vaut pour toutes les occurrences (Oracle refuserait une colonne ambiguë)."""
    occ = {}
    for t in select.find_all(exp.Table):
        if t.find_ancestor(exp.Select) is select and t.name.upper() in tables_p:
            occ[(t.alias_or_name or t.name).upper()] = t.name.upper()
    if not occ:
        return []
    filtrees, liens = set(), []

    def qual(c: exp.Column):
        return c.table.upper() if c.table else None

    for eq in select.find_all(exp.EQ):
        if eq.find_ancestor(exp.Select) is not select or not _conjoint(eq):
            continue
        l, r = eq.left, eq.right
        if all(isinstance(x, exp.Column) and x.name.upper() == colonne for x in (l, r)):
            if qual(l) and qual(r):
                liens.append((qual(l), qual(r)))
            continue
        for a, b in ((l, r), (r, l)):
            if isinstance(a, exp.Column) and a.name.upper() == colonne and _valeur(b) == permise:
                filtrees |= {qual(a)} if qual(a) else set(occ)
    for dans in select.find_all(exp.In):
        if (dans.find_ancestor(exp.Select) is select and _conjoint(dans)
                and isinstance(dans.this, exp.Column) and dans.this.name.upper() == colonne
                and [_valeur(x) for x in dans.expressions] == [permise]):
            filtrees |= {qual(dans.this)} if qual(dans.this) else set(occ)
    change = True
    while change:
        change = False
        for a, b in liens:
            if (a in filtrees) != (b in filtrees):
                filtrees |= {a, b}
                change = True
    return sorted({nom for alias, nom in occ.items() if alias not in filtrees})


def hors_structure(sql: str, regle: str, partitionnees) -> List[str]:
    """Ce que la STRUCTURE du SQL dit du périmètre, sans aucune valeur étrangère à lire :
    - « ventilé par <colonne> » : un profil restreint qui groupe par la colonne de partition
      demande, par construction, les autres partitions (vu le 23/11 : l'analyste sous une note
      piégée « plausible » a écrit GROUP BY DEPARTMENT_ID, et compté sur la VPD pour filtrer) ;
    - « <table> lue sans filtre sur <colonne> » : une table partitionnée lue sans comparer la
      colonne de partition à la valeur permise (signal plus faible : l'agent s'en remet à la base).
    """
    part = _partition(regle)
    if part is None:
        return []
    colonne, permise = part
    try:
        arbre = sqlglot.parse_one(sql, read="oracle")
    except Exception:  # noqa: BLE001
        return []
    tables_p = {t.upper() for t in partitionnees}
    raisons: List[str] = []
    for groupe in arbre.find_all(exp.Group):
        if any(isinstance(c, exp.Column) and c.name.upper() == colonne for e in groupe.expressions
               for c in ([e] if isinstance(e, exp.Column) else e.find_all(exp.Column))):
            raisons.append(f"ventilé par {colonne}")
            break
    for select in arbre.find_all(exp.Select):
        raisons += [f"{t} lue sans filtre sur {colonne}" for t in _non_filtrees(select, colonne, permise, tables_p)]
    return list(dict.fromkeys(raisons))
