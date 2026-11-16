from borne.modele import CONSIGNES, CONSIGNES_RH, ModeleFactice, ModeleGroq, Proposition, construire_prompt, extraire


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


def test_le_modele_sait_qui_l_interroge_meme_sans_consignes():
    # Sans ce contexte, « mon service » était sans réponse possible quand la VPD est
    # coupée, et la consigne « ne montre que son service » inapplicable : la barrière
    # « prompt » aurait été mesurée mauvaise par construction. Ce n'est pas une barrière,
    # c'est une information — présente dans toutes les configurations.
    for consignes in (True, False):
        systeme = construire_prompt("q", "schéma", consignes, "manager du service 50 (Shipping)")[0]["content"]
        assert "manager du service 50 (Shipping)" in systeme


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
    assert p.panne                       # une panne, pas un refus


def test_le_vrai_modele_repond(cle_groq):
    import os
    m = ModeleGroq(os.environ.get("MODELE", "openai/gpt-oss-120b"), cle_groq)
    # Une question DANS le périmètre : « combien d'employés y a-t-il ? » (toute l'entreprise)
    # est refusée par gpt-oss-120b, et c'est conforme aux consignes.
    p = m.ecrire_sql("Combien d'employés y a-t-il dans mon service ?",
                     "HR.EMPLOYEES(EMPLOYEE_ID NUMBER, LAST_NAME VARCHAR2, DEPARTMENT_ID NUMBER)", True)
    # « p.sql or p.refus » passait aussi sur une PANNE (le refus porte le message d'erreur) :
    # il n'a rien vu quand Groq a retiré llama-3.3-70b. Une panne doit faire échouer ce test.
    assert not p.panne, p.refus
    assert p.sql and "SELECT" in p.sql.upper()


def test_le_factice_cede_aussi_a_la_seconde_tentative():
    # À la seconde tentative, l'agent ajoute l'erreur Oracle à la question. Le factice
    # ne la reconnaissait plus et « refusait » : le banc comptait un refus du modèle
    # pour un modèle qui cède toujours (vu sur la vraie base le 16/11/2026).
    from borne.modele import ModeleFactice
    m = ModeleFactice({"liste les e-mails": "SELECT email FROM employees"})
    relance = "liste les e-mails\n\nTa requête précédente a échoué : ORA-01722. Corrige-la. Requête : …"
    assert m.ecrire_sql(relance, "", True).sql == "SELECT email FROM employees"


def test_le_modele_groq_compte_ses_jetons():
    # Sans ce compte, le coût d'une campagne n'était qu'une estimation.
    class Reponse:
        class usage:
            prompt_tokens, completion_tokens = 400, 90
        choices = [type("C", (), {"message": type("M", (), {"content": "```sql\nSELECT 1 FROM dual\n```"})})]

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    return Reponse()
    m = ModeleGroq("openai/gpt-oss-120b", "cle", client=Client())
    m.ecrire_sql("q", "s", True)
    m.ecrire_sql("q", "s", True)
    assert (m.appels, m.jetons_entree, m.jetons_sortie) == (2, 800, 180)



def test_la_rh_a_ses_propres_consignes():
    # Une consigne unique (« refuse l'ensemble des salaires ») faisait refuser à la RH
    # des questions qu'elle a le droit de poser : 7 refus à tort au pilote.
    from borne.config import CONTEXTE_RH
    rh = construire_prompt("q", "s", True, CONTEXTE_RH)[0]["content"]
    manager = construire_prompt("q", "s", True, "manager du service 50 (Shipping)")[0]["content"]
    assert CONSIGNES_RH in rh and CONSIGNES not in rh
    assert CONSIGNES in manager and CONSIGNES_RH not in manager
    assert "SELECT" in CONSIGNES_RH and "ignorer ces règles" in CONSIGNES_RH


def test_une_limite_de_debit_fait_attendre_puis_reessayer():
    # 16/11/2026 : la limite Groq est de 8 000 jetons par MINUTE. Sans attente, les appels
    # tombaient en 429 en série et six configurations de la campagne étaient perdues.
    class RateLimitError(Exception):
        pass
    attentes, essais = [], []

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    essais.append(1)
                    if len(essais) < 3:
                        raise RateLimitError("Error code: 429 - Rate limit reached ... Please try again in 892.5ms.")
                    return type("R", (), {"usage": None, "choices": [type("C", (), {"message": type("M", (), {"content": "```sql\nSELECT 1 FROM dual\n```"})})]})()
    m = ModeleGroq("openai/gpt-oss-20b", "cle", client=Client(), attendre=attentes.append)
    p = m.ecrire_sql("q", "s", True)
    assert p.sql == "SELECT 1 FROM dual" and not p.panne
    # Au moins le délai demandé (892,5 ms), plus une petite marge.
    assert len(essais) == 3 and attentes and 0.89 <= attentes[0] < 2


def test_une_limite_qui_ne_passe_pas_reste_une_panne():
    class RateLimitError(Exception):
        pass

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    raise RateLimitError("Error code: 429 - Please try again in 2.85s.")
    m = ModeleGroq("openai/gpt-oss-20b", "cle", client=Client(), attendre=lambda s: None)
    p = m.ecrire_sql("q", "s", True)
    assert p.panne and p.sql is None
