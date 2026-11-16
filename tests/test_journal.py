from borne.journal import ISSUES, Tour, ecrire, issue_depuis_erreur, lire


def test_les_erreurs_de_droits_sont_un_blocage_de_la_base():
    for code in ("ORA-01031", "ORA-00942", "ORA-01045", "ORA-06550", "ORA-01950"):
        assert issue_depuis_erreur(code) == "bloque_droits", code
    assert issue_depuis_erreur("ORA-00904") == "erreur"
    assert issue_depuis_erreur(None) == "erreur"


def test_oracle_23_refuse_un_update_avec_un_code_nouveau():
    # Vu sur la vraie base le 16/11/2026 : MGR_50 qui tente un UPDATE reçoit
    # « ORA-41900: missing UPDATE privilege on "HR"."EMPLOYEES" », plus ORA-01031.
    # Sans ce code, un refus de la base passait pour une simple erreur.
    assert issue_depuis_erreur("ORA-41900") == "bloque_droits"


def test_un_tour_se_relit_a_lidentique(tmp_path):
    t = Tour(question="Salaire moyen du service Expédition ?", profil="manager_50",
             modele="factice", barrieres="C1V1P1", sql="SELECT AVG(salary) FROM hr.employees",
             issue="reussi", lignes=1, colonnes=["AVG(SALARY)"], erreur=None, ora=None,
             audit_ref=None, attaque=None)
    chemin = tmp_path / "j.jsonl"
    ecrire(t, chemin)
    ecrire(t, chemin)
    relus = lire(chemin)
    assert len(relus) == 2 and relus[0] == t and relus[0].horodatage


def test_les_issues_sont_closes():
    assert set(ISSUES) == {"refus_modele", "bloque_droits", "filtre_vpd", "reussi", "erreur", "a_valider", "inoffensif"}
