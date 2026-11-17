"""Phase 3 : poser une politique d'accès CANDIDATE sur le terrain d'essai, jamais sur HR.

- `controler(source)` : contrôle statique du code (écrit par un modèle, ou à la main).
  Défense en profondeur : ce qui protège vraiment, c'est que la fonction est créée dans
  ESSAI_POL, qui ne peut que lire sa table de profils (sql/04_essai.sql).
- `TerrainEssai` : installe la fonction (connecté en ESSAI_POL), pose la politique sur les
  tables de HR_ESSAI (connecté en SEC_ADMIN), lit ce qu'un compte de test voit, retire.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Set

#: Les comptes de test (sql/04_essai.sql). ESSAI_X n'a pas de profil, exprès.
COMPTES_ESSAI = ("ESSAI_M50", "ESSAI_M80", "ESSAI_RH", "ESSAI_X")

#: Ce qui identifie une ligne, par table protégée : le juge compare des ensembles de clés.
CLES = {
    "EMPLOYEES": "employee_id",
    "JOB_HISTORY": "employee_id || '|' || TO_CHAR(start_date, 'YYYY-MM-DD')",
}

_INTERDITS = [
    (r"\bEXECUTE\s+IMMEDIATE\b", "SQL dynamique"),
    (r"\bDBMS_\w+", "paquet système DBMS_"),
    (r"\bUTL_\w+", "paquet système UTL_"),
    (r"\bSYS\s*\.", "objet du schéma SYS"),
    (r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b", "écriture de données"),
    (r"\b(COMMIT|ROLLBACK|SAVEPOINT)\b", "contrôle de transaction"),
    (r"\bAUTONOMOUS_TRANSACTION\b", "transaction autonome"),
    (r"\b(DROP|ALTER|GRANT|REVOKE)\b", "DDL ou droits"),
    (r"\bOPEN\s+\w+\s+FOR\b", "curseur dynamique"),
    (r"\bDATABASE\s+LINK\b|@\w+", "lien vers une autre base"),
]

_ENTETE = re.compile(
    r"^\s*CREATE\s+OR\s+REPLACE\s+FUNCTION\s+(?:ESSAI_POL\s*\.\s*)?(\w+)\s*"
    r"\(\s*\w+\s+VARCHAR2\s*,\s*\w+\s+VARCHAR2\s*\)\s*RETURN\s+VARCHAR2\s+(?:AS|IS)\b",
    re.I)


class ControleRefuse(ValueError):
    """La source n'est pas une fonction de politique acceptable."""


class NeCompilePas(ControleRefuse):
    """Acceptée par le contrôle, mais Oracle ne la compile pas. Ce n'est pas un refus de
    SÉCURITÉ : les confondre ferait passer une faute de syntaxe pour du code dangereux bloqué."""


def _sans_commentaires(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"--[^\n]*", " ", source)


def controler(source: str) -> str:
    """Rend le nom (en majuscules) de l'unique fonction de politique, ou lève ControleRefuse."""
    texte = _sans_commentaires(source or "").strip().rstrip("/").strip()
    m = _ENTETE.match(texte)
    if not m:
        raise ControleRefuse("attendu : une seule CREATE OR REPLACE FUNCTION nom(p VARCHAR2, "
                             "p VARCHAR2) RETURN VARCHAR2")
    if len(re.findall(r"\bCREATE\b", texte, re.I)) != 1:
        raise ControleRefuse("une seule unité est permise")
    for motif, raison in _INTERDITS:
        if re.search(motif, texte, re.I):
            raise ControleRefuse(f"refusé : {raison}")
    return m.group(1).upper()


class TerrainEssai:
    """Le terrain d'essai de la phase 3 (copie HR_ESSAI, comptes ESSAI_*)."""

    def __init__(self, dsn: str, mot_de_passe: str, tables: Sequence[str] = ("EMPLOYEES", "JOB_HISTORY")):
        import oracledb
        self._oracledb = oracledb
        self.dsn, self.mdp, self.tables = dsn, mot_de_passe, tuple(t.upper() for t in tables)

    def _connecter(self, compte: str):
        return self._oracledb.connect(user=compte, password=self.mdp, dsn=self.dsn)

    def retirer(self) -> None:
        """Retire toute politique posée sur la copie (et seulement sur la copie)."""
        with self._connecter("SEC_ADMIN") as c:
            cur = c.cursor()
            for objet, nom in cur.execute(
                    "SELECT object_name, policy_name FROM all_policies WHERE object_owner = 'HR_ESSAI'"
            ).fetchall():
                cur.callproc("DBMS_RLS.DROP_POLICY", ["HR_ESSAI", objet, nom])

    def installer(self, source: str) -> str:
        """Contrôle, crée la fonction dans ESSAI_POL, pose la politique sur la copie.
        Rend le nom de la fonction. Lève ControleRefuse si le code est refusé ou ne compile pas."""
        nom = controler(source)
        texte = _sans_commentaires(source).strip().rstrip("/").strip()
        with self._connecter("ESSAI_POL") as c:
            cur = c.cursor()
            cur.execute(texte)
            erreurs = cur.execute(
                "SELECT line, text FROM user_errors WHERE name = :n ORDER BY sequence", n=nom).fetchall()
            if erreurs:
                raise NeCompilePas("ne compile pas : " + " ; ".join(f"l.{l} {t.strip()}" for l, t in erreurs[:3]))
        self.retirer()
        with self._connecter("SEC_ADMIN") as c:
            cur = c.cursor()
            for table in self.tables:
                cur.callproc("DBMS_RLS.ADD_POLICY", [], {
                    "object_schema": "HR_ESSAI", "object_name": table,
                    "policy_name": ("ESSAI_" + table)[:30], "function_schema": "ESSAI_POL",
                    "policy_function": nom, "statement_types": "SELECT"})
        return nom

    def visibles(self, compte: str, table: str) -> Optional[Set[str]]:
        """Les clés qu'un compte de test voit dans une table. None : la politique a ÉCHOUÉ à
        l'exécution (ORA-28112 & co) — Oracle refuse alors la requête entière."""
        with self._connecter(compte) as c:
            try:
                rows = c.cursor().execute(f"SELECT {CLES[table]} FROM {table}").fetchall()
            except self._oracledb.DatabaseError:
                return None
        return {str(r[0]) for r in rows}

    def photographier(self) -> Dict[str, Dict[str, Optional[Set[str]]]]:
        """Ce que chaque compte de test voit dans chaque table protégée."""
        return {c: {t: self.visibles(c, t) for t in self.tables} for c in COMPTES_ESSAI}


def lister_comptes() -> List[str]:
    return list(COMPTES_ESSAI)
