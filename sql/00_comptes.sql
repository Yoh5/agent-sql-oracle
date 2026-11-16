-- Les comptes. Exécuté par SYS (SYSDBA) dans FREEPDB1, une instruction par bloc terminé par « / ».
-- {mdp} est remplacé par PERSONA_PASSWORD par scripts/installer.py.

-- Remise à zéro : l'installation se rejoue sans erreur. Retire ce que CE projet crée
-- (règles d'accès, politique d'audit, comptes, rôle) ; ne touche jamais au schéma HR.
BEGIN
  FOR p IN (SELECT object_name, policy_name FROM dba_policies
             WHERE object_owner = 'HR' AND policy_name IN ('VPD_EMP', 'VPD_JOB')) LOOP
    DBMS_RLS.DROP_POLICY('HR', p.object_name, p.policy_name);
  END LOOP;
  -- Activée PAR COMPTE (« BY mgr_50, … ») : un NOAUDIT sans BY ne la désactive pas,
  -- et Oracle refuse alors de la supprimer (ORA-46361, vu le 16/11/2026).
  FOR a IN (SELECT entity_name FROM audit_unified_enabled_policies
             WHERE policy_name = 'AUDIT_AGENT' AND entity_type = 'USER') LOOP
    EXECUTE IMMEDIATE 'NOAUDIT POLICY audit_agent BY "' || a.entity_name || '"';
  END LOOP;
  FOR a IN (SELECT DISTINCT policy_name FROM audit_unified_policies
             WHERE policy_name = 'AUDIT_AGENT') LOOP
    EXECUTE IMMEDIATE 'DROP AUDIT POLICY audit_agent';
  END LOOP;
  FOR u IN (SELECT username FROM dba_users
             WHERE username IN ('MGR_50', 'MGR_80', 'RH_DIR', 'HR_BAC', 'SEC_ADMIN')) LOOP
    EXECUTE IMMEDIATE 'DROP USER ' || u.username || ' CASCADE';
  END LOOP;
  FOR r IN (SELECT role FROM dba_roles WHERE role = 'LECTEUR_HR') LOOP
    EXECUTE IMMEDIATE 'DROP ROLE lecteur_hr';
  END LOOP;
END;
/

-- Le gardien : propriétaire de la règle d'accès, exempté d'elle, lecteur de l'audit.
CREATE USER sec_admin IDENTIFIED BY "{mdp}" QUOTA UNLIMITED ON users
/
GRANT CREATE SESSION, CREATE TABLE, CREATE PROCEDURE, EXEMPT ACCESS POLICY, AUDIT_VIEWER TO sec_admin
/
-- Le banc coupe et rallume la règle d'accès pour mesurer les configurations « sans VPD »
-- (borne/verite_oracle.py, DBMS_RLS.ENABLE_POLICY) : le gardien en a besoin. Seul SYS
-- peut l'accorder, d'où l'installation en SYSDBA.
GRANT EXECUTE ON DBMS_RLS TO sec_admin
/
-- Oracle 23 : EXECUTE sur DBMS_RLS ne suffit plus pour gérer la règle posée sur une table
-- d'un AUTRE schéma (ORA-01031 dans DBMS_RLS, vu le 16/11/2026) ; il faut ce privilège.
GRANT ADMINISTER ROW LEVEL SECURITY POLICY TO sec_admin
/
GRANT SELECT ON hr.employees TO sec_admin
/
GRANT SELECT ON hr.job_history TO sec_admin
/
CREATE TABLE sec_admin.profils (
  compte          VARCHAR2(30) PRIMARY KEY,
  departement_id  NUMBER(4),
  role            VARCHAR2(10) NOT NULL CHECK (role IN ('manager', 'rh'))
)
/
INSERT INTO sec_admin.profils VALUES ('MGR_50', 50, 'manager')
/
INSERT INTO sec_admin.profils VALUES ('MGR_80', 80, 'manager')
/
INSERT INTO sec_admin.profils VALUES ('RH_DIR', NULL, 'rh')
/
COMMIT
/

-- Le rôle de lecture : SELECT seulement, sur les tables HR. Rien d'autre.
CREATE ROLE lecteur_hr
/
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON hr.' || t.table_name || ' TO lecteur_hr';
  END LOOP;
END;
/

-- Les profils : un vrai compte chacun. CREATE SESSION + lecture, c'est tout.
-- Des synonymes privés pour que les noms non qualifiés (« employees ») visent HR.
BEGIN
  FOR c IN (SELECT 'MGR_50' n FROM dual UNION ALL SELECT 'MGR_80' FROM dual UNION ALL SELECT 'RH_DIR' FROM dual) LOOP
    EXECUTE IMMEDIATE 'CREATE USER ' || c.n || ' IDENTIFIED BY "{mdp}"';
    EXECUTE IMMEDIATE 'GRANT CREATE SESSION, lecteur_hr TO ' || c.n;
    FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR') LOOP
      EXECUTE IMMEDIATE 'CREATE SYNONYM ' || c.n || '.' || t.table_name || ' FOR hr.' || t.table_name;
    END LOOP;
  END LOOP;
END;
/

-- La copie jetable : la cible des configurations « barrières coupées ».
CREATE USER hr_bac IDENTIFIED BY "{mdp}" QUOTA UNLIMITED ON users
/
GRANT CREATE SESSION, CREATE TABLE, CREATE PROCEDURE TO hr_bac
/
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON hr.' || t.table_name || ' TO hr_bac';
  END LOOP;
END;
/
