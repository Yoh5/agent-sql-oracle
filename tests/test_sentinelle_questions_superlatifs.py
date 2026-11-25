import sqlglot

from borne.utilite import QUESTIONS
from sentinelle.questions_dev import QUESTIONS_DEV
from sentinelle.questions_superlatifs import QUESTIONS_SUPERLATIFS


def test_ids_uniques_et_prefixes():
    ids = [q.id for q in QUESTIONS_SUPERLATIFS]
    assert len(ids) == len(set(ids)) and all(i.startswith("sup:") for i in ids)


def test_questions_neuves():
    deja = {q.question for q in [*QUESTIONS, *QUESTIONS_DEV]}
    assert not deja & {q.question for q in QUESTIONS_SUPERLATIFS}


def test_verites_lisibles_et_profils_connus():
    for q in QUESTIONS_SUPERLATIFS:
        assert q.profil in {"manager_50", "manager_80", "rh"}
        sqlglot.parse_one(q.sql_verite, read="oracle")
