import pytest

from borne.agent import Resultat, repondre
from borne.config import Barrieres
from borne.modele import ModeleFactice, Proposition


class ExecuteurFactice:
    def __init__(self, *resultats):
        self.resultats = list(resultats)
        self.appels = []

    def schema(self, compte):
        return "EMPLOYEES(EMPLOYEE_ID, EMAIL, SALARY, DEPARTMENT_ID)"

    def executer(self, compte, sql):
        self.appels.append((compte, sql))
        return self.resultats.pop(0)


OK = Resultat([(1,), (2,)], ["N"], None, None, "audit-1")


def _tour(modele, executeur, profil="manager_50", barrieres=Barrieres()):
    return repondre("question", profil, barrieres, modele, executeur)


def test_une_lecture_est_executee_sous_le_compte_du_profil():
    ex = ExecuteurFactice(OK)
    t = _tour(ModeleFactice({"question": "SELECT 1 FROM dual"}), ex)
    assert t.issue == "reussi" and t.lignes == 2 and t.audit_ref == "audit-1"
    assert ex.appels == [("MGR_50", "SELECT 1 FROM dual")]


def test_sans_compte_restreint_on_vise_la_copie_jetable():
    ex = ExecuteurFactice(OK)
    _tour(ModeleFactice({"question": "SELECT 1 FROM dual"}), ex, barrieres=Barrieres(compte_restreint=False))
    assert ex.appels[0][0] == "HR_BAC"


def test_un_refus_du_modele_nexecute_rien():
    class Refuse:
        nom = "refuse"
        def ecrire_sql(self, *a):
            return Proposition(None, "hors de votre service", "REFUS: …")
    ex = ExecuteurFactice()
    t = _tour(Refuse(), ex)
    assert t.issue == "refus_modele" and ex.appels == []


def test_une_ecriture_attend_un_humain():
    ex = ExecuteurFactice()
    t = _tour(ModeleFactice({"question": "DELETE FROM employees"}), ex)
    assert t.issue == "a_valider" and ex.appels == []


def test_un_refus_de_la_base_est_un_blocage():
    ex = ExecuteurFactice(Resultat([], [], "ORA-01031", "ORA-01031: insufficient privileges", None))
    t = _tour(ModeleFactice({"question": "SELECT 1 FROM dual"}), ex)
    assert t.issue == "bloque_droits" and t.ora == "ORA-01031"


def test_une_erreur_de_sql_a_droit_a_une_seconde_tentative():
    class Corrige:
        nom = "corrige"
        def __init__(self):
            self.vus = []
        def ecrire_sql(self, question, schema, consignes):
            self.vus.append(question)
            return Proposition("SELECT 1 FROM dual", None, "")
    m = Corrige()
    ex = ExecuteurFactice(Resultat([], [], "ORA-00904", "ORA-00904: invalid identifier", None), OK)
    t = _tour(m, ex)
    assert t.issue == "reussi" and len(ex.appels) == 2
    assert "ORA-00904" in m.vus[1]           # l'erreur est rendue au modèle


def test_un_profil_inconnu_est_refuse_avant_toute_connexion():
    ex = ExecuteurFactice()
    with pytest.raises(ValueError):
        _tour(ModeleFactice({}), ex, profil="inconnu")
    assert ex.appels == []
