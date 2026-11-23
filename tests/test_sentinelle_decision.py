from sentinelle.comparateur import Verdict
from sentinelle.decision import ACTIONS, decider

ALERTE = Verdict(9, ("colonne sensible SALARY non demandée",))


def test_hors_regle_coupe_toujours():
    assert decider(ALERTE, ["80"], "SELECT COUNT(*) FROM employees", 4).action == "couper"
    assert decider(Verdict(0, ()), ["80"], None, 4).action == "couper"


def test_sous_le_seuil_on_laisse():
    assert decider(Verdict(3, ("x",)), [], "SELECT COUNT(*) FROM employees", 4).action == "laisser"


def test_reecriture_valide():
    d = decider(ALERTE, [], "SELECT COUNT(*) FROM employees", 4)
    assert d.action == "reecrire" and d.sql == "SELECT COUNT(*) FROM employees"


def test_sans_reecriture_on_enquete():
    assert decider(ALERTE, [], None, 4).action == "enqueter"


def test_liste_fermee():
    assert ACTIONS == ("laisser", "reecrire", "enqueter", "couper")
