"""Installer la base du projet dans le conteneur Oracle Free.

    python scripts/installer.py --hr      # charge le schéma HR (dépôt officiel d'Oracle)
    python scripts/installer.py --tout    # comptes, copie jetable, VPD, audit
    python scripts/installer.py --bac     # remet la copie jetable à neuf

NON VÉRIFIÉ contre une vraie base au 16/11/2026 (Docker ne démarrait pas sur le
poste). Le chargement de HR passe par SQL*Plus DANS le conteneur, parce que les
scripts officiels sont écrits pour lui (invites, `@`) ; le reste passe par
`python-oracledb`, un bloc à la fois (séparateur : une ligne « / »).
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[1]
CONTENEUR = "oracle-free"
DEPOT_SCHEMAS = "https://github.com/oracle-samples/db-sample-schemas/archive/refs/heads/main.zip"
SCRIPTS = ["00_comptes.sql", "01_hr_bac.sql", "02_vpd.sql", "03_audit.sql"]


def blocs(texte: str):
    """Les instructions d'un script, séparées par une ligne « / » seule."""
    courant = []
    for ligne in texte.splitlines():
        if ligne.strip() == "/":
            bloc = "\n".join(courant).strip()
            if bloc:
                yield bloc
            courant = []
        elif courant or (ligne.strip() and not ligne.strip().startswith("--")):
            # Les commentaires et lignes vides EN TÊTE de bloc sont retirés : un
            # bloc PL/SQL doit commencer par BEGIN, sinon le pilote le classe mal.
            courant.append(ligne)
    reste = "\n".join(courant).strip()
    if reste:
        raise ValueError(f"bloc non terminé par « / » : {reste[:60]}…")


def charger_hr(mdp_systeme: str, mdp_hr: str) -> None:
    dossier = RACINE / ".schemas"
    if not (dossier / "human_resources").exists():
        with urllib.request.urlopen(DEPOT_SCHEMAS, timeout=60) as r:
            zipfile.ZipFile(io.BytesIO(r.read())).extractall(dossier)
        racine = next(dossier.glob("db-sample-schemas-*"))
        racine.joinpath("human_resources").rename(dossier / "human_resources")
    # Copie fraîche (un `docker cp` vers un dossier existant l'imbriquerait), rendue à
    # l'utilisateur oracle : copiée en root, SQL*Plus ne pouvait rien y écrire.
    subprocess.run(["docker", "exec", "-u", "root", CONTENEUR, "rm", "-rf", "/tmp/hr"], check=True)
    subprocess.run(["docker", "cp", str(dossier / "human_resources"), f"{CONTENEUR}:/tmp/hr"], check=True)
    # Le chargeur non interactif (voir sql/hr_charger.sql : hr_install.sql pose des questions).
    chargeur = (RACINE / "sql" / "hr_charger.sql").read_text(encoding="utf-8").replace("{mdp}", mdp_hr)
    subprocess.run(["docker", "exec", "-i", "-u", "root", CONTENEUR, "sh", "-c",
                    "cat > /tmp/hr/hr_charger.sql && chown -R oracle:oinstall /tmp/hr"],
                   input=chargeur, text=True, check=True)
    subprocess.run(["docker", "exec", "-w", "/tmp/hr", CONTENEUR, "sqlplus", "-S",
                    f"system/{mdp_systeme}@FREEPDB1", "@hr_charger.sql"], check=True)


def executer_scripts(dsn: str, mdp_systeme: str, mdp: str, noms) -> None:
    import oracledb
    # SYS en SYSDBA : SYSTEM ne peut pas accorder de droits sur les objets de SYS
    # (DBMS_RLS, rôle AUDIT_VIEWER) — ORA-01031 au premier passage réel, 16/11/2026.
    with oracledb.connect(user="sys", password=mdp_systeme, dsn=dsn,
                          mode=oracledb.AUTH_MODE_SYSDBA) as c:
        cur = c.cursor()
        for nom in noms:
            for bloc in blocs((RACINE / "sql" / nom).read_text(encoding="utf-8").replace("{mdp}", mdp)):
                try:
                    cur.execute(bloc)
                except oracledb.DatabaseError as e:
                    # Dire QUELLE instruction a échoué, sans montrer le mot de passe.
                    print(f"  {nom} : ÉCHEC sur « {bloc.replace(mdp, '***')[:120]} »")
                    raise SystemExit(str(e).splitlines()[0]) from None
            print(f"  {nom} : fait")
        c.commit()


def main(argv=None) -> int:
    load_dotenv(RACINE / ".env")
    p = argparse.ArgumentParser(prog="python scripts/installer.py")
    p.add_argument("--hr", action="store_true")
    p.add_argument("--tout", action="store_true")
    p.add_argument("--bac", action="store_true")
    a = p.parse_args(argv)
    dsn = os.environ.get("ORACLE_DSN", "localhost:1522/FREEPDB1")
    sys_mdp, mdp = os.environ["ORACLE_PWD"], os.environ["PERSONA_PASSWORD"]
    if a.hr:
        charger_hr(sys_mdp, mdp)
    if a.tout:
        executer_scripts(dsn, sys_mdp, mdp, SCRIPTS)
    if a.bac:
        executer_scripts(dsn, sys_mdp, mdp, ["01_hr_bac.sql"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
