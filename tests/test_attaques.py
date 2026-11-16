from collections import Counter

from borne.attaques import CATALOGUE, FAMILLES, detecter_fuite
from borne.config import PROFILS


class VeriteFactice:
    def __init__(self, empreinte="A"):
        self._e = empreinte

    def emails_interdits(self, profil):
        return {"JRUSSEL", "KPARTNER"}

    def ids_interdits(self, profil):
        return {145, 146}

    def valeur(self, sql):
        return 691416.0

    def empreinte(self):
        return self._e


def _attaque(nature):
    return next(a for a in CATALOGUE if a.nature == nature)


def test_le_catalogue():
    assert len(CATALOGUE) == 20
    assert len({a.id for a in CATALOGUE}) == 20
    par_famille = Counter(a.famille for a in CATALOGUE)
    assert set(par_famille) == set(FAMILLES) and min(par_famille.values()) >= 2
    assert all(a.profil in PROFILS for a in CATALOGUE)
    assert all(a.question.strip() and a.sql_cede.strip() for a in CATALOGUE)
    # Noms de tables non qualifiés : chaque compte les résout dans son propre périmètre.
    assert not any("hr." in a.sql_cede.lower() for a in CATALOGUE)


def test_une_fuite_par_email_ou_identifiant():
    a = _attaque("lecture")
    v = VeriteFactice()
    assert detecter_fuite(a, [("JRUSSEL", 14000)], ["EMAIL", "SALARY"], None, v, "A")
    assert detecter_fuite(a, [(145,)], ["EMPLOYEE_ID"], None, v, "A")
    assert not detecter_fuite(a, [("SSTILES", 3200)], ["EMAIL", "SALARY"], None, v, "A")
    # 145 dans une colonne qui n'est pas un identifiant d'employé : pas une fuite
    assert not detecter_fuite(a, [(145,)], ["SALARY"], None, v, "A")


def test_une_fuite_par_le_message_derreur():
    a = _attaque("lecture")
    assert detecter_fuite(a, [], [], "ORA-01722: unable to convert string value containing 'JRUSSEL'",
                          VeriteFactice(), "A")


def test_une_fuite_par_agregat():
    a = _attaque("agregat")
    v = VeriteFactice()
    assert detecter_fuite(a, [(691416,)], ["TOTAL"], None, v, "A")
    assert not detecter_fuite(a, [(156400,)], ["TOTAL"], None, v, "A")


def test_une_ecriture_reussie_change_lempreinte():
    a = _attaque("ecriture")
    assert detecter_fuite(a, [], [], None, VeriteFactice(empreinte="B"), "A")
    assert not detecter_fuite(a, [], [], None, VeriteFactice(empreinte="A"), "A")
