import pytest

from borne.classer import classer


@pytest.mark.parametrize("sql, attendu", [
    ("select 1 from dual", "lecture"),
    ("  -- une note\nWITH t AS (SELECT 1 x FROM dual) SELECT x FROM t", "lecture"),
    ("/* bloc */ SELECT * FROM hr.employees", "lecture"),
    ("SELECT ';' FROM dual", "lecture"),
    ("SELECT 1 FROM dual;", "lecture"),                       # un ; final n'est pas une 2e instruction
    ("DELETE FROM hr.employees", "ecriture"),
    ("update hr.employees set salary = 0", "ecriture"),
    ("BEGIN dbms_session.set_identifier('RH_DIR'); END;", "ecriture"),
    ("DROP TABLE hr.employees", "ecriture"),
    ("SELECT 1 FROM dual; DROP TABLE x", "multiple"),
    ("", "vide"),
    ("   -- rien\n", "vide"),
])
def test_classer(sql, attendu):
    assert classer(sql) == attendu


def test_un_mot_inconnu_part_en_validation():
    # Dans le doute, on demande à un humain : jamais l'inverse.
    assert classer("EXPLAIN PLAN FOR SELECT 1 FROM dual") == "ecriture"
