"""Installe le banc dans Autonomous Database Free (conteneur adb-free) pour la comparaison avec Select AI.

    python scripts/installer_adb.py

ADB ne donne pas SYS : tout passe par ADMIN. On recrée HR depuis adb/hr_export.json (exporté de
oracle-free, mêmes 107 employés), puis on rejoue NOS scripts sql/00, 01, 02 avec trois adaptations :
- l'espace de stockage s'appelle DATA, pas USERS ;
- le mot de passe des comptes est ADB_PERSONA_PWD (ADB impose 12 caractères, majuscule, chiffre) ;
- l'audit (sql/03) n'est pas rejoué : il n'entre pas dans la comparaison et ses droits diffèrent sur ADB.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import string
import sys
from pathlib import Path

import oracledb
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[1]
WALLET = RACINE / "adb" / "tls_wallet"
DSN = ("(description=(retry_count=2)(retry_delay=3)(address=(protocol=tcps)(port=1532)(host=localhost))"
       "(connect_data=(service_name=myatp_low.adb.oraclecloud.com))(security=(ssl_server_dn_match=no)))")


def connecter(user: str, mdp: str):
    return oracledb.connect(user=user, password=mdp, dsn=DSN, config_dir=str(WALLET),
                            wallet_location=str(WALLET), wallet_password=os.environ["ADB_WALLET_PWD"])


def mdp_persona() -> str:
    env = RACINE / ".env"
    t = env.read_text(encoding="utf-8")
    m = re.search(r"^ADB_PERSONA_PWD=(.+)$", t, re.M)
    if m:
        return m.group(1).strip()
    v = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(18)) + "Kq7_"
    env.write_text(t.rstrip("\n") + f"\nADB_PERSONA_PWD={v}\n", encoding="utf-8")
    return v


TYPES = {"NUMBER": lambda c: "NUMBER" + (f"({c[3]},{c[4] or 0})" if c[3] else ""),
         "VARCHAR2": lambda c: f"VARCHAR2({c[2]})", "CHAR": lambda c: f"CHAR({c[2]})", "DATE": lambda c: "DATE"}
CLES = {"REGIONS": "region_id", "COUNTRIES": "country_id", "LOCATIONS": "location_id", "DEPARTMENTS": "department_id",
        "JOBS": "job_id", "EMPLOYEES": "employee_id"}


def creer_hr(cur, export: dict) -> None:
    cur.execute("""BEGIN FOR u IN (SELECT username FROM dba_users WHERE username = 'HR') LOOP
                     EXECUTE IMMEDIATE 'DROP USER hr CASCADE'; END LOOP; END;""")
    cur.execute("CREATE USER hr NO AUTHENTICATION QUOTA UNLIMITED ON data")
    for table, d in export.items():
        cols = ", ".join(f"{c[0]} {TYPES[c[1]](c)}{'' if c[5] == 'Y' else ' NOT NULL'}" for c in d["colonnes"])
        cle = f", CONSTRAINT pk_{table.lower()} PRIMARY KEY ({CLES[table]})" if table in CLES else ""
        cur.execute(f"CREATE TABLE hr.{table} ({cols}{cle})")
        noms = [c[0] for c in d["colonnes"]]
        dates = {i for i, c in enumerate(d["colonnes"]) if c[1] == "DATE"}
        vals = ", ".join(f"TO_DATE(SUBSTR(:{i + 1}, 1, 10), 'YYYY-MM-DD')" if i in dates else f":{i + 1}" for i in range(len(noms)))
        if d["lignes"]:
            cur.executemany(f"INSERT INTO hr.{table} ({', '.join(noms)}) VALUES ({vals})", d["lignes"])
        print(f"  hr.{table} : {len(d['lignes'])} lignes")


def blocs(sql: str):
    """Les instructions d'un de NOS scripts, séparées par « / » seul sur sa ligne."""
    for b in re.split(r"^\s*/\s*$", sql, flags=re.M):
        b = "\n".join(l for l in b.splitlines() if not l.strip().startswith("--")).strip()
        if b:
            yield b if b.upper().startswith(("BEGIN", "DECLARE", "CREATE OR REPLACE")) else b.rstrip(";")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(RACINE / ".env")
    mdp = mdp_persona()
    c = connecter("admin", os.environ["ADB_ADMIN_PWD"])
    cur = c.cursor()
    creer_hr(cur, json.loads((RACINE / "adb" / "hr_export.json").read_text(encoding="utf-8")))
    c.commit()
    for f in ("00_comptes.sql", "01_hr_bac.sql", "02_vpd.sql"):
        texte = (RACINE / "sql" / f).read_text(encoding="utf-8").replace("{mdp}", mdp)
        texte = re.sub(r"\bON\s+users\b", "ON data", texte, flags=re.I)
        texte = texte.replace(", AUDIT_VIEWER", "")      # rôle propre à l'audit, non rejoué ici
        ok = ko = 0
        for b in blocs(texte):
            try:
                cur.execute(b)
                ok += 1
            except oracledb.DatabaseError as e:
                ko += 1
                print(f"  {f} : {str(e).splitlines()[0][:150]}\n      ← {b[:110]!r}")
        c.commit()
        print(f"  {f} : {ok} instructions passées, {ko} en erreur")
    print("  politiques VPD :", cur.execute("SELECT object_name, policy_name FROM dba_policies WHERE object_owner='HR'").fetchall())
    for compte in ("MGR_50", "MGR_80", "RH_DIR"):
        with connecter(compte, mdp) as cc:
            n = cc.cursor().execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        print(f"  {compte} voit {n} employés")
    return 0


if __name__ == "__main__":
    sys.exit(main())
