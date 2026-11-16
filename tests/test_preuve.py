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


def test_une_reference_qui_echoue_est_une_faute_du_banc_pas_un_succes():
    # Trouvé le 16/11/2026 : la référence de « historique_actuel » échouait (ORA-28113) et
    # comparer() SAUTAIT la table en silence : un mutant à trou était déclaré « juste ».
    from borne.preuve import ReferenceInvalide
    with pytest.raises(ReferenceInvalide):
        comparer(_photo(M=None), _photo(M={"1"}))


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


def test_le_generateur_extrait_la_fonction_et_donne_les_colonnes_au_modele():
    from borne.generateur import GenerateurPolitique
    vus = []

    class Modele:
        def completer(self, messages):
            vus.append(messages)
            return "Voici :\n```sql\n" + CATALOGUE[0].reference + "\n/\n```\nBonne journée."
    src = GenerateurPolitique(Modele()).generer("un manager voit son service", "gen_x",
                                                {"EMPLOYEES": ["EMPLOYEE_ID", "DEPARTMENT_ID"]})
    assert src.startswith("CREATE OR REPLACE FUNCTION ref_service") and src.endswith("END;")
    systeme = vus[0][0]["content"]
    assert "gen_x" in systeme and "EMPLOYEES : EMPLOYEE_ID, DEPARTMENT_ID" in systeme
    assert "un manager voit son service" in vus[0][1]["content"]


def test_reel_les_attaques_ne_trouvent_rien_sur_la_reference_et_trouvent_un_trou_de_manager(terrain):
    # Sous la référence : aucune attaque ne fuit. Sous un mutant où le manager voit aussi les
    # employés sans service : les attaques jouées par les managers doivent le montrer.
    from borne.preuve import rejouer_attaques
    regle = next(r for r in CATALOGUE if r.id == "service")
    meme = rejouer_attaques(terrain, regle.reference, regle.reference)
    assert {x["issue"] for x in meme} <= {"identique", "hors_perimetre", "sans_reference"}
    trou = rejouer_attaques(terrain, regle.reference, regle.mutants["null_ouvert"].source)
    assert any(x["issue"] in ("fuite", "divergence") for x in trou), trou


def test_reel_les_attaques_ratent_un_trou_que_la_comparaison_de_lignes_attrape(terrain):
    # Trouvé le 16/11/2026 : « la RH voit aussi la direction générale ». Les 20 attaques sont
    # jouées surtout par des managers, aucune ne cherche ce que la RH ne doit pas voir : elles
    # ne voient RIEN. La comparaison des lignes visibles, exhaustive, l'attrape. C'est pour
    # cela que le juge est la comparaison, et les attaques un complément.
    from borne.preuve import juger, rejouer_attaques
    regle = next(r for r in CATALOGUE if r.id == "sauf_direction")
    mutant = regle.mutants["rh_partout"].source
    assert juger(terrain, regle.reference, mutant).verdict == "trou"
    assert not any(x["issue"] in ("fuite", "divergence")
                   for x in rejouer_attaques(terrain, regle.reference, mutant))


def test_la_boucle_de_correction_rend_le_rapport_au_modele_et_s_arrete_sur_juste():
    from borne.generateur import GenerateurPolitique, generer_et_prouver
    recus = []

    class Modele:
        def completer(self, messages):
            recus.append(messages)
            return "```sql\n" + (CATALOGUE[0].mutants["null_ouvert"].source if len(recus) == 1
                                 else CATALOGUE[0].reference) + "\n```"

    def eprouver(source):
        juste = source == CATALOGUE[0].reference
        return {"verdict": "juste" if juste else "trou",
                "detail": "juste" if juste else "ESSAI_M50/EMPLOYEES : 1 en trop, 0 en moins"}
    tours = generer_et_prouver(GenerateurPolitique(Modele()), CATALOGUE[0], "gen_s",
                               {"EMPLOYEES": ["EMPLOYEE_ID"]}, eprouver, corrections=2)
    assert [t["verdict"] for t in tours] == ["trou", "juste"]
    assert "1 en trop" in recus[1][-1]["content"]          # le rapport du juge revient au modèle



def test_une_reponse_sans_fonction_est_illisible_pas_refusee():
    from borne.generateur import GenerateurPolitique, generer_et_prouver
    reponses = iter(["Je réfléchis...", "```sql\n" + CATALOGUE[0].reference + "\n```"])

    class Modele:
        def completer(self, messages):
            return next(reponses)
    tours = generer_et_prouver(GenerateurPolitique(Modele()), CATALOGUE[0], "g", {}, 
                               lambda s: {"verdict": "juste", "detail": "juste"}, corrections=2)
    assert [t["verdict"] for t in tours] == ["illisible", "juste"]
    assert "Je réfléchis" in tours[0]["detail"]


def test_le_rapport_montre_le_parcours_et_echappe_le_code():
    from borne.rapport_phase3 import construire
    page = construire([{"regle": "service", "modele": "openai/gpt-oss-20b", "verdict": "juste",
                        "detail": "juste", "attaques_fuite": [], "source": "RETURN '<b>';",
                        "historique": [{"tour": 1, "verdict": "trop_stricte", "detail": "1 en moins", "source": ""},
                                       {"tour": 2, "verdict": "juste", "detail": "juste", "source": ""}]}])
    assert "Trop stricte" in page and "Juste" in page and "1 en moins" in page
    assert "&lt;b&gt;" in page and "<b>';" not in page        # le code est échappé
