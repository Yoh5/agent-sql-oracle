"""L'exécuteur réel : du SQL envoyé à Oracle sous le compte d'un profil.

Il ne filtre rien et ne juge rien : la sécurité est dans la base. Il se
contente de trois précautions qui protègent l'APPLICATION, pas les données :

- une seule instruction par appel (`python-oracledb` n'en exécute qu'une ;
  un texte qui en contient plusieurs est refusé avant envoi plutôt que tronqué) ;
- un plafond de lignes rapatriées et un délai d'appel, pour qu'un produit
  cartésien ne fasse pas tomber la page ;
- un `rollback` après chaque appel : rien de ce qu'un compte aurait pu
  modifier ne survit au tour (la copie jetable mise à part, voir le banc).
"""
from __future__ import annotations

import re
from typing import Callable, Dict, Optional

from borne.agent import Resultat
from borne.classer import classer

MAX_LIGNES = 200
DELAI_MS = 10_000
_ORA = re.compile(r"\b(ORA-\d{5})\b")

#: Le schéma qu'un compte voit : ses tables, ou celles que lui ouvrent ses synonymes.
_SQL_SCHEMA = """
SELECT s.synonym_name AS nom, c.column_name, c.data_type
  FROM user_synonyms s
  JOIN all_tab_columns c ON c.owner = s.table_owner AND c.table_name = s.table_name
UNION ALL
SELECT c.table_name, c.column_name, c.data_type FROM user_tab_columns c
 ORDER BY 1, 2
"""


def code_ora(message: str) -> Optional[str]:
    m = _ORA.search(message or "")
    return m.group(1) if m else None


class ExecuteurOracle:
    def __init__(self, dsn: str, mots_de_passe: Dict[str, str], max_lignes: int = MAX_LIGNES,
                 delai_ms: int = DELAI_MS, connecteur: Optional[Callable] = None,
                 lire_audit: Optional[Callable[[str], Optional[str]]] = None):
        self.dsn, self.mots_de_passe = dsn, dict(mots_de_passe)
        self.max_lignes, self.delai_ms = max_lignes, delai_ms
        self._connecteur = connecteur or self._connecter
        self._lire_audit = lire_audit or (lambda compte: None)
        self._connexions: Dict[str, object] = {}

    def _connecter(self, compte: str):
        import oracledb
        return oracledb.connect(user=compte, password=self.mots_de_passe[compte], dsn=self.dsn)

    def _connexion(self, compte: str):
        if compte not in self.mots_de_passe:
            raise KeyError(f"compte non prévu pour l'agent : {compte}")
        if compte not in self._connexions:
            c = self._connecteur(compte)
            c.call_timeout = self.delai_ms
            self._connexions[compte] = c
        return self._connexions[compte]

    def schema(self, compte: str) -> str:
        cur = self._connexion(compte).cursor()
        try:
            cur.execute(_SQL_SCHEMA)
            tables: Dict[str, list] = {}
            for nom, col, typ in cur.fetchall():
                tables.setdefault(nom, []).append(f"{col} {typ}")
            return "\n".join(f"{t}({', '.join(c)})" for t, c in tables.items())
        finally:
            cur.close()

    def executer(self, compte: str, sql: str) -> Resultat:
        conn = self._connexion(compte)
        texte = (sql or "").strip()
        if classer(texte) == "multiple":
            return Resultat([], [], None, "plusieurs instructions refusées : une seule par question", None)
        texte = texte.rstrip(";").strip() if classer(texte) == "lecture" else texte
        cur = conn.cursor()
        try:
            cur.execute(texte)
            colonnes = [d[0] for d in (cur.description or [])]
            lignes = [tuple(l) for l in cur.fetchmany(self.max_lignes)] if colonnes else []
            return Resultat(lignes, colonnes, None, None, self._lire_audit(compte))
        except Exception as e:
            message = str(e).split("\nHelp:")[0].strip()
            return Resultat([], [], code_ora(message), message, self._lire_audit(compte))
        finally:
            cur.close()
            try:
                conn.rollback()
            except Exception:
                pass
