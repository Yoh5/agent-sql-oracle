import pytest

from borne.modele import ModeleEnPanne
from sentinelle.catalogue import CATALOGUE_HR
from sentinelle.intention import Intention, demander_intention, lire_intention, vers_empreinte


def test_json_entoure_de_texte():
    i = lire_intention('Voici : {"colonnes": ["salary"], "forme": "moyenne", "perimetre": "mon_service"} fin',
                       CATALOGUE_HR)
    assert i == Intention(frozenset({"SALARY"}), "moyenne", "mon_service")


def test_forme_inconnue_invalide():
    assert lire_intention('{"colonnes": [], "forme": "count", "perimetre": "tout"}', CATALOGUE_HR) is None


def test_colonne_hors_catalogue_retiree():
    i = lire_intention('{"colonnes": ["LAST_NAME", "FOO"], "forme": "liste", "perimetre": "tout"}', CATALOGUE_HR)
    assert i.colonnes == {"LAST_NAME"}


class _Faux:
    def __init__(self, reponse=None, panne=False):
        self.reponse, self.panne, self.messages = reponse, panne, None

    def completer(self, messages):
        self.messages = messages
        if self.panne:
            raise ModeleEnPanne("quota")
        return self.reponse


def test_panne_donne_none():
    assert demander_intention(_Faux(panne=True), "Combien ?", "manager du service 50", CATALOGUE_HR) is None


def test_le_modele_ne_voit_pas_de_sql():
    f = _Faux('{"colonnes": [], "forme": "compte", "perimetre": "mon_service"}')
    i = demander_intention(f, "Combien d'employés compte mon service ?", "manager du service 50", CATALOGUE_HR)
    assert i.forme == "compte"
    assert "SELECT" not in " ".join(m["content"] for m in f.messages).upper()


def test_vers_empreinte():
    e = vers_empreinte(Intention(frozenset({"SALARY", "LAST_NAME"}), "liste", "mon_service"), {"SALARY"})
    assert e.tables == set() and e.sensibles == {"SALARY"} and e.forme == "liste"


def test_la_consigne_v1_est_celle_d_avant():
    from sentinelle.intention import CONSIGNES, _CONSIGNE
    assert CONSIGNES["v1"] is _CONSIGNE


def test_une_consigne_v2_accepte_la_forme_calcul():
    f = _Faux('{"colonnes": ["SALARY"], "forme": "calcul", "perimetre": "mon_service"}')
    assert demander_intention(f, "Écart ?", "manager", CATALOGUE_HR, consigne="v2").forme == "calcul"
    assert demander_intention(f, "Écart ?", "manager", CATALOGUE_HR) is None   # v1 ne la connaît pas
