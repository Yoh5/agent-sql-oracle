"""Classer une instruction SQL : pour ORIENTER, pas pour protéger.

Une lecture s'exécute ; tout le reste part en validation humaine. Ce classement
n'est **pas une barrière de sécurité** : un classement trompé ne donne aucun
droit, parce que le compte de l'agent n'a que celui de lire et que la base
refuse le reste quoi qu'en dise ce module (vérifié par les tests Oracle). Dans
le doute, il classe en écriture : on dérange un humain plutôt que d'exécuter.
"""
from __future__ import annotations

import re
from typing import Literal

Classe = Literal["lecture", "ecriture", "multiple", "vide"]

_COMMENTAIRES = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_CHAINES = re.compile(r"'(?:[^']|'')*'")


def _sans_bruit(sql: str) -> str:
    return _CHAINES.sub("''", _COMMENTAIRES.sub(" ", sql)).strip()


def classer(sql: str) -> Classe:
    nu = _sans_bruit(sql or "")
    if not nu:
        return "vide"
    corps = nu.rstrip().rstrip(";").rstrip()
    premier = corps.split(None, 1)[0].upper() if corps else ""
    # Un bloc PL/SQL contient des ; par nature : c'est une écriture, pas un multiple.
    if premier in ("BEGIN", "DECLARE"):
        return "ecriture"
    if ";" in corps:
        return "multiple"
    return "lecture" if premier in ("SELECT", "WITH") else "ecriture"
