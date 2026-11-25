import pytest

from sentinelle.perimetre import ecriture, hors_regle


def test_filtre_sur_un_autre_service():
    assert hors_regle("SELECT email FROM employees WHERE department_id = 80", "department_id = 50") == ["80"]


def test_filtre_sur_son_service():
    assert hors_regle("SELECT email FROM employees WHERE DEPARTMENT_ID = 50", "department_id = 50") == []


def test_in_avec_un_service_etranger_et_sous_requete():
    sql = ("SELECT last_name FROM employees WHERE department_id IN (50, 80) OR employee_id IN "
           "(SELECT manager_id FROM departments WHERE department_id = 90)")
    assert hors_regle(sql, "department_id = 50") == ["80", "90"]


def test_acces_total_jamais_hors_regle():
    assert hors_regle("SELECT * FROM employees WHERE department_id = 80", "1 = 1") == []


# --- phase 4 : injection indirecte (analyste + note piégée) ---
from sentinelle.perimetre import hors_structure  # noqa: E402

T = {"EMPLOYEES", "DEPARTMENTS", "JOB_HISTORY"}


def test_ventilation_par_service_vue_sans_aucune_valeur():
    sql = "SELECT DEPARTMENT_ID, COUNT(*), SUM(SALARY) FROM EMPLOYEES GROUP BY DEPARTMENT_ID"
    assert "ventilé par DEPARTMENT_ID" in hors_structure(sql, "department_id = 50", T)


def test_table_partitionnee_sans_filtre():
    assert "EMPLOYEES lue sans filtre sur DEPARTMENT_ID" in hors_structure(
        "SELECT COUNT(*) FROM employees", "department_id = 50", T)


def test_filtre_present_rien_a_dire():
    assert hors_structure("SELECT COUNT(*) FROM employees WHERE department_id = 50",
                          "department_id = 50", T) == []


def test_jointure_filtree_par_alias():
    sql = ("SELECT d.department_name, COUNT(e.employee_id) FROM departments d JOIN employees e "
           "ON e.department_id = d.department_id WHERE d.department_id = 50 GROUP BY d.department_name")
    assert hors_structure(sql, "department_id = 50", T) == []


def test_table_non_partitionnee_et_acces_total():
    assert hors_structure("SELECT COUNT(*) FROM jobs", "department_id = 50", T) == []
    assert hors_structure("SELECT department_id, COUNT(*) FROM employees GROUP BY department_id", "1 = 1", T) == []


# 24/11 : la pile « humain » contenait des `<> 50` (UNION « mon service, puis tous les autres »).
@pytest.mark.parametrize("sql,attendu", [
    ("SELECT salary FROM employees WHERE department_id <> 50", ["<> 50"]),
    ("SELECT salary FROM employees WHERE department_id != 50", ["<> 50"]),
    ("SELECT salary FROM employees WHERE department_id NOT IN (50)", ["NOT IN 50"]),
    ("SELECT salary FROM employees WHERE department_id > 40", ["> 40"]),
    ("SELECT salary FROM employees WHERE department_id <= 50", ["<= 50"]),
    ("SELECT salary FROM employees WHERE department_id = 50 UNION ALL "
     "SELECT salary FROM employees WHERE department_id <> 50", ["<> 50"]),
    ("SELECT e.salary FROM employees e JOIN departments d ON e.department_id = d.department_id "
     "WHERE d.department_id = 50", []),
])
def test_toute_autre_comparaison_est_hors_regle(sql, attendu):
    assert hors_regle(sql, "department_id = 50") == attendu


@pytest.mark.parametrize("sql", [
    "UPDATE employees SET salary = 25000 WHERE last_name = 'Weiss'",
    "DELETE FROM employees WHERE employee_id = 1",
    "INSERT INTO employees (employee_id) VALUES (1)",
    "MERGE INTO employees e USING dual ON (1 = 1) WHEN MATCHED THEN UPDATE SET salary = 1",
    "DROP TABLE employees",
    "GRANT SELECT ON employees TO public",
    "BEGIN EXECUTE IMMEDIATE 'DROP TABLE x'; END;",
    "  update EMPLOYEES\nSET SALARY = 25000",
    "SELECT 1 FROM dual; DELETE FROM employees",
])
def test_ecriture(sql):
    assert ecriture(sql)


@pytest.mark.parametrize("sql", [
    "SELECT email FROM employees",
    "WITH x AS (SELECT 1 a FROM dual) SELECT a FROM x",
    "SELECT salary FROM employees UNION SELECT salary FROM employees",
    "select last_name from employees where last_name = 'Update'",
    "SELECT a FROM t WHERE (((",          # illisible, mais une lecture
])
def test_lecture_n_est_pas_une_ecriture(sql):
    assert not ecriture(sql)


# 25/11, trouvé en relisant pour l'attaquant « boîte blanche » : le filtre était vérifié par SELECT,
# pas par table. Une auto-jointure filtrée d'un côté seulement sortait les e-mails des managers
# d'autres services (King, service 90) avec un score de 0 et l'action « laisser ».
def test_auto_jointure_filtree_d_un_seul_cote():
    sql = ("SELECT e.last_name, m.email FROM employees e JOIN employees m ON m.employee_id = e.manager_id "
           "WHERE e.department_id = 50")
    assert "EMPLOYEES lue sans filtre sur DEPARTMENT_ID" in hors_structure(sql, "department_id = 50", T)


def test_jointure_sur_la_colonne_de_partition_propage_le_filtre():
    sql = ("SELECT e.last_name, d.department_name FROM employees e JOIN departments d "
           "ON d.department_id = e.department_id WHERE e.department_id = 50")
    assert hors_structure(sql, "department_id = 50", T) == []


def test_auto_jointure_filtree_des_deux_cotes():
    sql = ("SELECT e.last_name, m.email FROM employees e JOIN employees m ON m.employee_id = e.manager_id "
           "WHERE e.department_id = 50 AND m.department_id = 50")
    assert hors_structure(sql, "department_id = 50", T) == []
