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
    d = e([SANS_FILTRE], sql="WITH x AS (SELECT email FROM employees) SELECT email FROM x")
    assert d.action == "humain" and "sonde impossible : cte" in d.raisons_restantes


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


# 25/11 : une intention illisible part en enquête ; le second avis lit alors la question en entier,
# et la chaîne est rejouée avec son intention. La sonde garde le dernier mot sur le périmètre.
ILLISIBLE = "intention illisible"
SQL_50 = "SELECT last_name FROM employees WHERE department_id = 50"


def test_illisible_rejugee_par_le_second_avis_et_sans_raison_liberee():
    d = enqueter(SQL_50, (ILLISIBLE,), R, T, lambda s: False, avis("LAST_NAME"), [], rejuger=lambda i: ())
    assert d.action == "liberer" and ILLISIBLE in d.raisons_levees


def test_illisible_rejugee_mais_le_second_avis_voit_un_ecart():
    d = enqueter(SQL_50, (ILLISIBLE,), R, T, lambda s: False, avis("LAST_NAME"), [],
                 rejuger=lambda i: (SENSIBLE,))
    assert d.action == "humain" and SENSIBLE in d.raisons_restantes


def test_illisible_et_second_avis_illisible_humain():
    d = enqueter(SQL_50, (ILLISIBLE,), R, T, lambda s: False, lambda: None, [], rejuger=lambda i: ())
    assert d.action == "humain" and ILLISIBLE in d.raisons_restantes


def test_illisible_sans_rejeu_humain():
    assert enqueter(SQL_50, (ILLISIBLE,), R, T, lambda s: False, jamais, []).action == "humain"


def test_illisible_mais_hors_perimetre_coupe_avant_tout_avis():
    assert enqueter(SQL_50, (ILLISIBLE,), R, T, lambda s: True, jamais, [], rejuger=lambda i: ()).action == "couper"


def test_meme_texte_de_raison_que_la_chaine():
    from sentinelle.chaine import INTENTION_ILLISIBLE
    assert ILLISIBLE == INTENTION_ILLISIBLE


# 25/11 : la RH (règle « 1 = 1 », tous les services) n'a pas de périmètre à sonder : aucune ligne ne peut
# en sortir. Avant, « sonde impossible : sans_partition » l'envoyait à un humain (36 légitimes).
def test_regle_d_acces_total_rien_a_sonder():
    d = enqueter("SELECT last_name FROM employees", ("EMPLOYEES lue sans filtre sur DEPARTMENT_ID",), "1 = 1", T,
                 lambda s: (_ for _ in ()).throw(AssertionError("pas de sonde")), jamais, [])
    assert d.action == "liberer" and d.hors is False


def test_regle_illisible_reste_humain():
    d = enqueter("SELECT last_name FROM employees", (SANS_FILTRE,), "region = 'EU' OR 1 = 1", T,
                 lambda s: False, jamais, [])
    assert d.action == "humain"


# 25/11 : les superlatifs (« le nom de la dernière embauche ») — une liste d'AU PLUS une ligne reçue
LISTE = "liste rendue pour une question de calcul"
DERNIER = "SELECT last_name FROM employees WHERE department_id = 50 ORDER BY hire_date DESC FETCH FIRST 1 ROW ONLY"


@pytest.mark.parametrize("n", [0, 1])
def test_liste_d_une_ligne_au_plus_liberee(n):
    d = enqueter(DERNIER, (LISTE,), R, T, lambda s: False, jamais, [], lignes=n)
    assert d.action == "liberer" and d.raisons_levees == (LISTE,)


@pytest.mark.parametrize("n", [None, 2, 107])
def test_liste_de_plusieurs_lignes_ou_inconnue_humain(n):
    d = enqueter(DERNIER, (LISTE,), R, T, lambda s: False, jamais, [], lignes=n)
    assert d.action == "humain" and d.raisons_restantes == (LISTE,)


def test_une_ligne_ne_leve_que_la_forme():
    d = enqueter(DERNIER, (LISTE, "SELECT *"), R, T, lambda s: False, jamais, [], lignes=1)
    assert d.action == "humain" and d.raisons_restantes == ("SELECT *",)


def test_une_ligne_hors_perimetre_coupe_quand_meme():
    assert enqueter(DERNIER, (LISTE,), R, T, lambda s: True, jamais, [], lignes=1).action == "couper"


def test_meme_texte_de_raison_que_le_comparateur():
    from sentinelle.comparateur import comparer
    from sentinelle.empreinte import Empreinte
    vide = frozenset()
    v = comparer(Empreinte(True, vide, vide, vide, "calcul", False),
                 Empreinte(True, vide, vide, vide, "liste", False))
    assert LISTE in v.raisons
