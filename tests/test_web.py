from fastapi.testclient import TestClient

from borne.agent import Resultat
from borne.modele import ModeleFactice
from borne.web import creer_app


class Executeur:
    def schema(self, compte):
        return "EMPLOYEES(EMPLOYEE_ID, EMAIL)"

    def executer(self, compte, sql):
        return Resultat([(120, "MWEISS"), (121, "AFRIPP")], ["EMPLOYEE_ID", "EMAIL"], None, None, "a-1")


def _client():
    m = ModeleFactice({"qui travaille chez moi ?": "SELECT employee_id, email FROM employees"})
    return TestClient(creer_app(m, Executeur()))


def test_la_page_se_sert():
    r = _client().get("/")
    assert r.status_code == 200 and "Agent SQL" in r.text


def test_une_question_rend_le_tour_et_les_lignes():
    r = _client().post("/question", json={"question": "qui travaille chez moi ?", "profil": "manager_50",
                                          "barrieres": "C1V1P1"})
    d = r.json()
    assert r.status_code == 200
    assert d["tour"]["issue"] == "reussi" and d["tour"]["sql"].startswith("SELECT")
    assert d["lignes"] == [[120, "MWEISS"], [121, "AFRIPP"]] and d["colonnes"] == ["EMPLOYEE_ID", "EMAIL"]
    assert d["couche"]                       # la phrase qui dit où la question s'est arrêtée


def test_un_profil_inconnu_ou_des_barrieres_invalides_sont_refuses():
    c = _client()
    assert c.post("/question", json={"question": "x", "profil": "pdg", "barrieres": "C1V1P1"}).status_code == 400
    assert c.post("/question", json={"question": "x", "profil": "rh", "barrieres": "zzz"}).status_code == 400


def test_les_profils_sont_listes_sans_secret():
    d = _client().get("/profils").json()
    assert {p["nom"] for p in d} == {"manager_50", "manager_80", "rh"}
    assert not any("mot" in str(p).lower() or "password" in str(p).lower() for p in d)
