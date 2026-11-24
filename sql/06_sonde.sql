-- Le compte de la sonde de l'enquêteur (sentinelle/sonde.py). Exécuté par SYS (SYSDBA).
--
-- Il exécute un WHERE écrit sous l'influence de l'attaquant : il voit tous les services
-- (EXEMPT ACCESS POLICY, sinon la sonde ne verrait que ce que la VPD laisse voir) mais n'a
-- RIEN d'autre que la lecture des tables HR. La sonde ne lui demande qu'un bit.
BEGIN
  FOR u IN (SELECT username FROM dba_users WHERE username = 'SENT_SONDE') LOOP
    EXECUTE IMMEDIATE 'DROP USER sent_sonde CASCADE';
  END LOOP;
END;
/
CREATE USER sent_sonde IDENTIFIED BY "{mdp}"
/
GRANT CREATE SESSION, EXEMPT ACCESS POLICY TO sent_sonde
/
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = 'HR' AND table_name <> 'NOTES_SERVICE') LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON hr.' || t.table_name || ' TO sent_sonde';
  END LOOP;
END;
/
