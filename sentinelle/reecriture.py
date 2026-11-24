"""La réécriture minimale : répondre à la question, et rien de plus.

Plutôt que refuser une requête qui rend plus que demandé, on garde ce que l'agent a écrit
pour SÉLECTIONNER les lignes (FROM, jointures, WHERE — donc ses droits) et on remplace
seulement ce qui SORT par ce que l'intention demande :
- compte → COUNT(*) ; somme / moyenne / minimum / maximum → la fonction sur LA colonne demandée ;
- liste → les colonnes demandées, et elles seules.
Tout cas douteux rend None (GROUP BY, UNION, SQL illisible, liste sans colonne, plusieurs
colonnes pour un agrégat, compte qui nomme une colonne, calcul sur plusieurs agrégats) : l'action devient alors « enquêter », jamais une réécriture devinée.
"""
from __future__ import annotations

from typing import Optional

import sqlglot
from sqlglot import exp

from sentinelle.empreinte import Empreinte

_FONCTIONS = {"somme": exp.Sum, "moyenne": exp.Avg, "minimum": exp.Min, "maximum": exp.Max}


def reecrire(sql: str, intention: Empreinte, sensibles) -> Optional[str]:
    try:
        arbres = [a for a in sqlglot.parse(sql, read="oracle") if a is not None]
    except Exception:  # noqa: BLE001
        return None
    if len(arbres) != 1 or not isinstance(arbres[0], exp.Select):
        return None
    select = arbres[0]
    if select.args.get("group"):
        return None
    cols = sorted(c.lower() for c in intention.colonnes)
    if intention.forme == "compte":
        # Un compte qui nomme une colonne est ambigu : COUNT(*), COUNT(col) ou COUNT(DISTINCT col) ?
        # (24/11, exécuté sur Oracle : « managers différents » réécrit en COUNT(*) rendait un faux chiffre.)
        if cols:
            return None
        sortie = [exp.Count(this=exp.Star())]
    elif intention.forme in _FONCTIONS:
        if len(cols) != 1:
            return None
        sortie = [_FONCTIONS[intention.forme](this=exp.column(cols[0]))]
    elif intention.forme == "liste":
        if not cols:
            return None
        sortie = [exp.column(c) for c in cols]
    else:
        return None
    m = select.copy()
    m.set("expressions", sortie)
    if intention.forme != "liste":
        m.set("order", None)   # un ORDER BY sur un agrégat global n'a plus de sens
    return m.sql(dialect="oracle")
