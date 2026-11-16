"""La page : une question, un profil, trois barrières — et où la question s'est arrêtée.

    uvicorn borne.web:app --port 8030

`creer_app(modele, executeur)` sert aux tests ; `app` se construit depuis `.env`
au premier appel (Groq + Oracle). Aucune clé ni aucun mot de passe ne sort.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from borne.agent import Executeur, repondre_detail
from borne.config import PROFILS, Barrieres
from borne.modele import Modele

PAGE = Path(__file__).with_name("page.html")
MAX_AFFICHEES = 50

#: Ce que l'issue veut dire, en une phrase, pour la personne qui a posé la question.
COUCHES = {
    "reussi": "La base a exécuté la requête dans votre périmètre.",
    "filtre_vpd": "La base a exécuté la requête, et sa règle d'accès a retiré les lignes hors de votre périmètre.",
    "bloque_droits": "La base a refusé : votre compte n'a pas ce droit.",
    "refus_modele": "Le modèle a refusé d'écrire la requête. Rien n'a été envoyé à la base.",
    "a_valider": "C'est une modification : rien n'a été exécuté, elle attend la validation d'une personne.",
    "erreur": "La requête n'a pas abouti.",
    "inoffensif": "La requête a abouti sans viser de donnée sensible.",
}


class Question(BaseModel):
    question: str
    profil: str
    barrieres: str = "C1V1P1"


def creer_app(modele: Optional[Modele] = None, executeur: Optional[Executeur] = None) -> FastAPI:
    app = FastAPI(title="Agent SQL borné par Oracle")
    etat = {"modele": modele, "executeur": executeur}

    def _dependances():
        if etat["modele"] is None or etat["executeur"] is None:
            from dotenv import load_dotenv
            from borne.modele import ModeleGroq
            from borne.oracle import ExecuteurOracle
            from borne.verite_oracle import VeriteOracle
            load_dotenv()
            mdp = os.environ.get("PERSONA_PASSWORD", "")
            v = VeriteOracle(os.environ["ORACLE_DSN"], mdp)
            etat["modele"] = etat["modele"] or ModeleGroq(
                os.environ.get("MODELE", "openai/gpt-oss-120b"), os.environ["GROQ_API_KEY"])
            etat["executeur"] = etat["executeur"] or ExecuteurOracle(
                os.environ["ORACLE_DSN"], {c: mdp for c in ("MGR_50", "MGR_80", "RH_DIR", "HR_BAC")},
                lire_audit=v.derniere_entree_audit)
        return etat["modele"], etat["executeur"]

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/profils")
    def profils():
        return [{"nom": p.nom, "departement": p.departement, "role": p.role} for p in PROFILS.values()]

    @app.post("/question")
    def question(q: Question):
        if q.profil not in PROFILS:
            raise HTTPException(400, f"profil inconnu : {q.profil}")
        try:
            barrieres = Barrieres.depuis_code(q.barrieres)
        except ValueError as e:
            raise HTTPException(400, str(e))
        modele, executeur = _dependances()
        tour, r = repondre_detail(q.question, q.profil, barrieres, modele, executeur)
        lignes = [[v if isinstance(v, (int, float, str)) or v is None else str(v) for v in l]
                  for l in (r.lignes[:MAX_AFFICHEES] if r else [])]
        return {"tour": tour.__dict__, "colonnes": r.colonnes if r else [], "lignes": lignes,
                "couche": COUCHES.get(tour.issue, "")}

    return app


app = creer_app()
