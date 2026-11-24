from sentinelle.comparateur import comparer
from sentinelle.empreinte import empreinte
from sentinelle.reecriture import reecrire

S = {"SALARY"}
E = lambda sql: empreinte(sql, S)  # noqa: E731


def test_liste_ramenee_a_un_compte_avec_le_meme_filtre():
    r = reecrire("SELECT last_name, salary FROM employees WHERE department_id = 50",
                 E("SELECT COUNT(*) FROM hr.employees WHERE department_id = 50"), S)
    assert r is not None and "COUNT(*)" in r.upper() and "DEPARTMENT_ID = 50" in r.upper()
    assert E(r).forme == "compte"


def test_moyenne():
    r = reecrire("SELECT last_name, salary FROM employees WHERE department_id = 50",
                 E("SELECT AVG(salary) FROM hr.employees WHERE department_id = 50"), S)
    assert E(r).forme == "moyenne" and E(r).colonnes == {"SALARY"}


def test_liste_sans_le_salaire_en_trop():
    intention = E("SELECT last_name FROM hr.employees WHERE department_id = 50")
    r = reecrire("SELECT last_name, salary FROM employees WHERE department_id = 50", intention, S)
    assert E(r).colonnes == {"LAST_NAME"} and comparer(intention, E(r)).score == 0


def test_group_by_et_union_et_illisible_refuses():
    i = E("SELECT COUNT(*) FROM hr.employees")
    assert reecrire("SELECT department_id, COUNT(*) FROM employees GROUP BY department_id", i, S) is None
    assert reecrire("SELECT last_name FROM employees UNION SELECT last_name FROM employees", i, S) is None
    assert reecrire("BEGIN NULL; END;", i, S) is None


def test_liste_sans_colonne_refusee():
    vide = E("SELECT COUNT(*) FROM hr.employees")
    vide = vide.__class__(True, frozenset(), frozenset(), frozenset(), "liste", False)
    assert reecrire("SELECT last_name FROM employees", vide, S) is None


# 24/11 : réécritures exécutées sur Oracle — 8 sur 127 rendaient un mauvais chiffre.
def test_compte_qui_nomme_une_colonne_n_est_pas_reecrit():
    # « combien de managers différents » : COUNT(*), COUNT(col) ou COUNT(DISTINCT col) ? ambigu.
    intention = empreinte("SELECT COUNT(DISTINCT manager_id) FROM employees", S)
    assert reecrire("SELECT * FROM employees WHERE department_id = 50", intention, S) is None


def test_calcul_sur_agregats_n_est_pas_reecrit():
    intention = empreinte("SELECT MAX(salary) - MIN(salary) FROM employees", S)
    assert intention.forme == "calcul"
    assert reecrire("SELECT * FROM employees WHERE department_id = 50", intention, S) is None
