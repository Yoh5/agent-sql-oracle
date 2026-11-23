from sentinelle.empreinte import empreinte

S = {"SALARY"}


def test_compte_avec_alias_et_table_non_qualifiee():
    e = empreinte("SELECT COUNT(*) AS NB FROM EMPLOYEES WHERE DEPARTMENT_ID = 50", S)
    assert e.valide and e.forme == "compte" and e.tables == {"EMPLOYEES"} and e.sensibles == set()


def test_moyenne_sort_la_colonne_agregee():
    e = empreinte("SELECT AVG(salary) FROM hr.employees WHERE department_id = 50", S)
    assert e.forme == "moyenne" and e.colonnes == {"SALARY"} and e.sensibles == {"SALARY"}


def test_sous_requete_ne_sort_pas_salary():
    e = empreinte("SELECT last_name FROM hr.employees WHERE department_id = 50 AND salary = "
                  "(SELECT MAX(salary) FROM hr.employees WHERE department_id = 50)", S)
    assert e.forme == "liste" and e.colonnes == {"LAST_NAME"} and e.sensibles == set()


def test_etoile_expose_toutes_les_sensibles():
    e = empreinte("SELECT * FROM employees", S)
    assert e.etoile and e.sensibles == {"SALARY"}


def test_groupe():
    sql = "SELECT department_id, SUM(salary) FROM hr.employees GROUP BY department_id"
    assert empreinte(sql, S).forme == "groupe"


def test_illisible_ne_leve_pas():
    assert empreinte("BEGIN EXECUTE IMMEDIATE 'x'; END;", S).valide is False
    assert empreinte("SELECT 1 FROM dual; DROP TABLE t", S).valide is False
