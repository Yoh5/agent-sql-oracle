"""Fixtures communes. Sans Oracle ni clé, les tests qui en ont besoin se sautent
en disant pourquoi : `pytest` doit passer sur n'importe quel poste."""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[1]
load_dotenv(RACINE / ".env")


def _connexion_systeme():
    import oracledb
    return oracledb.connect(user="system", password=os.environ.get("ORACLE_PWD", ""),
                            dsn=os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1"),
                            tcp_connect_timeout=3)


@pytest.fixture(scope="session")
def oracle_dispo():
    """Oracle joignable, sinon le test se saute."""
    try:
        c = _connexion_systeme()
    except Exception as e:  # base arrêtée, Docker éteint, mot de passe absent
        pytest.skip(f"Oracle injoignable ({type(e).__name__}) : voir README, « Démarrer Oracle »")
    c.close()
    return True


@pytest.fixture(scope="session")
def cle_groq():
    cle = os.environ.get("GROQ_API_KEY", "").strip()
    if not cle:
        pytest.skip("GROQ_API_KEY absente : test du vrai modèle sauté")
    return cle
