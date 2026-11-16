"""Les scripts SQL se découpent proprement : sans base, on vérifie au moins la forme."""
import importlib.util
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", RACINE / "scripts" / "installer.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.mark.parametrize("nom", installer.SCRIPTS)
def test_chaque_script_se_decoupe_sans_reste(nom):
    texte = (RACINE / "sql" / nom).read_text(encoding="utf-8")
    blocs = list(installer.blocs(texte))
    assert blocs
    for b in blocs:
        assert not b.rstrip().endswith("/")
        # Une instruction SQL simple ne finit pas par « ; » (python-oracledb la refuserait) ;
        # un bloc PL/SQL, si.
        if not b.lstrip().upper().startswith(("BEGIN", "DECLARE", "CREATE OR REPLACE")):
            assert not b.rstrip().endswith(";"), b[:60]


def test_un_bloc_non_termine_est_signale():
    with pytest.raises(ValueError):
        list(installer.blocs("SELECT 1 FROM dual\n/\nSELECT 2 FROM dual"))


def test_la_vpd_lit_le_compte_connecte():
    vpd = (RACINE / "sql" / "02_vpd.sql").read_text(encoding="utf-8")
    assert "SESSION_USER" in vpd and "CLIENT_IDENTIFIER" not in vpd
    assert "RETURN '1=0'" in vpd          # compte inconnu : rien
