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


def test_une_reecriture_qui_changerait_la_reponse_est_comptee():
    # « managers différents » lu comme un compte sans colonne : la réécriture rendrait COUNT(*)
    paires = [(Q["manager_50:managers_distincts"], Intention(frozenset(), "compte", "mon_service")),
              (Q["manager_50:effectif"], Intention(frozenset(), "compte", "mon_service")),
              (Q["manager_50:salaire_moyen"], Intention(frozenset({"SALARY"}), "moyenne", "mon_service"))]
    r = juger_intentions(paires, {"SALARY"})
    assert r["reecritures_alterees"] == 1
    assert r["erreurs"] == [("manager_50:managers_distincts", "réécriture altérée")]


def test_les_erreurs_sont_nommees():
    paires = [(Q["manager_50:salaire_moyen"], Intention(frozenset(), "moyenne", "mon_service"))]
    r = juger_intentions(paires, {"SALARY"})
    assert ("manager_50:salaire_moyen", "sensibles") in r["erreurs"]
