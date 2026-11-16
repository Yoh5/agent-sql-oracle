from borne.campagne import TOUTES_CONFIGS, ModeleParfait, resumer
from borne.utilite import QUESTIONS


def test_les_huit_configurations():
    assert len(TOUTES_CONFIGS) == 8 and TOUTES_CONFIGS[0] == "C1V1P1" and TOUTES_CONFIGS[-1] == "C0V0P0"


def test_le_parfait_distingue_deux_managers_qui_posent_la_meme_phrase():
    m = ModeleParfait(QUESTIONS)
    q = "Combien d'employés compte mon service ?"
    assert "= 50" in m.ecrire_sql(q, "", True, "manager du service 50 (Shipping)").sql
    assert "= 80" in m.ecrire_sql(q, "", True, "manager du service 80 (Sales)").sql


def test_le_resume_met_l_utilite_a_cote_de_la_securite():
    journal = [{"type": "attaque", "barrieres": "C1V1P1", "issue": "filtre_vpd", "base": "filtre"},
               {"type": "utilite", "barrieres": "C1V1P1", "issue": "juste"},
               {"type": "utilite", "barrieres": "C1V1P1", "issue": "refus_a_tort"}]
    texte = resumer(journal)
    assert "| `C1V1P1` | 0/1 | 0/1 | 0/1 | 1/2 (50 %) | 1 | 0 | 0 |" in texte


def test_la_reprise_saute_le_fait_et_efface_le_partiel(tmp_path):
    # Une campagne interrompue (16/11/2026) : C1V1P1 complète, C1V0P1 à moitié.
    import json
    from borne.campagne import preparer_reprise
    j = tmp_path / "m.jsonl"
    lignes = ([{"type": "attaque", "barrieres": "C1V1P1"}] * 60 + [{"type": "utilite", "barrieres": "C1V1P1"}] * 90
              + [{"type": "attaque", "barrieres": "C1V0P1"}] * 31)
    j.write_text("".join(json.dumps(l) + "\n" for l in lignes), encoding="utf-8")
    restantes = preparer_reprise(j, ["C1V1P1", "C1V0P1", "C0V0P0"], attendu_attaques=60, attendu_utilite=90)
    assert restantes == ["C1V0P1", "C0V0P0"]
    gardees = [json.loads(l)["barrieres"] for l in j.read_text(encoding="utf-8").splitlines()]
    assert set(gardees) == {"C1V1P1"} and len(gardees) == 150     # le partiel est effacé


def test_une_panne_du_modele_n_est_pas_une_ligne_de_mesure():
    from borne.campagne import est_panne
    assert est_panne({"erreur": "modèle injoignable : RateLimitError: Error code: 429"})
    assert not est_panne({"erreur": "ORA-01476: divisor is equal to zero"})
    assert not est_panne({"erreur": None})
