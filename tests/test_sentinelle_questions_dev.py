from borne.utilite import QUESTIONS
from sentinelle.empreinte import empreinte
from sentinelle.questions_dev import QUESTIONS_DEV


def test_le_jeu_de_dev_ne_reprend_aucune_question_du_jeu_de_mesure():
    mesure = {q.question.lower() for q in QUESTIONS}
    assert not [q.id for q in QUESTIONS_DEV if q.question.lower() in mesure]
    assert len({q.id for q in QUESTIONS_DEV}) == len(QUESTIONS_DEV)


def test_chaque_verite_du_jeu_de_dev_se_lit():
    assert all(empreinte(q.sql_verite, {"SALARY"}).valide for q in QUESTIONS_DEV)


def test_le_jeu_de_dev_couvre_les_familles_visees():
    formes = [empreinte(q.sql_verite, {"SALARY"}).forme for q in QUESTIONS_DEV]
    assert formes.count("calcul") >= 5 and formes.count("groupe") >= 5
    assert sum("DISTINCT" in q.sql_verite for q in QUESTIONS_DEV) >= 5
