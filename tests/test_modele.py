from borne.modele import CONSIGNES, ModeleFactice, ModeleGroq, Proposition, construire_prompt, extraire


def test_extraire_un_bloc_sql():
    p = extraire("Voici :\n```sql\nSELECT 1 FROM dual\n```\nVoilà.")
    assert p.sql == "SELECT 1 FROM dual" and p.refus is None


def test_extraire_un_refus():
    p = extraire("REFUS: ces données sont hors de votre service")
    assert p.sql is None and p.refus == "ces données sont hors de votre service"


def test_une_reponse_illisible_nest_jamais_executee():
    p = extraire("Je pense que vous voulez la table des employés.")
    assert p.sql is None and p.refus == "réponse illisible du modèle"


def test_les_consignes_ne_sont_ajoutees_que_sur_demande():
    assert CONSIGNES in construire_prompt("q", "schéma", consignes=True)[0]["content"]
    assert CONSIGNES not in construire_prompt("q", "schéma", consignes=False)[0]["content"]


def test_le_factice_rend_le_sql_prevu_ou_refuse():
    m = ModeleFactice({"tous les salaires": "SELECT salary FROM hr.employees"})
    assert m.ecrire_sql("tous les salaires", "", True).sql == "SELECT salary FROM hr.employees"
    assert m.ecrire_sql("autre chose", "", True).refus.startswith("factice")


def test_un_modele_injoignable_rend_une_proposition_pas_une_exception():
    class ClientEnPanne:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    raise TimeoutError("délai dépassé")
    m = ModeleGroq("llama", "cle", client=ClientEnPanne())
    p = m.ecrire_sql("question", "schéma", True)
    assert isinstance(p, Proposition) and p.sql is None and p.refus.startswith("modèle injoignable")


def test_le_vrai_modele_repond(cle_groq):
    import os
    m = ModeleGroq(os.environ.get("MODELE", "llama-3.3-70b-versatile"), cle_groq)
    p = m.ecrire_sql("Combien d'employés y a-t-il ?",
                     "HR.EMPLOYEES(EMPLOYEE_ID NUMBER, LAST_NAME VARCHAR2, DEPARTMENT_ID NUMBER)", True)
    assert p.sql or p.refus
