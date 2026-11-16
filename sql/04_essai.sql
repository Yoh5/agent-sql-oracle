-- Phase 3 : le terrain d'essai des politiques générées. Exécuté par SYS (SYSDBA).
-- {mdp} est remplacé par PERSONA_PASSWORD par scripts/installer.py.
--
-- Une politique candidate n'est JAMAIS posée sur HR. Elle l'est sur HR_ESSAI, une copie,
-- interrogée par des comptes de test qui ne voient que la copie. La fonction de politique
-- vit dans ESSAI_POL, un schéma qui ne peut que lire sa table de profils : en droits du
-- définisseur, même une fonction malveillante ne peut que rendre un prédicat.

-- Remise à zéro (supprimer un utilisateur CASCADE retire aussi ses tables et les
-- politiques posées dessus).
BEGIN
  FOR u IN (SELECT username FROM dba_users
             WHERE username IN ('ESSAI_M50', 'ESSAI_M80', 'ESSAI_RH', 'ESSAI_X', 'HR_ESSAI', 'ESSAI_POL')) LOOP
    EXECUTE IMMEDIATE 'DROP USER ' || u.username || ' CASCADE';
  END LOOP;
END;
/

-- La copie : les tables de HR, données comprises.
CREATE USER hr_essai NO AUTHENTICATION QUOTA UNLIMITED ON users
/
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR') LOOP
    EXECUTE IMMEDIATE 'CREATE TABLE hr_essai.' || t.table_name || ' AS SELECT * FROM hr.' || t.table_name;
  END LOOP;
END;
/

-- Le propriétaire des fonctions de politique : se connecter, créer une fonction, lire SES
-- profils. Rien d'autre — aucune table de HR_ESSAI, aucun paquet système.
CREATE USER essai_pol IDENTIFIED BY "{mdp}" QUOTA 10M ON users
/
GRANT CREATE SESSION, CREATE PROCEDURE TO essai_pol
/
CREATE TABLE essai_pol.profils (
  compte          VARCHAR2(30) PRIMARY KEY,
  departement_id  NUMBER(4),
  role            VARCHAR2(10) NOT NULL CHECK (role IN ('manager', 'rh')),
  employee_id     NUMBER(6)
)
/
-- Les managers des services 50 (Fripp, 121) et 80 (Russell, 145) ; la RH (Mavris, 203).
INSERT INTO essai_pol.profils VALUES ('ESSAI_M50', 50, 'manager', 121)
/
INSERT INTO essai_pol.profils VALUES ('ESSAI_M80', 80, 'manager', 145)
/
INSERT INTO essai_pol.profils VALUES ('ESSAI_RH', 40, 'rh', 203)
/
COMMIT
/

-- Les comptes de test : lecture de la copie, par des synonymes, et rien d'autre.
-- ESSAI_X n'a PAS de profil : une politique qui oublie de refuser par défaut lui montre
-- tout, et sans lui ce trou serait invisible au juge.
BEGIN
  FOR c IN (SELECT 'ESSAI_M50' n FROM dual UNION ALL SELECT 'ESSAI_M80' FROM dual
            UNION ALL SELECT 'ESSAI_RH' FROM dual UNION ALL SELECT 'ESSAI_X' FROM dual) LOOP
    EXECUTE IMMEDIATE 'CREATE USER ' || c.n || ' IDENTIFIED BY "{mdp}"';
    EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO ' || c.n;
    FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR_ESSAI') LOOP
      EXECUTE IMMEDIATE 'GRANT SELECT ON hr_essai.' || t.table_name || ' TO ' || c.n;
      EXECUTE IMMEDIATE 'CREATE SYNONYM ' || c.n || '.' || t.table_name || ' FOR hr_essai.' || t.table_name;
    END LOOP;
  END LOOP;
END;
/

-- Le gardien lit la copie (vérité du juge) ; il pose et retire les politiques candidates.
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR_ESSAI') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON hr_essai.' || t.table_name || ' TO sec_admin';
  END LOOP;
END;
/
