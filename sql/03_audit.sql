-- L'audit unifié : chaque lecture des tables HR par un compte de profil est consignée
-- par Oracle, indépendamment de ce que l'agent dit avoir fait. Exécuté par SYS (SYSDBA).

CREATE AUDIT POLICY audit_agent
  ACTIONS SELECT ON hr.employees, SELECT ON hr.job_history, SELECT ON hr.departments,
          UPDATE ON hr.employees, DELETE ON hr.employees
/
AUDIT POLICY audit_agent BY mgr_50, mgr_80, rh_dir
/
