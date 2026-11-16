"""Le juge de la phase 3 : sans base pour la comparaison, avec Oracle pour le catalogue."""
import os

import pytest

from borne.preuve import comparer
from borne.regles import CATALOGUE


def _photo(**vus):
    return {c: {"EMPLOYEES": v} for c, v in vus.items()}


def test_des_lignes_en_trop_sont_un_trou_et_en_moins_un_exces():
    ref = _photo(M={"1", "2"}, X=set())
    assert comparer(ref, _photo(M={"1", "2"}, X=set())).verdict == "juste"
    assert comparer(ref, _photo(M={"1", "2"}, X={"1"})).verdict == "trou"
    assert comparer(ref, _photo(M={"1"}, X=set())).verdict == "trop_stricte"
    assert comparer(ref, _photo(M={"1", "3"}, X=set())).verdict == "trou_et_trop_stricte"


def test_une_politique_qui_plante_est_une_erreur_pas_un_succes():
    # Oracle refuse alors la requête entière : « zéro ligne en trop » n'est pas une victoire.
    assert comparer(_photo(M={"1"}), _photo(M=None)).verdict == "erreur"


def test_chaque_regle_a_des_mutants_des_deux_sortes():
    for r in CATALOGUE:
        assert {"trou", "trop_stricte"} <= {m.attendu for m in r.mutants.values()}, r.id


@pytest.fixture(scope="module")
def terrain(oracle_dispo):
    from borne.politique import TerrainEssai
    return TerrainEssai(os.environ["ORACLE_DSN"], os.environ.get("PERSONA_PASSWORD", ""))


@pytest.mark.parametrize("regle", CATALOGUE, ids=lambda r: r.id)
def test_reel_la_reference_est_juste_et_chaque_mutant_est_attrape(terrain, regle):
    from borne.preuve import juger
    assert juger(terrain, regle.reference, regle.reference).verdict == "juste"
    for nom, mutant in regle.mutants.items():
        v = juger(terrain, regle.reference, mutant.source)
        assert v.verdict == mutant.attendu, f"{regle.id}/{nom} ({mutant.defaut}) : {v.verdict} — {v.resume()}"


def test_reel_une_politique_malveillante_est_refusee_avant_la_base(terrain):
    from borne.preuve import juger
    piege = CATALOGUE[0].reference.replace("BEGIN\n", "BEGIN\n  EXECUTE IMMEDIATE 'GRANT DBA TO essai_x';\n", 1)
    assert juger(terrain, CATALOGUE[0].reference, piege).verdict == "refusee"
