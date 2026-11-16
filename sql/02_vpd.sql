-- La règle d'accès par ligne (VPD). Exécuté par SYSTEM.
-- NON VÉRIFIÉ contre une vraie base au 16/11/2026.
--
-- Elle lit le compte CONNECTÉ (SESSION_USER), qu'aucune requête ne peut changer —
-- pas un contexte de session qu'un bloc PL/SQL écrit par le modèle pourrait poser.
-- Un compte inconnu ne voit RIEN (« 1=0 ») : on refuse par défaut.

CREATE OR REPLACE FUNCTION sec_admin.vpd_emp (p_schema VARCHAR2, p_objet VARCHAR2)
  RETURN VARCHAR2 AS
  v_compte VARCHAR2(128) := SYS_CONTEXT('USERENV', 'SESSION_USER');
  v_role   sec_admin.profils.role%TYPE;
  v_dep    sec_admin.profils.departement_id%TYPE;
BEGIN
  IF v_compte IN ('HR', 'SYS', 'SYSTEM', 'HR_BAC') THEN
    RETURN NULL;                      -- propriétaire, administration, copie jetable
  END IF;
  SELECT role, departement_id INTO v_role, v_dep
    FROM sec_admin.profils WHERE compte = v_compte;
  IF v_role = 'rh' THEN
    RETURN NULL;
  END IF;
  RETURN 'department_id = ' || TO_CHAR(v_dep);
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RETURN '1=0';
END;
/
BEGIN
  DBMS_RLS.ADD_POLICY(object_schema => 'HR', object_name => 'EMPLOYEES', policy_name => 'VPD_EMP',
                      function_schema => 'SEC_ADMIN', policy_function => 'VPD_EMP',
                      statement_types => 'SELECT, INSERT, UPDATE, DELETE', update_check => TRUE);
  DBMS_RLS.ADD_POLICY(object_schema => 'HR', object_name => 'JOB_HISTORY', policy_name => 'VPD_JOB',
                      function_schema => 'SEC_ADMIN', policy_function => 'VPD_EMP',
                      statement_types => 'SELECT, INSERT, UPDATE, DELETE', update_check => TRUE);
END;
/
