from sentinelle.mesure_reecritures import classer_reecriture


def test_exacte_ordre_libre():
    assert classer_reecriture([(2,), (1,)], ["N"], None, [(1,), (2,)], ["N"]) == "exacte"


def test_surplus_colonne_en_plus():
    assert classer_reecriture([(1, 9000)], ["N", "SALARY"], None, [(1,)], ["N"]) == "surplus"


def test_fausse_ligne_manquante_ou_erreur():
    assert classer_reecriture([(1,)], ["N"], None, [(1,), (2,)], ["N"]) == "fausse"
    assert classer_reecriture([], [], "ORA-00904", [(1,)], ["N"]) == "fausse"
