-- La copie jetable HR_BAC et sa remise à neuf. Exécuté par SYS (SYSDBA).
-- `recreer` est une procédure de HR_BAC (droits du définisseur) : elle supprime ses
-- propres tables et les recopie depuis HR. Appelée avant chaque attaque par le banc.

CREATE OR REPLACE PROCEDURE hr_bac.recreer AUTHID DEFINER AS
BEGIN
  FOR t IN (SELECT table_name FROM user_tables) LOOP
    EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS PURGE';
  END LOOP;
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR') LOOP
    EXECUTE IMMEDIATE 'CREATE TABLE ' || t.table_name || ' AS SELECT * FROM hr.' || t.table_name;
  END LOOP;
END;
/
BEGIN
  hr_bac.recreer;
END;
/
