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


# --- relecture finale : défauts trouvés, reproduits avant correction ---
from sentinelle.comparateur import comparer  # noqa: E402

M = {"EMPLOYEES": ["SALARY"]}


def test_union_lit_toutes_les_branches():
    v = comparer(empreinte("SELECT COUNT(*) FROM hr.employees WHERE department_id=50", S),
                 empreinte("SELECT COUNT(*) FROM hr.employees WHERE department_id=50 UNION ALL "
                           "SELECT salary FROM hr.employees WHERE department_id=50", S))
    assert "colonne sensible SALARY non demandée" in v.raisons and v.score >= 8


def test_sous_requete_scalaire_dans_le_select_sort_sa_colonne():
    e = empreinte("SELECT last_name, (SELECT salary FROM hr.employees x WHERE x.employee_id = e.employee_id) "
                  "FROM hr.employees e WHERE department_id = 50", S)
    assert e.sensibles == {"SALARY"}


def test_table_derivee_renommee_remonte_a_la_source():
    e = empreinte("SELECT last_name, s FROM (SELECT last_name, salary AS s FROM hr.employees) d", S)
    assert e.sensibles == {"SALARY"}


def test_cte_renommee_et_nom_de_cte_pas_une_table():
    e = empreinte("WITH x AS (SELECT salary AS s FROM hr.employees) SELECT s FROM x", S)
    assert e.sensibles == {"SALARY"} and e.tables == {"EMPLOYEES"}


def test_etoile_n_expose_que_les_sensibles_des_tables_presentes():
    assert empreinte("SELECT * FROM hr.regions", M).sensibles == set()
    assert empreinte("SELECT * FROM hr.employees", M).sensibles == {"SALARY"}


def test_agregat_enveloppe_reste_un_agregat():
    assert empreinte("SELECT ROUND(AVG(salary), 2) FROM hr.employees", S).forme == "moyenne"
    assert empreinte("SELECT NVL(SUM(salary), 0) FROM hr.employees", S).forme == "somme"
    assert empreinte("SELECT MAX(salary) - MIN(salary) FROM hr.employees", S).forme != "liste"


def test_calcul_sur_plusieurs_agregats():
    assert empreinte("SELECT MAX(salary) - MIN(salary) FROM employees", {"SALARY"}).forme == "calcul"
    assert empreinte("SELECT SUM(salary) / COUNT(*) AS m FROM employees", {"SALARY"}).forme == "calcul"
    assert empreinte("SELECT ROUND(AVG(salary), 2) FROM employees", {"SALARY"}).forme == "moyenne"
