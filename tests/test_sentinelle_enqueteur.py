import pytest

from sentinelle.enqueteur import ACTIONS_ENQUETE, enqueter
from sentinelle.intention import Intention

T = {"EMPLOYEES", "DEPARTMENTS", "JOB_HISTORY"}
R = "department_id = 50"
SQL = "SELECT job_id, AVG(salary) FROM employees WHERE department_id = 50 GROUP BY job_id"
SANS_FILTRE = "EMPLOYEES lue sans filtre sur DEPARTMENT_ID"
SENSIBLE = "colonne sensible SALARY non demandée"


def avis(*cols):
    return lambda: Intention(frozenset(cols), "groupe", "mon_service")


def jamais():
    raise AssertionError("le second avis ne devait pas être demandé")


def e(raisons, hors=False, second=jamais, historique=(), sql=SQL):
    return enqueter(sql, tuple(raisons), R, T, lambda s: hors, second, list(historique))


def test_actions_fermees():
    assert ACTIONS_ENQUETE == ("liberer", "couper", "humain")


def test_ligne_hors_perimetre_coupe_toujours():
    d = e([SENSIBLE], hors=True, second=avis("SALARY"))
    assert d.action == "couper" and d.hors is True


def test_sonde_non_construisible_humain():
    d = e([SANS_FILTRE], sql="SELECT email FROM employees UNION SELECT email FROM employees")
    assert d.action == "humain" and "sonde impossible : union" in d.raisons_restantes


def test_sonde_en_erreur_humain():
    assert e([SANS_FILTRE], hors=None).action == "humain"


def test_sans_filtre_leve_par_la_sonde():
    d = e([SANS_FILTRE])
    assert d.action == "liberer" and d.raisons_levees == (SANS_FILTRE,)


def test_colonne_confirmee_par_le_second_avis():
    d = e([SENSIBLE], second=avis("SALARY", "JOB_ID"))
    assert d.action == "liberer" and d.avis == ("JOB_ID", "SALARY")


@pytest.mark.parametrize("second", [avis("JOB_ID"), lambda: None])
def test_colonne_non_confirmee_humain(second):
    assert e([SENSIBLE], second=second).action == "humain"


def test_colonne_en_plus_aussi_levee_par_l_avis():
    assert e(["colonne LAST_NAME en plus"], second=avis("LAST_NAME")).action == "liberer"


@pytest.mark.parametrize("raison", ["question hors du périmètre du profil", "SELECT *",
                                    "liste rendue pour une question de compte", "table JOBS non demandée",
                                    "SQL illisible pour la sentinelle"])
def test_autres_raisons_humain(raison):
    assert e([raison], second=avis("SALARY")).action == "humain"


def test_session_suspecte_humain():
    d = e([SANS_FILTRE], historique=["couper", "enqueter"])
    assert d.action == "humain" and d.historique == 2


def test_historique_sous_le_seuil_n_empeche_pas():
    assert e([SANS_FILTRE], historique=["laisser", "laisser", "couper"]).action == "liberer"
