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
