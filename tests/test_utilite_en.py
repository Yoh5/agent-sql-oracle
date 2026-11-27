"""Les questions anglaises ne changent QUE la langue : mêmes ids, profils et vérités."""
from borne.utilite import QUESTIONS
from borne.utilite_en import QUESTIONS_EN


def test_meme_jeu_que_le_francais():
    assert len(QUESTIONS_EN) == len(QUESTIONS) == 90
    for fr, en in zip(QUESTIONS, QUESTIONS_EN):
        assert (fr.id, fr.profil, fr.sql_verite) == (en.id, en.profil, en.sql_verite)


def test_toutes_traduites():
    for fr, en in zip(QUESTIONS, QUESTIONS_EN):
        assert en.question != fr.question
        assert en.question.isascii(), en.question


def test_managers_parlent_de_leur_departement():
    for q in QUESTIONS_EN:
        if q.profil.startswith("manager"):
            assert "my department" in q.question, q.question
