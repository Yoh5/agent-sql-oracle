"""Phase 3 : le modèle écrit la politique d'accès depuis une règle en français.

Le modèle ne juge rien. Ce qu'il écrit passe le contrôle statique, est posé sur la copie
et comparé, ligne par ligne, à la politique de référence (borne/preuve.py).
"""
from __future__ import annotations

import re
from typing import Dict, List

CONSIGNE = """Tu écris une politique d'accès Oracle (VPD) : UNE fonction PL/SQL, et rien d'autre.

Signature imposée, sans rien changer :
  CREATE OR REPLACE FUNCTION {nom} (p_schema VARCHAR2, p_objet VARCHAR2) RETURN VARCHAR2 AS ...

La fonction rend un PRÉDICAT SQL (un texte, ex. 'department_id = 50'), ou NULL pour tout
autoriser. Oracle l'ajoute à chaque requête sur les tables protégées : {tables}.
Les colonnes de ces tables :
{colonnes}

Qui est connecté : SYS_CONTEXT('USERENV', 'SESSION_USER'). Son profil est dans la table
essai_pol.profils (compte VARCHAR2, departement_id NUMBER, role VARCHAR2 'manager' ou 'rh',
employee_id NUMBER). Un compte absent de cette table est inconnu.

Interdit : SQL dynamique (EXECUTE IMMEDIATE), paquets DBMS_ ou UTL_, objets de SYS,
INSERT/UPDATE/DELETE, COMMIT, DDL, transaction autonome. Une seule fonction.
Attention : la même fonction protège TOUTES les tables listées ; un prédicat doit être
valable sur chacune.

Réponds par un seul bloc ```sql contenant la fonction."""


def construire_messages(regle: str, nom: str, colonnes: Dict[str, List[str]]) -> List[Dict[str, str]]:
    systeme = CONSIGNE.format(
        nom=nom, tables=", ".join(colonnes),
        colonnes="\n".join(f"  {t} : {', '.join(c)}" for t, c in colonnes.items()))
    return [{"role": "system", "content": systeme},
            {"role": "user", "content": f"Règle à appliquer : {regle}"}]


def extraire_fonction(texte: str) -> str:
    """Le code de la fonction dans la réponse du modèle (bloc ```sql, sinon de CREATE à END;)."""
    bloc = re.search(r"```(?:sql|plsql)?\s*(.*?)```", texte or "", re.S | re.I)
    corps = bloc.group(1) if bloc else (texte or "")
    m = re.search(r"CREATE\s+OR\s+REPLACE\s+FUNCTION.*END\s*\w*\s*;", corps, re.S | re.I)
    return (m.group(0) if m else corps).strip().rstrip("/").strip()


class GenerateurPolitique:
    def __init__(self, modele):
        """`modele` : un ModeleGroq (ou tout objet qui a `completer(messages) -> str`)."""
        self.modele = modele

    def generer(self, regle: str, nom: str, colonnes: Dict[str, List[str]]) -> str:
        return extraire_fonction(self.modele.completer(construire_messages(regle, nom, colonnes)))
