-- Chargement NON INTERACTIF du schéma HR officiel (oracle-samples/db-sample-schemas).
-- Exécuté par SQL*Plus DANS le conteneur, connecté en SYSTEM sur FREEPDB1, depuis le
-- dossier human_resources copié dans /tmp/hr. {mdp} est remplacé par l'installateur.
--
-- Pourquoi pas hr_install.sql : il pose ses questions par ACCEPT (dont un mot de passe
-- masqué) et ne se pilote pas de façon fiable par l'entrée standard — au premier essai
-- réel (16/11/2026) il s'arrêtait après la question du tablespace. Ce fichier refait
-- exactement ses étapes, sans question.
WHENEVER SQLERROR EXIT SQL.SQLCODE
SET FEEDBACK OFF
SET DEFINE OFF

DECLARE
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM all_users WHERE username = 'HR';
  IF n > 0 THEN
    EXECUTE IMMEDIATE 'DROP USER HR CASCADE';
  END IF;
END;
/

CREATE USER hr IDENTIFIED BY "{mdp}" DEFAULT TABLESPACE users QUOTA UNLIMITED ON users;

GRANT CREATE MATERIALIZED VIEW, CREATE PROCEDURE, CREATE SEQUENCE, CREATE SESSION,
      CREATE SYNONYM, CREATE TABLE, CREATE TRIGGER, CREATE TYPE, CREATE VIEW TO hr;

ALTER SESSION SET CURRENT_SCHEMA = HR;
ALTER SESSION SET NLS_LANGUAGE = American;
ALTER SESSION SET NLS_TERRITORY = America;

SET DEFINE ON
@@hr_create.sql
@@hr_populate.sql
@@hr_code.sql

SET HEADING ON
SET FEEDBACK OFF
SELECT 'regions' t, 5 attendu, COUNT(*) reel FROM hr.regions
UNION ALL SELECT 'countries', 25, COUNT(*) FROM hr.countries
UNION ALL SELECT 'departments', 27, COUNT(*) FROM hr.departments
UNION ALL SELECT 'locations', 23, COUNT(*) FROM hr.locations
UNION ALL SELECT 'employees', 107, COUNT(*) FROM hr.employees
UNION ALL SELECT 'jobs', 19, COUNT(*) FROM hr.jobs
UNION ALL SELECT 'job_history', 10, COUNT(*) FROM hr.job_history;
EXIT
