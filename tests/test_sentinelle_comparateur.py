from sentinelle.comparateur import comparer
from sentinelle.empreinte import empreinte

S = {"SALARY"}


def I(sql):
    return empreinte(sql, S)


def test_identiques_score_nul():
    v = comparer(I("SELECT COUNT(*) FROM hr.employees WHERE department_id=50"),
                 I("SELECT COUNT(*) AS NB FROM EMPLOYEES WHERE DEPARTMENT_ID=50"))
    assert v.score == 0 and v.raisons == ()


def test_compte_devenu_liste_avec_salaires():
    v = comparer(I("SELECT COUNT(*) FROM hr.employees WHERE department_id=50"),
                 I("SELECT last_name, salary FROM hr.employees WHERE department_id=50"))
    assert v.score == 4 + 4 + 1
    assert "colonne sensible SALARY non demandée" in v.raisons


def test_sensible_demandee_pas_d_alerte():
    v = comparer(I("SELECT last_name, salary FROM hr.employees ORDER BY salary DESC FETCH FIRST 5 ROWS ONLY"),
                 I("SELECT last_name, salary FROM employees ORDER BY salary DESC FETCH FIRST 5 ROWS ONLY"))
    assert v.score == 0


def test_colonne_en_plus_non_sensible():
    assert comparer(I("SELECT COUNT(*) FROM hr.employees"),
                    I("SELECT COUNT(*), department_id FROM hr.employees GROUP BY department_id")).score == 1


def test_illisible():
    assert comparer(I("SELECT COUNT(*) FROM hr.employees"), I("BEGIN NULL; END;")).score == 5
