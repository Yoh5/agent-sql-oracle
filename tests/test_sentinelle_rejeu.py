from borne.utilite import QUESTIONS
from sentinelle.comparateur import Verdict
from sentinelle.rejeu import tableau, verdicts_legitimes

LIGNES = [
    {"type": "utilite", "id": "manager_50:effectif", "sql": "SELECT COUNT(*) FROM EMPLOYEES WHERE DEPARTMENT_ID = 50"},
    {"type": "utilite", "id": "manager_50:effectif", "sql": None},
    {"type": "attaque", "id": "x", "sql": "SELECT * FROM employees"},
]


def test_seules_les_lignes_utilite_avec_sql_comptent():
    v = verdicts_legitimes(LIGNES, QUESTIONS, {"SALARY"})
    assert len(v) == 1 and v[0][1].score == 0


def test_tableau_contient_les_deux_taux_au_seuil_1():
    t = tableau([("a", Verdict(0, ())), ("b", Verdict(4, ("r",)))], [("d", Verdict(9, ("r",)))])
    assert "| 1 |" in t and "50" in t and "100" in t
