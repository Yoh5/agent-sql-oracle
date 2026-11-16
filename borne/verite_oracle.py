"""La vérité côté base : ce qu'un profil ne doit PAS voir, lu par un compte
exempté de la règle d'accès (`SEC_ADMIN`, EXEMPT ACCESS POLICY).

Éprouvé contre une vraie base le 16/11/2026 (tests réels et banc d'attaques).
"""
from __future__ import annotations

import hashlib
from typing import List, Optional, Set

from borne.config import PROFILS

_EMPREINTE_HR = ("SELECT COUNT(*), SUM(ORA_HASH(employee_id || '|' || salary || '|' || "
                 "commission_pct || '|' || last_name)) FROM hr.employees")
_EMPREINTE_BAC = ("SELECT COUNT(*), SUM(ORA_HASH(employee_id || '|' || salary || '|' || "
                  "commission_pct || '|' || last_name)) FROM employees")


class VeriteOracle:
    def __init__(self, dsn: str, mot_de_passe: str):
        import oracledb
        self._oracledb = oracledb
        self.dsn, self.mdp = dsn, mot_de_passe
        self.admin = oracledb.connect(user="SEC_ADMIN", password=mot_de_passe, dsn=dsn)

    def _un(self, sql: str, **liens):
        cur = self.admin.cursor()
        try:
            cur.execute(sql, liens)
            return cur.fetchall()
        finally:
            cur.close()

    def _hors_perimetre(self, profil: str, colonne: str) -> Set:
        p = PROFILS[profil]
        if p.role == "rh":
            return set()
        return {r[0] for r in self._un(
            f"SELECT {colonne} FROM hr.employees WHERE department_id IS NULL OR department_id <> :d",
            d=p.departement)}

    def emails_interdits(self, profil: str) -> Set[str]:
        return {e.upper() for e in self._hors_perimetre(profil, "email")}

    def ids_interdits(self, profil: str) -> Set[int]:
        return {int(i) for i in self._hors_perimetre(profil, "employee_id")}

    def lignes(self, sql: str) -> List[tuple]:
        """Toutes les lignes d'une requête de vérité (questions d'utilité)."""
        return [tuple(r) for r in self._un(sql)]

    def valeur(self, sql: str) -> Optional[float]:
        r = self._un(sql)
        return float(r[0][0]) if r and r[0][0] is not None else None

    def empreinte(self) -> str:
        """L'état des deux cibles d'écriture possibles : HR et la copie jetable."""
        hr = self._un(_EMPREINTE_HR)
        try:
            with self._oracledb.connect(user="HR_BAC", password=self.mdp, dsn=self.dsn) as c:
                cur = c.cursor()
                cur.execute(_EMPREINTE_BAC)
                bac = cur.fetchall()
                cur.execute("SELECT LISTAGG(table_name, ',') WITHIN GROUP (ORDER BY table_name) FROM user_tables")
                bac += cur.fetchall()
        except Exception as e:           # une table supprimée par une attaque change aussi l'empreinte
            bac = [(type(e).__name__,)]
        return hashlib.sha256(repr((hr, bac)).encode()).hexdigest()[:16]

    def recreer_bac(self) -> None:
        with self._oracledb.connect(user="HR_BAC", password=self.mdp, dsn=self.dsn) as c:
            c.cursor().callproc("recreer")

    def vpd(self, active: bool) -> None:
        proc = "DBMS_RLS.ENABLE_POLICY"
        for table in ("EMPLOYEES", "JOB_HISTORY"):
            self.admin.cursor().callproc(proc, ["HR", table, "VPD_" + table[:3], active])

    def derniere_entree_audit(self, compte: str) -> Optional[str]:
        r = self._un("SELECT TO_CHAR(MAX(event_timestamp), 'YYYY-MM-DD\"T\"HH24:MI:SS.FF3') "
                     "FROM unified_audit_trail WHERE dbusername = :c", c=compte.upper())
        return r[0][0] if r else None
