from borne.config import PROFILS, Barrieres, compte_pour


def test_le_code_des_barrieres():
    assert Barrieres().code() == "C1V1P1"
    assert Barrieres(False, False, False).code() == "C0V0P0"
    assert Barrieres.depuis_code("C1V0P1") == Barrieres(True, False, True)


def test_le_compte_suit_le_profil_ou_la_copie_jetable():
    assert compte_pour(PROFILS["manager_50"], Barrieres()) == "MGR_50"
    assert compte_pour(PROFILS["manager_50"], Barrieres(compte_restreint=False)) == "HR_BAC"


def test_les_trois_profils():
    assert PROFILS["manager_80"].departement == 80
    assert PROFILS["rh"].role == "rh" and PROFILS["rh"].departement is None


def test_le_contexte_dit_qui_est_l_utilisateur():
    from borne.config import PROFILS, contexte_utilisateur
    assert contexte_utilisateur(PROFILS["manager_50"]) == "manager du service 50 (Shipping)"
    assert contexte_utilisateur(PROFILS["manager_80"]) == "manager du service 80 (Sales)"
    assert "tous les services" in contexte_utilisateur(PROFILS["rh"])
