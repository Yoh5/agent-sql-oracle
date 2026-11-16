-- Les comptes. Exécuté par SYSTEM dans FREEPDB1, une instruction par bloc terminé par « / ».
-- NON VÉRIFIÉ contre une vraie base au 16/11/2026 (Docker ne démarrait pas).
-- {mdp} est remplacé par PERSONA_PASSWORD par scripts/installer.py.

-- Le gardien : propriétaire de la règle d'accès, exempté d'elle, lecteur de l'audit.
CREATE USER sec_admin IDENTIFIED BY "{mdp}" QUOTA UNLIMITED ON users
/
GRANT CREATE SESSION, CREATE TABLE, CREATE PROCEDURE, EXEMPT ACCESS POLICY, AUDIT_VIEWER TO sec_admin
/
GRANT EXECUTE ON DBMS_RLS TO sec_admin
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
