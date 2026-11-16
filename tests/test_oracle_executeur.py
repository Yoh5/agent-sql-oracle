"""L'exécuteur : la logique se teste sans base (connexion simulée), le reste avec Oracle."""
import os

import pytest

from borne.oracle import ExecuteurOracle, code_ora


class Curseur:
    def __init__(self, journal, lignes=None, erreur=None, colonnes=("N",), rowcount=0):
        self.journal, self.lignes, self.erreur = journal, lignes or [], erreur
        self.description = [(c,) for c in colonnes] if colonnes else None
        self.arraysize, self.rowcount = 100, rowcount

    def execute(self, sql, *a, **k):
        self.journal.append(sql)
        if self.erreur:
            raise self.erreur

    def fetchmany(self, n):
        return self.lignes[:n]

    def fetchall(self):
        return self.lignes

    def close(self):
        pass


class Connexion:
    def __init__(self, **kw):
        self.journal, self.kw = [], kw
        self.call_timeout = None

    def cursor(self):
        return Curseur(self.journal, **self.kw)

    def rollback(self):
        self.journal.append("ROLLBACK")

    def commit(self):
        self.journal.append("COMMIT")


def _ex(**kw):
    conn = Connexion(**kw)
    ex = ExecuteurOracle("dsn", {"MGR_50": "x", "HR_BAC": "x"}, max_lignes=3,
                         connecteur=lambda compte: conn, lire_audit=lambda compte: "audit-7")
    return ex, conn


def test_une_ecriture_compte_les_lignes_modifiees_puis_est_annulee():
    # Sur un compte de profil, on annule toujours : on ne touche jamais au vrai HR.
    # Mais on relève combien de lignes la base a laissé modifier AVANT d'annuler —
    # sinon une écriture acceptée puis annulée passait pour « sans effet ».
    ex, conn = _ex(colonnes=None, rowcount=45)
    r = ex.executer("MGR_50", "DELETE FROM employees WHERE department_id = 50")
    assert r.modifiees == 45 and conn.journal[-1] == "ROLLBACK"


def test_la_copie_jetable_garde_ses_ecritures():
    # HR_BAC est recréée avant chaque attaque : on y VALIDE, pour que l'empreinte voie
    # l'effet réel d'une écriture, même cachée dans un bloc PL/SQL (rowcount y vaut 0).
    ex, conn = _ex(colonnes=None, rowcount=0)
    ex.executer("HR_BAC", "BEGIN UPDATE employees SET commission_pct = 0.9; END;")
    assert conn.journal[-1] == "COMMIT"


def test_le_point_virgule_final_est_retire():
    ex, conn = _ex(lignes=[(1,)])
    r = ex.executer("MGR_50", "SELECT 1 FROM dual;")
    assert conn.journal == ["SELECT 1 FROM dual", "ROLLBACK"] and r.lignes == [(1,)] and r.audit_ref == "audit-7"


def test_plusieurs_instructions_ne_sont_jamais_envoyees():
    ex, conn = _ex()
    r = ex.executer("MGR_50", "SELECT 1 FROM dual; DROP TABLE employees")
    assert conn.journal == [] and "plusieurs instructions" in r.message and r.ora is None


def test_le_resultat_est_plafonne():
    ex, _ = _ex(lignes=[(i,) for i in range(50)])
    assert len(ex.executer("MGR_50", "SELECT n FROM t").lignes) == 3


def test_une_erreur_oracle_devient_un_code():
    ex, _ = _ex(erreur=Exception("ORA-01031: insufficient privileges\nHelp: https://…"))
    r = ex.executer("MGR_50", "SELECT 1 FROM dual")
    assert r.ora == "ORA-01031" and r.lignes == [] and "insufficient" in r.message


def test_code_ora():
    assert code_ora("ORA-00942: table or view does not exist") == "ORA-00942"
    assert code_ora("DPY-6005: cannot connect") is None


def test_un_compte_inconnu_est_refuse():
    ex, conn = _ex()
    with pytest.raises(KeyError):
        ex.executer("SYSTEM", "SELECT 1 FROM dual")
    assert conn.journal == []


# --------------------------------------------------------------------------- #
# Avec Oracle
# --------------------------------------------------------------------------- #
def _reel():
    mdp = os.environ.get("PERSONA_PASSWORD", "")
    return ExecuteurOracle(os.environ["ORACLE_DSN"], {c: mdp for c in ("MGR_50", "MGR_80", "RH_DIR", "HR_BAC")})


def test_reel_une_lecture(oracle_dispo):
    assert _reel().executer("MGR_50", "SELECT 1 FROM dual;").lignes == [(1,)]


def test_reel_un_produit_cartesien_reste_plafonne(oracle_dispo):
    r = _reel().executer("RH_DIR", "SELECT a.employee_id FROM employees a CROSS JOIN employees b")
    assert len(r.lignes) <= 200


def test_reel_le_schema_vu_par_un_manager(oracle_dispo):
    s = _reel().schema("MGR_50")
    assert "EMPLOYEES" in s and "PROFILS" not in s
