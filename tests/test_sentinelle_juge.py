from borne.utilite import QUESTIONS
from sentinelle.intention import Intention
from sentinelle.juge import juger_intentions

Q = {q.id: q for q in QUESTIONS}


def test_une_juste_une_fausse_forme_et_une_illisible():
    paires = [(Q["manager_50:effectif"], Intention(frozenset(), "compte", "mon_service")),
              (Q["manager_50:salaire_moyen"], Intention(frozenset({"SALARY"}), "liste", "mon_service")),
              (Q["manager_50:masse"], None)]
    r = juger_intentions(paires, {"SALARY"})
    assert r["n"] == 3 and r["illisibles"] == 1
    assert r["forme_juste"] == 0.5 and r["sensibles_justes"] == 1.0
