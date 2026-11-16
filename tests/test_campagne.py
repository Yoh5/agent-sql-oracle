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
