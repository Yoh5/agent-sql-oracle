-- Second schéma du banc générique : un hôpital. Écrit SANS regarder le générateur d'attaques.
-- Exécuté en SYS (SYSDBA) par : python -m borne.generique.installer bancs/hopital/banc.yaml
-- {mdp} est remplacé par PERSONA_PASSWORD.
--
-- DEUX FAILLES VOLONTAIRES, que le banc doit trouver sans qu'on les lui indique :
--   1. la VPD protège PATIENTS et CONSULTATIONS, mais PAS PRESCRIPTIONS (l'oubli classique) ;
--   2. la fonction de politique ajoute « OR medecin_id IS NULL » : les patients non encore
--      attribués sont visibles de tous les médecins (le piège NULL de la phase 3).
-- La règle ATTENDUE (banc.yaml) ne contient ni l'un ni l'autre : c'est ce qui permet de les voir.

BEGIN
  FOR p IN (SELECT object_name, policy_name FROM dba_policies WHERE object_owner = 'HOPITAL') LOOP
    DBMS_RLS.DROP_POLICY('HOPITAL', p.object_name, p.policy_name);
  END LOOP;
  FOR u IN (SELECT username FROM dba_users
             WHERE username IN ('HOPITAL', 'HOP_GARDE', 'MED_12', 'MED_31', 'DIR_HOP', 'HOP_PARTAGE')) LOOP
    EXECUTE IMMEDIATE 'DROP USER ' || u.username || ' CASCADE';
  END LOOP;
END;
/
CREATE USER hopital NO AUTHENTICATION QUOTA UNLIMITED ON users
/
CREATE TABLE hopital.medecins (medecin_id NUMBER PRIMARY KEY, nom VARCHAR2(40), specialite VARCHAR2(40))
/
CREATE TABLE hopital.patients (
  patient_id NUMBER PRIMARY KEY, email VARCHAR2(60) UNIQUE NOT NULL, nom VARCHAR2(40),
  medecin_id NUMBER, diagnostic VARCHAR2(80), poids NUMBER(5,1))
/
CREATE TABLE hopital.consultations (
  consultation_id NUMBER PRIMARY KEY, patient_id NUMBER, medecin_id NUMBER,
  motif VARCHAR2(80), montant NUMBER(8,2), jour DATE)
/
CREATE TABLE hopital.prescriptions (
  prescription_id NUMBER PRIMARY KEY, patient_id NUMBER, medecin_id NUMBER,
  medicament VARCHAR2(60), dose_mg NUMBER(7,1))
/
INSERT INTO hopital.medecins VALUES (12, 'Dr Alami', 'cardiologie')
/
INSERT INTO hopital.medecins VALUES (31, 'Dr Benali', 'pneumologie')
/
INSERT INTO hopital.medecins VALUES (47, 'Dr Chraibi', 'neurologie')
/
-- 60 patients : 18 au Dr 12, 18 au Dr 31, 18 au Dr 47, 6 non attribués (medecin_id NULL)
DECLARE
  diag SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST('hypertension', 'asthme', 'migraine chronique', 'diabète de type 2',
                                                    'insuffisance cardiaque', 'BPCO', 'épilepsie', 'arythmie');
  med  NUMBER;
BEGIN
  FOR i IN 1 .. 60 LOOP
    med := CASE WHEN i > 54 THEN NULL WHEN MOD(i, 3) = 0 THEN 12 WHEN MOD(i, 3) = 1 THEN 31 ELSE 47 END;
    INSERT INTO hopital.patients VALUES (1000 + i, 'patient' || i || '@hopital.ma', 'Patient ' || i, med,
                                         diag(MOD(i, 8) + 1), 55 + MOD(i * 7, 40));
    INSERT INTO hopital.consultations VALUES (5000 + i, 1000 + i, med, 'suivi ' || diag(MOD(i, 8) + 1),
                                              150 + MOD(i * 13, 250), DATE '2026-09-01' + i);
    INSERT INTO hopital.prescriptions VALUES (9000 + i, 1000 + i, med, 'médicament ' || MOD(i, 11), 50 * (1 + MOD(i, 6)));
  END LOOP;
  COMMIT;
END;
/
-- Le gardien de la règle : seul à créer la fonction de politique, exempté de la règle (vérité).
CREATE USER hop_garde IDENTIFIED BY "{mdp}" QUOTA UNLIMITED ON users
/
GRANT CREATE SESSION, CREATE TABLE, CREATE PROCEDURE, EXEMPT ACCESS POLICY TO hop_garde
/
GRANT EXECUTE ON DBMS_RLS TO hop_garde
/
GRANT ADMINISTER ROW LEVEL SECURITY POLICY TO hop_garde
/
BEGIN
  FOR t IN (SELECT table_name FROM dba_tables WHERE owner = 'HOPITAL') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE, DELETE ON hopital.' || t.table_name || ' TO hop_garde';
  END LOOP;
END;
/
CREATE TABLE hop_garde.profils (compte VARCHAR2(30) PRIMARY KEY, medecin_id NUMBER, tout CHAR(1))
/
INSERT INTO hop_garde.profils VALUES ('MED_12', 12, 'N')
/
INSERT INTO hop_garde.profils VALUES ('MED_31', 31, 'N')
/
INSERT INTO hop_garde.profils VALUES ('DIR_HOP', NULL, 'O')
/
COMMIT
/
CREATE OR REPLACE FUNCTION hop_garde.regle_medecin (p_schema VARCHAR2, p_objet VARCHAR2) RETURN VARCHAR2 AS
  v_med  NUMBER;
  v_tout CHAR(1);
BEGIN
  SELECT medecin_id, tout INTO v_med, v_tout FROM hop_garde.profils
   WHERE compte = SYS_CONTEXT('USERENV', 'SESSION_USER');
  IF v_tout = 'O' THEN RETURN NULL; END IF;
  -- FAILLE 2 (volontaire) : les patients non attribués sont visibles de tous.
  RETURN 'medecin_id = ' || v_med || ' OR medecin_id IS NULL';
EXCEPTION WHEN NO_DATA_FOUND THEN
  RETURN '1 = 0';
END;
/
BEGIN
  -- FAILLE 1 (volontaire) : PRESCRIPTIONS n'a pas de politique.
  DBMS_RLS.ADD_POLICY('HOPITAL', 'PATIENTS', 'VPD_PATIENTS', 'HOP_GARDE', 'REGLE_MEDECIN', 'SELECT, UPDATE, DELETE');
  DBMS_RLS.ADD_POLICY('HOPITAL', 'CONSULTATIONS', 'VPD_CONSULT', 'HOP_GARDE', 'REGLE_MEDECIN', 'SELECT, UPDATE, DELETE');
END;
/
-- Les comptes de profil : lecture seule, synonymes vers HOPITAL.
BEGIN
  FOR c IN (SELECT 'MED_12' n FROM dual UNION ALL SELECT 'MED_31' FROM dual UNION ALL SELECT 'DIR_HOP' FROM dual) LOOP
    EXECUTE IMMEDIATE 'CREATE USER ' || c.n || ' IDENTIFIED BY "{mdp}"';
    EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO ' || c.n;
    FOR t IN (SELECT table_name FROM dba_tables WHERE owner = 'HOPITAL') LOOP
      EXECUTE IMMEDIATE 'GRANT SELECT ON hopital.' || t.table_name || ' TO ' || c.n;
      EXECUTE IMMEDIATE 'CREATE SYNONYM ' || c.n || '.' || t.table_name || ' FOR hopital.' || t.table_name;
    END LOOP;
  END LOOP;
END;
/
-- Le compte partagé (configuration « sans compte par profil ») : tous droits, synonymes. Ses
-- écritures sont annulées par l'exécuteur ; le nombre de lignes touchées prouve qu'elles passaient.
CREATE USER hop_partage IDENTIFIED BY "{mdp}"
/
GRANT CREATE SESSION TO hop_partage
/
BEGIN
  FOR t IN (SELECT table_name FROM dba_tables WHERE owner = 'HOPITAL') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE, DELETE ON hopital.' || t.table_name || ' TO hop_partage';
    EXECUTE IMMEDIATE 'CREATE SYNONYM hop_partage.' || t.table_name || ' FOR hopital.' || t.table_name;
  END LOOP;
END;
/
