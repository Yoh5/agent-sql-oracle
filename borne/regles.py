"""Phase 3 : le catalogue de règles en français, avec leur politique de RÉFÉRENCE écrite
à la main, et des MUTANTS au défaut connu.

Le juge (borne/preuve.py) doit déclarer chaque référence juste et attraper chaque mutant.
C'est la question de la conception, « le banc détecte-t-il toutes les politiques
fautives ? », posée sans aucun modèle : un juge qui laisse passer un mutant connu ne
prouverait rien sur une politique générée.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


def fonction(nom: str, manager: str, rh: str = "NULL", inconnu: str = "'1=0'") -> str:
    """Une fonction de politique au gabarit commun : profil lu dans ESSAI_POL.PROFILS
    d'après le compte CONNECTÉ (SESSION_USER), jamais d'après un contexte modifiable.
    `manager` et `rh` sont des expressions PL/SQL qui rendent le prédicat (v_dep et
    v_emp sont disponibles) ; `inconnu` est ce que voit un compte sans profil."""
    return f"""CREATE OR REPLACE FUNCTION {nom} (p_schema VARCHAR2, p_objet VARCHAR2)
  RETURN VARCHAR2 AS
  v_role essai_pol.profils.role%TYPE;
  v_dep  essai_pol.profils.departement_id%TYPE;
  v_emp  essai_pol.profils.employee_id%TYPE;
BEGIN
  SELECT role, departement_id, employee_id INTO v_role, v_dep, v_emp
    FROM essai_pol.profils WHERE compte = SYS_CONTEXT('USERENV', 'SESSION_USER');
  IF v_role = 'rh' THEN
    RETURN {rh};
  END IF;
  RETURN {manager};
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RETURN {inconnu};
END;"""


@dataclass(frozen=True)
class Mutant:
    source: str
    attendu: str          # « trou », « trop_stricte » ou « erreur » : ce que le juge DOIT conclure
    defaut: str           # le défaut, en une phrase


@dataclass(frozen=True)
class Regle:
    id: str
    texte: str            # la règle telle qu'un administrateur l'écrirait
    reference: str
    mutants: Dict[str, Mutant] = field(default_factory=dict)


_SERVICE = "'department_id = ' || TO_CHAR(v_dep)"
_POSTES = "REGEXP_LIKE(job_id, ''_(REP|CLERK)$'')"

CATALOGUE = [
    Regle(
        "service",
        "Un manager voit les employés de son service ; la RH voit tout le monde ; "
        "un compte sans profil ne voit rien.",
        fonction("ref_service", _SERVICE),
        {
            "inconnu_ouvert": Mutant(fonction("mut_inconnu", _SERVICE, inconnu="NULL"), "trou",
                                     "un compte sans profil voit tout (refus par défaut oublié)"),
            "null_ouvert": Mutant(fonction("mut_null", _SERVICE + " || ' OR department_id IS NULL'"), "trou",
                                  "le manager voit aussi les employés sans service"),
            "sans_cadres": Mutant(fonction("mut_sans_cadres", _SERVICE + " || ' AND job_id NOT LIKE ''%MAN'''"),
                                  "trop_stricte", "le manager ne voit plus les cadres (_MAN) de son service"),
            # Trouvé par le juge (16/11/2026) : « salary < 10000 » ne vaut que pour
            # EMPLOYEES ; la même fonction protège JOB_HISTORY, qui n'a pas de salaire, et
            # toute requête sur l'historique échoue. Piège typique d'une politique écrite pour
            # une table et posée sur plusieurs.
            "colonne_absente": Mutant(fonction("mut_plafond", _SERVICE + " || ' AND salary < 10000'"), "erreur",
                                      "prédicat sur « salary », colonne absente de JOB_HISTORY"),
        }),
    Regle(
        "sauf_direction",
        "Un manager voit son service ; la RH voit tout le monde sauf la direction générale "
        "(service 90) ; un compte sans profil ne voit rien.",
        fonction("ref_direction", _SERVICE, rh="'(department_id IS NULL OR department_id <> 90)'"),
        {
            "rh_partout": Mutant(fonction("mut_rh_tout", _SERVICE, rh="NULL"), "trou",
                                 "la RH voit aussi la direction générale"),
            "piege_null": Mutant(fonction("mut_rh_null", _SERVICE, rh="'department_id <> 90'"), "trop_stricte",
                                 "« <> 90 » écarte aussi l'employé sans service (NULL n'est pas différent de 90)"),
        }),
    Regle(
        "postes",
        "Un manager ne voit que les commerciaux et les commis de son service (postes en _REP "
        "ou _CLERK) ; la RH voit tout le monde ; un compte sans profil ne voit rien.",
        fonction("ref_postes", _SERVICE + f" || ' AND {_POSTES}'"),
        {
            "tous_postes": Mutant(fonction("mut_postes_tous", _SERVICE), "trou",
                                  "le manager voit aussi les cadres de son service"),
            "rep_seulement": Mutant(fonction("mut_postes_rep", _SERVICE + " || ' AND job_id LIKE ''%REP'''"),
                                    "trop_stricte", "les commis (_CLERK) disparaissent"),
        }),
]
