"""Select AI (Oracle, DBMS_CLOUD_AI) comme « modèle » du banc : même attaques, mêmes questions, même base.

    python -m borne.campagne --adb --modele selectai:gpt-4.1-mini --configs C1V1P0 C1V0P0 C0V1P0 C0V0P0
    python -m borne.campagne --adb --modele openrouter:openai/gpt-4.1-mini ...   # notre agent, MÊME modèle

Ce qui est comparé : QUI écrit le SQL. Select AI génère la requête avec son propre prompt (le schéma HR
et ses consignes de génération, sans aucune consigne de sécurité) ; notre agent avec le sien. Dans les
deux cas, la requête est exécutée par le même exécuteur, sous le compte du profil : la VPD et le
détecteur de fuite sont strictement les mêmes. Select AI ne sait pas qui est connecté : on lui donne la
même phrase de contexte que celle que reçoit notre agent (« Utilisateur connecté : … »).

Pourquoi le fournisseur OpenAI natif et pas OpenRouter : avec une adresse « compatible OpenAI »
(provider_endpoint), Select AI renvoyait de la prose au lieu du SQL, alors que la même invite envoyée
directement à OpenRouter rendait une requête correcte (vérifié le 17/11/2026, trois variantes).

Les connexions du banc sont redirigées vers Autonomous Database Free (conteneur adb-free) par
`rediriger_vers_adb()` : rien d'autre dans le code du banc ne change.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from borne.modele import Proposition

RACINE = Path(__file__).resolve().parents[1]
WALLET = RACINE / "adb" / "tls_wallet"
DSN_ADB = ("(description=(retry_count=2)(retry_delay=3)(address=(protocol=tcps)(port=1532)(host=localhost))"
           "(connect_data=(service_name=myatp_low.adb.oraclecloud.com))(security=(ssl_server_dn_match=no)))")


def rediriger_vers_adb() -> None:
    """Toute connexion oracledb du processus part vers ADB, avec le portefeuille TLS et le mot de
    passe des comptes ADB (ADB impose ses règles de complexité : il diffère de PERSONA_PASSWORD)."""
    import oracledb
    vraie = oracledb.connect
    if getattr(vraie, "_vers_adb", False):
        return

    def connect(*args, **kw):
        user = (kw.get("user") or (args[0] if args else "")).upper()
        mdp = os.environ["ADB_ADMIN_PWD"] if user == "ADMIN" else os.environ["ADB_PERSONA_PWD"]
        return vraie(user=user, password=mdp, dsn=DSN_ADB, config_dir=str(WALLET),
                     wallet_location=str(WALLET), wallet_password=os.environ["ADB_WALLET_PWD"])
    connect._vers_adb = True
    oracledb.connect = connect


def cle_openai() -> str:
    t = (RACINE.parent / "paypal-mandat" / ".env").read_text(encoding="utf-8")
    return re.search(r"^OPENAI_API_KEY\s*=\s*(.+)$", t, re.M).group(1).strip().strip("'\"")


class ModeleSelectAI:
    """Génère le SQL par DBMS_CLOUD_AI.GENERATE(action => 'showsql'), dans la session ADMIN : la
    génération ne dépend que de l'invite et du schéma ; l'EXÉCUTION se fait ensuite sous le compte."""

    def __init__(self, modele: str = "gpt-4.1-mini"):
        import oracledb
        rediriger_vers_adb()
        self.nom = f"selectai:{modele}"
        self.appels = self.jetons_entree = self.jetons_sortie = 0
        self.c = oracledb.connect(user="ADMIN")
        cur = self.c.cursor()
        cur.execute("""BEGIN DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(host => 'api.openai.com',
          ace => xs$ace_type(privilege_list => xs$name_list('http'), principal_name => 'ADMIN',
                             principal_type => xs_acl.ptype_db)); END;""")
        cur.execute("""BEGIN BEGIN DBMS_CLOUD.DROP_CREDENTIAL('BANC_OA'); EXCEPTION WHEN OTHERS THEN NULL; END;
                       DBMS_CLOUD.CREATE_CREDENTIAL('BANC_OA', 'openai', :k); END;""", k=cle_openai())
        attrs = {"provider": "openai", "credential_name": "BANC_OA", "model": modele,
                 "object_list": [{"owner": "HR"}], "temperature": 0}
        cur.execute("""BEGIN BEGIN DBMS_CLOUD_AI.DROP_PROFILE('BANC'); EXCEPTION WHEN OTHERS THEN NULL; END;
                       DBMS_CLOUD_AI.CREATE_PROFILE('BANC', :a); END;""", a=json.dumps(attrs))

    def ecrire_sql(self, question: str, schema: str, consignes: bool, contexte: str = "") -> Proposition:
        q = question.split("\n\nTa requête précédente a échoué", 1)[0]
        invite = f"Utilisateur connecté : {contexte}. {q}" if contexte else q
        try:
            r = self.c.cursor().execute(
                "SELECT DBMS_CLOUD_AI.GENERATE(prompt => :q, profile_name => 'BANC', action => 'showsql') FROM dual",
                q=invite).fetchone()[0]
        except Exception as e:  # réseau, quota : une panne, jamais un refus
            return Proposition(None, f"modèle injoignable : {type(e).__name__}: {e}"[:300], "", panne=True)
        self.appels += 1
        texte = str(r or "").strip()
        if re.match(r"^\s*(SELECT|WITH)\b", texte, re.I):
            # Le banc qualifie lui-même les objets par le compte (synonymes) : on retire « "HR". »
            sql = re.sub(r'"HR"\.', "", texte).rstrip().rstrip(";")
            return Proposition(sql, None, texte)
        return Proposition(None, texte[:300] or "réponse vide", texte)
