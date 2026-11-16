"""L'agent : une question, du SQL, une exécution, une issue.

Un graphe LangGraph court, et c'est voulu : le chemin d'une question est
toujours le même (schéma → requête → exécution → une correction si erreur →
réponse). Moins d'étapes, moins d'endroits où une consigne malveillante peut
se glisser, et une issue qu'on sait attribuer à une étape précise.

L'agent ne protège rien lui-même. Il exécute sous le compte Oracle du profil,
et c'est la base qui décide de ce que ce compte voit et peut faire.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple, TypedDict

from langgraph.graph import END, StateGraph

from borne.classer import classer
from borne.config import PROFILS, Barrieres, compte_pour
from borne.journal import Tour, issue_depuis_erreur
from borne.modele import Modele, Proposition


@dataclass
class Resultat:
    lignes: List[tuple]
    colonnes: List[str]
    ora: Optional[str]
    message: Optional[str]
    audit_ref: Optional[str]
    #: lignes que la base a laissé modifier, relevé AVANT l'annulation (0 pour une lecture,
    #: et pour un bloc PL/SQL, où le pilote ne le rapporte pas).
    modifiees: int = 0


class Executeur(Protocol):
    def schema(self, compte: str) -> str: ...
    def executer(self, compte: str, sql: str) -> Resultat: ...


class Etat(TypedDict, total=False):
    question: str
    compte: str
    consignes: bool
    schema: str
    proposition: Proposition
    resultat: Resultat
    tentatives: int
    issue: str


def _graphe(modele: Modele, executeur: Executeur):
    def lire_schema(e: Etat) -> Etat:
        return {"schema": executeur.schema(e["compte"]), "tentatives": 0}

    def ecrire(e: Etat) -> Etat:
        question = e["question"]
        r = e.get("resultat")
        if r is not None and r.ora:          # seconde tentative : on rend l'erreur au modèle
            question += (f"\n\nTa requête précédente a échoué : {r.message}. "
                         f"Corrige-la. Requête : {e['proposition'].sql}")
        return {"proposition": modele.ecrire_sql(question, e["schema"], e["consignes"]),
                "tentatives": e["tentatives"] + 1}

    def aiguiller(e: Etat) -> str:
        p = e["proposition"]
        if p.sql is None:
            return "panne" if p.panne else "refus"
        return "executer" if classer(p.sql) == "lecture" else "a_valider"

    def executer(e: Etat) -> Etat:
        return {"resultat": executeur.executer(e["compte"], e["proposition"].sql)}

    def apres_execution(e: Etat) -> str:
        r = e["resultat"]
        if r.ora and issue_depuis_erreur(r.ora) == "erreur" and e["tentatives"] < 2:
            return "ecrire"
        return END

    g = StateGraph(Etat)
    g.add_node("schema", lire_schema)
    g.add_node("ecrire", ecrire)
    g.add_node("executer", executer)
    g.add_node("refus", lambda e: {"issue": "refus_modele"})
    g.add_node("panne", lambda e: {"issue": "erreur"})   # le modèle n'a pas répondu
    g.add_node("a_valider", lambda e: {"issue": "a_valider"})
    g.set_entry_point("schema")
    g.add_edge("schema", "ecrire")
    g.add_conditional_edges("ecrire", aiguiller, {"refus": "refus", "panne": "panne", "executer": "executer",
                                                    "a_valider": "a_valider"})
    g.add_conditional_edges("executer", apres_execution, {"ecrire": "ecrire", END: END})
    g.add_edge("refus", END)
    g.add_edge("panne", END)
    g.add_edge("a_valider", END)
    return g.compile()


def repondre(question: str, profil: str, barrieres: Barrieres, modele: Modele,
             executeur: Executeur, attaque: Optional[str] = None) -> Tour:
    return repondre_detail(question, profil, barrieres, modele, executeur, attaque)[0]


def repondre_detail(question: str, profil: str, barrieres: Barrieres, modele: Modele,
                    executeur: Executeur, attaque: Optional[str] = None
                    ) -> Tuple[Tour, Optional[Resultat]]:
    """Le tour, et le résultat brut (les lignes) dont le banc a besoin pour juger
    une fuite. Les lignes ne vont jamais dans le journal."""
    if profil not in PROFILS:
        raise ValueError(f"profil inconnu : {profil!r} (connus : {', '.join(PROFILS)})")
    compte = compte_pour(PROFILS[profil], barrieres)
    fin = _graphe(modele, executeur).invoke(
        {"question": question, "compte": compte, "consignes": barrieres.consignes_prompt})

    p: Proposition = fin["proposition"]
    r: Optional[Resultat] = fin.get("resultat")
    issue = fin.get("issue")
    if issue is None:
        issue = issue_depuis_erreur(r.ora) if (r and r.ora) else ("erreur" if r and r.message else "reussi")
    return Tour(question=question, profil=profil, modele=getattr(modele, "nom", "?"),
                barrieres=barrieres.code(), sql=p.sql, issue=issue,
                lignes=len(r.lignes) if r else 0, colonnes=list(r.colonnes) if r else [],
                erreur=(r.message if r else p.refus), ora=r.ora if r else None,
                audit_ref=r.audit_ref if r else None, attaque=attaque), r
