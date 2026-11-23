from sentinelle.perimetre import hors_regle


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
