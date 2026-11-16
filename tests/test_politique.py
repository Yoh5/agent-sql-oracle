"""Le contrôle statique d'une politique candidate (code écrit par un modèle).

Défense en profondeur seulement : ce qui protège vraiment, c'est que la fonction est
créée dans ESSAI_POL, un schéma qui ne peut que lire ses profils. Mais ce qui n'a rien à
faire dans une fonction de politique est refusé avant même d'atteindre la base.
"""
import pytest

from borne.politique import ControleRefuse, controler

BONNE = """CREATE OR REPLACE FUNCTION pol_r1 (p_schema VARCHAR2, p_objet VARCHAR2)
  RETURN VARCHAR2 AS
  v_role essai_pol.profils.role%TYPE;
  v_dep  essai_pol.profils.departement_id%TYPE;
BEGIN
  SELECT role, departement_id INTO v_role, v_dep
    FROM essai_pol.profils WHERE compte = SYS_CONTEXT('USERENV', 'SESSION_USER');
  IF v_role = 'rh' THEN RETURN NULL; END IF;
  RETURN 'department_id = ' || TO_CHAR(v_dep);
EXCEPTION WHEN NO_DATA_FOUND THEN RETURN '1=0';
END;"""


def test_une_politique_ordinaire_passe_et_donne_son_nom():
    assert controler(BONNE) == "POL_R1"


@pytest.mark.parametrize("piege", [
    "EXECUTE IMMEDIATE 'GRANT DBA TO essai_m50';",          # SQL dynamique
    "DBMS_OUTPUT.PUT_LINE('x');",                            # paquet système
    "UTL_HTTP.REQUEST('http://exemple');",                   # sortie réseau
    "INSERT INTO essai_pol.profils VALUES ('X', 1, 'rh', 1);",  # écriture
    "UPDATE essai_pol.profils SET role = 'rh';",
    "DELETE FROM essai_pol.profils;",
    "COMMIT;",
    "PRAGMA AUTONOMOUS_TRANSACTION;",
    "SELECT COUNT(*) INTO v_dep FROM sys.dba_users;",         # objet de SYS
])
def test_ce_qui_n_a_rien_a_faire_dans_une_politique_est_refuse(piege):
    source = BONNE.replace("BEGIN\n", "BEGIN\n  " + piege + "\n", 1)
    with pytest.raises(ControleRefuse):
        controler(source)


def test_une_seule_fonction_et_rien_d_autre():
    with pytest.raises(ControleRefuse):
        controler(BONNE + "\n/\nCREATE OR REPLACE FUNCTION autre RETURN VARCHAR2 AS BEGIN RETURN NULL; END;")
    with pytest.raises(ControleRefuse):
        controler("CREATE OR REPLACE PROCEDURE p AS BEGIN NULL; END;")
    with pytest.raises(ControleRefuse):
        controler(BONNE.replace("RETURN VARCHAR2 AS", "RETURN NUMBER AS", 1))


def test_un_mot_interdit_cache_dans_un_commentaire_ne_trompe_pas_le_controle():
    # Les commentaires sont retirés avant le contrôle : un mot dans un commentaire ne
    # déclenche rien, et ne peut pas non plus servir à masquer du code.
    assert controler(BONNE.replace("BEGIN\n", "BEGIN\n  -- pas de DELETE ici\n", 1)) == "POL_R1"
