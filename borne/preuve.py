"""Phase 3 : le juge d'une politique candidate. Il compare des LIGNES, jamais du texte.

Pour chaque compte de test et chaque table protégée, les clés visibles avec la politique
candidate sont comparées aux clés visibles avec la politique de RÉFÉRENCE :
- des lignes en trop  -> **trou** (quelqu'un voit ce qu'il ne devrait pas) ;
- des lignes en moins -> **trop_stricte** (une question légitime perd des données) ;
- la requête échoue alors que la référence répond -> **erreur** (une politique qui
  plante bloque tout : Oracle refuse la requête entière).
Le modèle qui a écrit la politique n'est jamais consulté.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from borne.politique import ControleRefuse, NeCompilePas, TerrainEssai

Photo = Dict[str, Dict[str, Optional[Set[str]]]]


class ReferenceInvalide(RuntimeError):
    """La politique de RÉFÉRENCE échoue : c'est le banc qui est faux, pas la candidate."""


@dataclass
class Ecart:
    compte: str
    table: str
    en_trop: int
    en_moins: int
    exemples_en_trop: List[str] = field(default_factory=list)
    exemples_en_moins: List[str] = field(default_factory=list)
    erreur: bool = False


@dataclass
class Verdict:
    verdict: str                       # juste | trou | trop_stricte | trou_et_trop_stricte | erreur | refusee
    ecarts: List[Ecart] = field(default_factory=list)
    motif: str = ""

    def resume(self) -> str:
        if self.verdict in ("refusee", "ne_compile_pas"):
            return f"refusée avant installation : {self.motif}"
        if not self.ecarts:
            return "juste : chaque compte voit exactement ce que voit la référence"
        return " ; ".join(
            f"{e.compte}/{e.table} : " + ("la requête échoue" if e.erreur else
                                          f"{e.en_trop} en trop, {e.en_moins} en moins"
                                          + (f" (en trop : {', '.join(e.exemples_en_trop)})" if e.exemples_en_trop else "")
                                          + (f" (en moins : {', '.join(e.exemples_en_moins)})" if e.exemples_en_moins else ""))
            for e in self.ecarts)


def comparer(reference: Photo, candidate: Photo) -> Verdict:
    ecarts: List[Ecart] = []
    for compte, tables in reference.items():
        for table, attendu in tables.items():
            vu = candidate[compte][table]
            if attendu is None:
                # La référence elle-même échoue : il n'y a plus rien à comparer. Sauter la
                # table déclarait « juste » n'importe quelle candidate (vu le 16/11/2026).
                raise ReferenceInvalide(f"la référence échoue pour {compte} sur {table}")
            if vu is None:
                ecarts.append(Ecart(compte, table, 0, len(attendu), erreur=True))
                continue
            trop, moins = vu - attendu, attendu - vu
            if trop or moins:
                ecarts.append(Ecart(compte, table, len(trop), len(moins),
                                    sorted(trop)[:3], sorted(moins)[:3]))
    if any(e.erreur for e in ecarts):
        nom = "erreur"
    else:
        trou, stricte = any(e.en_trop for e in ecarts), any(e.en_moins for e in ecarts)
        nom = ("trou_et_trop_stricte" if trou and stricte else "trou" if trou
               else "trop_stricte" if stricte else "juste")
    return Verdict(nom, ecarts)


def juger(terrain: TerrainEssai, reference: str, candidate: str) -> Verdict:
    """Installe la référence, photographie ; installe la candidate, photographie ; compare.
    Laisse le terrain sans politique."""
    try:
        terrain.installer(reference)
        attendu = terrain.photographier()
        try:
            terrain.installer(candidate)
        except NeCompilePas as e:
            return Verdict("ne_compile_pas", motif=str(e))
        except ControleRefuse as e:
            return Verdict("refusee", motif=str(e))
        return comparer(attendu, terrain.photographier())
    finally:
        terrain.retirer()


# --------------------------------------------------------------------------- #
# Les 20 attaques du banc, rejouées sur la copie
# --------------------------------------------------------------------------- #
#: Profil du banc -> compte de test qui le joue sur la copie.
COMPTE_DU_PROFIL = {"manager_50": "ESSAI_M50", "manager_80": "ESSAI_M80", "rh": "ESSAI_RH"}


def _lignes(terrain: TerrainEssai, compte: str, sql: str):
    """Les lignes rendues (multiensemble de textes), ou None si la requête échoue."""
    from collections import Counter
    with terrain._connecter(compte) as c:
        try:
            return Counter(repr(tuple(r)) for r in c.cursor().execute(sql.rstrip(";")).fetchall())
        except terrain._oracledb.DatabaseError:
            return None


def rejouer_attaques(terrain: TerrainEssai, reference: str, candidate: str,
                     attaques=None) -> List[Dict[str, str]]:
    """Chaque attaque est jouée sous la référence puis sous la candidate, par le compte de
    test du profil visé. fuite = la candidate rend des lignes que la référence cache ;
    plus_stricte = l'inverse ; divergence = les deux (un agrégat qui change de valeur)."""
    from borne.attaques import CATALOGUE as ATTAQUES
    attaques = list(attaques or ATTAQUES)
    lisibles = [a for a in attaques if a.nature != "ecriture"]
    try:
        terrain.installer(reference)
        avant = {a.id: _lignes(terrain, COMPTE_DU_PROFIL[a.profil], a.sql_cede) for a in lisibles}
        terrain.installer(candidate)
        apres = {a.id: _lignes(terrain, COMPTE_DU_PROFIL[a.profil], a.sql_cede) for a in lisibles}
    finally:
        terrain.retirer()
    resultat = []
    for a in attaques:
        if a.nature == "ecriture":
            resultat.append({"attaque": a.id, "famille": a.famille, "issue": "hors_perimetre"})
            continue
        r, c = avant[a.id], apres[a.id]
        if r is None:
            issue = "sans_reference"       # la requête échoue déjà sous la référence
        elif c is None:
            issue = "erreur"
        else:
            trop, moins = c - r, r - c
            issue = ("divergence" if trop and moins else "fuite" if trop
                     else "plus_stricte" if moins else "identique")
        resultat.append({"attaque": a.id, "famille": a.famille, "issue": issue})
    return resultat
