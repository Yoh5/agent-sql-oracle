import pytest

from sentinelle.sonde import construire_sonde

T = {"EMPLOYEES", "DEPARTMENTS", "JOB_HISTORY"}
R = "department_id = 50"


def test_sonde_simple():
    s, m = construire_sonde("SELECT email FROM employees WHERE job_id = 'SA_REP'", R, T)
    assert m is None and "FETCH FIRST 1 ROW" in s.upper() and "IS NULL" in s.upper() and "<> 50" in s


def test_sonde_garde_les_jointures_et_le_where():  # Oxford
    s, _ = construire_sonde("SELECT e.email FROM employees e JOIN departments d ON e.department_id = d.department_id "
                            "JOIN locations l ON d.location_id = l.location_id WHERE l.city = 'Oxford'", R, T)
    assert "OXFORD" in s.upper() and "E.DEPARTMENT_ID" in s.upper() and "D.DEPARTMENT_ID" in s.upper()


def test_sonde_retire_group_by_having_et_sortie():
    s, _ = construire_sonde("SELECT job_id, AVG(salary) FROM employees GROUP BY job_id HAVING AVG(salary) > 1 "
                            "ORDER BY 2", R, T)
    assert "GROUP BY" not in s.upper() and "HAVING" not in s.upper() and "SALARY" not in s.upper()


def test_sonde_table_qualifiee_sans_alias():
    s, _ = construire_sonde("SELECT COUNT(*) FROM hr.employees", R, T)
    assert "EMPLOYEES.DEPARTMENT_ID" in s.upper()


def test_sonde_garde_la_sous_requete_du_where():   # manager_50:chef
    s, _ = construire_sonde("SELECT last_name FROM employees WHERE employee_id = (SELECT manager_id FROM departments "
                            "WHERE department_id = 50)", R, T)
    assert "MANAGER_ID" in s.upper()


def test_sonde_sans_partition_rien_a_sonder():
    assert construire_sonde("SELECT COUNT(*) FROM employees", "1 = 1", T) == (None, "sans_partition")


@pytest.mark.parametrize("sql,motif", [
    ("SELECT email FROM employees UNION SELECT email FROM employees", "union"),
    ("WITH x AS (SELECT * FROM employees) SELECT * FROM x", "cte"),
    ("SELECT * FROM (SELECT * FROM employees) t", "derivee"),
    ("SELECT utl_http.request('http://x') FROM employees", "fonction"),
    ("SELECT hr.f(salary) FROM employees", "fonction"),
    ("SELECT f(salary) FROM employees", "fonction"),
    ("SELECT email FROM employees WHERE employee_id IN (SELECT g(1) FROM dual)", "fonction"),
    ("pas du sql", "illisible"),
    ("SELECT * FROM locations", "aucune_table_partitionnee"),
])
def test_sonde_non_construisible(sql, motif):
    assert construire_sonde(sql, R, T) == (None, motif)


# --- Exécution sur Oracle : compte SENT_SONDE, VPD active (elle ne le concerne pas : EXEMPT ACCESS POLICY).

@pytest.fixture(scope="module")
def sonde(oracle_dispo):
    import os
    from sentinelle.sonde import Sonde
    try:
        return Sonde(os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1"), os.environ.get("PERSONA_PASSWORD", ""))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"compte SENT_SONDE absent ({type(e).__name__}) : python scripts/installer.py --sonde")


@pytest.mark.parametrize("sql,attendu", [
    ("SELECT email FROM employees WHERE job_id = 'SA_REP'", True),
    ("SELECT e.email FROM employees e JOIN departments d ON e.department_id = d.department_id "
     "JOIN locations l ON d.location_id = l.location_id WHERE l.city = 'Oxford'", True),
    ("SELECT COUNT(*) FROM employees WHERE department_id = 50", False),
    ("SELECT last_name FROM employees WHERE employee_id = (SELECT manager_id FROM departments "
     "WHERE department_id = 50)", False),
    ("SELECT COUNT(*) FROM employees WHERE employee_id = 178", True),   # Grant : service NULL
])
def test_reel_sonde(sonde, sql, attendu):
    s, motif = construire_sonde(sql, R, T)
    assert motif is None and sonde.hors_perimetre(s) is attendu


def test_reel_sonde_sans_autre_droit(sonde):
    assert sonde.hors_perimetre("SELECT 1 FROM dba_users FETCH FIRST 1 ROWS ONLY") is None
    assert sonde.hors_perimetre("SELECT 1 FROM sec_admin.profils FETCH FIRST 1 ROWS ONLY") is None
