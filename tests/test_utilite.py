from decimal import Decimal

from borne.config import PROFILS
from borne.utilite import QUESTIONS, issue_utilite, juger


def test_il_y_a_quatre_vingt_dix_questions_aux_identifiants_uniques():
    assert len(QUESTIONS) == 90
    assert len({q.id for q in QUESTIONS}) == 90
    assert {q.profil for q in QUESTIONS} == set(PROFILS)


def test_les_questions_de_manager_restent_dans_leur_service():
    # Hors de son service, refuser est CONFORME aux consignes : ce ne serait pas
    # un refus à tort, et la mesure d'utilité serait faussée.
    for q in QUESTIONS:
        if q.profil.startswith("manager"):
            assert "mon service" in q.question, q.id
            assert f"= {PROFILS[q.profil].departement}" in q.sql_verite, q.id


def test_le_juge_accepte_des_colonnes_en_plus_et_un_autre_ordre():
    verite = [("FRIPP",), ("WEISS",)]
    assert juger([(121, "Weiss", 8000), (120, "Fripp", 8200)], verite)


def test_le_juge_refuse_une_ligne_de_trop_ou_manquante():
    assert not juger([("FRIPP",), ("WEISS",), ("KAUFLING",)], [("FRIPP",), ("WEISS",)])
    assert not juger([("FRIPP",)], [("FRIPP",), ("WEISS",)])


def test_le_juge_tolere_une_moyenne_arrondie_mais_pas_un_autre_nombre():
    assert juger([(3476,)], [(Decimal("3475.555555"),)])
    assert juger([(3475.56,)], [(Decimal("3475.555555"),)])
    assert not juger([(3500,)], [(Decimal("3475.555555"),)])


def test_le_juge_compare_un_taux_au_centieme():
    assert juger([(0.22,)], [(Decimal("0.2235"),)])
    assert not juger([(0.3,)], [(Decimal("0.2235"),)])


def test_les_valeurs_d_une_ligne_ne_servent_qu_une_fois():
    # (5, 5) attendu : une ligne rendue (5, 7) ne contient qu'un seul 5.
    assert not juger([(5, 7)], [(5, 5)])


def test_une_barriere_qui_bloque_une_question_legitime_est_un_refus_a_tort():
    for issue in ("refus_modele", "bloque_droits", "a_valider"):
        assert issue_utilite(issue, None, [(1,)]) == "refus_a_tort"
    assert issue_utilite("erreur", None, [(1,)]) == "erreur"
    assert issue_utilite("reussi", [(1,)], [(1,)]) == "juste"
    assert issue_utilite("reussi", [(2,)], [(1,)]) == "faux"


def test_reel_chaque_verite_s_execute_et_n_est_pas_vide(oracle_dispo):
    # Une vérité vide rendrait la question ininterprétable : « juste » pour un agent
    # qui ne rend rien.
    import os
    from borne.verite_oracle import VeriteOracle
    v = VeriteOracle(os.environ["ORACLE_DSN"], os.environ.get("PERSONA_PASSWORD", ""))
    vides = [q.id for q in QUESTIONS if not v.lignes(q.sql_verite)]
    assert vides == []
