"""Phase 3, de bout en bout : le modèle écrit la politique, le banc la prouve.

    python -m borne.phase3 --modele openai/gpt-oss-120b            # les 3 règles du catalogue
    python -m borne.phase3 --modele openai/gpt-oss-120b --regle service

Pour chaque règle : génération -> contrôle statique -> pose sur la COPIE -> comparaison des
lignes visibles avec la référence (le juge) -> rejeu des 20 attaques. Rapport dans
journal/phase3/<modèle>.md, une ligne JSON par règle à côté. Rien n'est posé sur HR.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

from borne.generateur import GenerateurPolitique, generer_et_prouver
from borne.politique import TerrainEssai
from borne.preuve import juger, rejouer_attaques
from borne.regles import CATALOGUE


def colonnes_protegees(terrain: TerrainEssai) -> Dict[str, List[str]]:
    with terrain._connecter("SEC_ADMIN") as c:
        lignes = c.cursor().execute(
            "SELECT table_name, column_name FROM all_tab_columns WHERE owner = 'HR_ESSAI' "
            "AND table_name IN ('EMPLOYEES', 'JOB_HISTORY') ORDER BY table_name, column_id").fetchall()
    out: Dict[str, List[str]] = {}
    for t, col in lignes:
        out.setdefault(t, []).append(col)
    return out


def eprouver(regle, source: str, terrain: TerrainEssai) -> dict:
    v = juger(terrain, regle.reference, source)
    attaques = [] if v.verdict == "refusee" else rejouer_attaques(terrain, regle.reference, source)
    fuites = [a["attaque"] for a in attaques if a["issue"] in ("fuite", "divergence")]
    return {"regle": regle.id, "verdict": v.verdict, "detail": v.resume(), "attaques_fuite": fuites,
            "attaques": attaques, "source": source}


def rapport(modele: str, resultats: List[dict]) -> str:
    lignes = [f"# Phase 3 — politiques écrites par {modele}", "",
              "| règle | premier essai | après correction | tours | attaques qui passent | détail |",
              "|---|---|---|---|---|---|"]
    for r in resultats:
        lignes.append(f"| `{r['regle']}` | {r.get('premier', r['verdict'])} | **{r['verdict']}** "
                      f"| {r.get('tours', 1)} | {len(r['attaques_fuite'])} "
                      f"{('(' + ', '.join(r['attaques_fuite']) + ')') if r['attaques_fuite'] else ''} "
                      f"| {r['detail']} |")
    return "\n".join(lignes) + "\n"


def main(argv=None) -> int:
    from dotenv import load_dotenv
    from borne.modele import ModeleEnPanne, modele_depuis, nom_de_fichier
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    p = argparse.ArgumentParser(prog="python -m borne.phase3")
    p.add_argument("--modele", default=os.environ.get("MODELE", "openai/gpt-oss-120b"))
    p.add_argument("--regle", nargs="*", help="identifiants de règles (défaut : toutes)")
    p.add_argument("--corrections", type=int, default=2,
                   help="tours de correction après un verdict non juste (0 = un seul essai)")
    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    terrain = TerrainEssai(os.environ["ORACLE_DSN"], os.environ.get("PERSONA_PASSWORD", ""))
    modele = modele_depuis(a.modele)
    gen = GenerateurPolitique(modele)
    colonnes = colonnes_protegees(terrain)
    sortie = Path("journal/phase3")
    sortie.mkdir(parents=True, exist_ok=True)
    nom = nom_de_fichier(a.modele)
    resultats = []
    for regle in [r for r in CATALOGUE if not a.regle or r.id in a.regle]:
        try:
            tours = generer_et_prouver(gen, regle, f"gen_{regle.id}", colonnes,
                                       lambda s, rg=regle: eprouver(rg, s, terrain), a.corrections)
        except ModeleEnPanne as e:
            print(f"  {regle.id} : {e} — arrêt (une panne n'est pas une mesure)")
            break
        r = dict(tours[-1], premier=tours[0]["verdict"], tours=len(tours),
                 parcours=" -> ".join(x["verdict"] for x in tours),
                 historique=[{"tour": x["tour"], "verdict": x["verdict"], "detail": x["detail"],
                              "source": x["source"]} for x in tours])
        resultats.append(r)
        with (sortie / f"{nom}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  {regle.id} : {r['parcours']} — {r['detail']}", flush=True)
    texte = rapport(a.modele, resultats)
    texte += f"\n{modele.appels} appels · {modele.jetons_entree} jetons en entrée · {modele.jetons_sortie} en sortie\n"
    (sortie / f"{nom}.md").write_text(texte, encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
