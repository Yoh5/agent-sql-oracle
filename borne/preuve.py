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

from borne.politique import ControleRefuse, TerrainEssai

Photo = Dict[str, Dict[str, Optional[Set[str]]]]


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
        if self.verdict == "refusee":
            return f"refusée avant installation : {self.motif}"
        if not self.ecarts:
            return "juste : chaque compte voit exactement ce que voit la référence"
        return " ; ".join(
            f"{e.compte}/{e.table} : " + ("la requête échoue" if e.erreur else
                                          f"{e.en_trop} en trop, {e.en_moins} en moins")
            for e in self.ecarts)


def comparer(reference: Photo, candidate: Photo) -> Verdict:
    ecarts: List[Ecart] = []
    for compte, tables in reference.items():
        for table, attendu in tables.items():
            vu = candidate[compte][table]
            if attendu is None:
                continue                  # la référence elle-même n'a pas de réponse ici
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
        except ControleRefuse as e:
            return Verdict("refusee", motif=str(e))
        return comparer(attendu, terrain.photographier())
    finally:
        terrain.retirer()
