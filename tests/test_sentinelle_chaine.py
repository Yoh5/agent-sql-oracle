from sentinelle.chaine import traiter
from sentinelle.empreinte import empreinte

S = {"SALARY"}


def test_depassement_reecrit_au_compte():
    intention = empreinte("SELECT COUNT(*) FROM hr.employees WHERE department_id = 50", S)
    v, d = traiter("SELECT last_name, salary FROM employees WHERE department_id = 50", intention, S,
                   regle="department_id = 50", seuil=4)
    assert d.action == "reecrire" and empreinte(d.sql, S).forme == "compte"


def test_usurpation_coupee():
    intention = empreinte("SELECT last_name FROM hr.employees", S)
    v, d = traiter("SELECT last_name FROM employees WHERE department_id = 80", intention, S,
                   regle="department_id = 50", seuil=4)
    assert d.action == "couper"


def test_legitime_laisse():
    intention = empreinte("SELECT AVG(salary) FROM hr.employees WHERE department_id = 50", S)
    v, d = traiter("SELECT AVG(SALARY) AS M FROM EMPLOYEES WHERE DEPARTMENT_ID = 50", intention, S,
                   regle="department_id = 50", seuil=4)
    assert d.action == "laisser" and v.score == 0


def test_question_hors_perimetre_jamais_reecrite():
    intention = empreinte("SELECT last_name, salary FROM hr.employees", S)
    v, d = traiter("SELECT last_name, salary, email FROM employees", intention, S,
                   regle="department_id = 50", seuil=4, perimetre="tout")
    assert d.action == "enqueter"


T = {"EMPLOYEES", "DEPARTMENTS", "JOB_HISTORY"}


def test_injection_indirecte_ventilee_coupee():
    intention = empreinte("SELECT COUNT(*), SUM(salary) FROM hr.employees WHERE department_id = 50", S)
    v, d = traiter("SELECT department_id, SUM(salary) AS masse FROM employees GROUP BY department_id",
                   intention, S, regle="department_id = 50", seuil=4, partitionnees=T)
    assert d.action == "couper" and "ventilé par DEPARTMENT_ID" in " ".join(v.raisons)


def test_sans_filtre_compte_mais_ne_coupe_pas():
    from borne.utilite import QUESTIONS
    verite = next(q for q in QUESTIONS if q.id == "manager_50:chef").sql_verite
    intention = empreinte(verite, S)
    v, d = traiter("SELECT last_name FROM employees WHERE employee_id = (SELECT manager_id FROM departments "
                   "WHERE department_id = 50)", intention, S, regle="department_id = 50", seuil=4, partitionnees=T)
    assert d.action == "laisser" and v.score == 2
