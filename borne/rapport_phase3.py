"""Le rapport de la phase 3, lisible par l'administrateur qui doit valider une politique.

    python -m borne.rapport_phase3            # journal/phase3/*.jsonl -> journal/phase3/rapport.html

Pour chaque règle et chaque modèle : la règle en français, le parcours des essais, ce que
le juge a vu (compte par compte), le code final, le rejeu des attaques. Aucune politique
n'est déployée par ce rapport : il sert à décider.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import List

from borne.regles import CATALOGUE

COULEURS = {"juste": "ok", "trou": "ko", "trou_et_trop_stricte": "ko", "erreur": "ko",
            "trop_stricte": "attente", "illisible": "neutre", "refusee": "neutre"}
MOTS = {"juste": "Juste", "trou": "Trou", "trou_et_trop_stricte": "Trou et trop stricte",
        "erreur": "Erreur", "trop_stricte": "Trop stricte", "illisible": "Illisible", "refusee": "Refusée"}

STYLE = """
:root{--bg:#f5f6f8;--carte:#fff;--ink:#0f172a;--ink-2:#475569;--filet:#d8dde4;
--ok:#15803d;--ok-f:#e9f5ec;--ko:#b42318;--ko-f:#fbeceb;--attente:#a15c07;--attente-f:#fbf2e1;
--neutre:#475569;--neutre-f:#eef1f5;--sans:"Source Sans 3",system-ui,sans-serif;--mono:"JetBrains Mono",Consolas,monospace}
*{box-sizing:border-box;margin:0}body{font-family:var(--sans);background:var(--bg);color:var(--ink);font-size:15px;line-height:1.5}
.wrap{max-width:1080px;margin:0 auto;padding:32px 40px 64px}h1{font-size:24px}.these{color:var(--ink-2);margin:6px 0 24px}
.carte{background:var(--carte);border:1px solid var(--filet);border-radius:8px;padding:20px 24px;margin-bottom:18px}
h2{font-size:18px;margin-bottom:4px}.regle{color:var(--ink-2);margin-bottom:14px}
.parcours{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 12px}
.etat{font-size:13px;font-weight:600;border-radius:999px;padding:3px 12px}
.ok{color:var(--ok);background:var(--ok-f)}.ko{color:var(--ko);background:var(--ko-f)}
.attente{color:var(--attente);background:var(--attente-f)}.neutre{color:var(--neutre);background:var(--neutre-f)}
.fleche{color:var(--ink-2)}.modele{font-family:var(--mono);font-size:13px;color:var(--ink-2)}
ol{margin:6px 0 10px 20px;font-size:14px}li{margin:3px 0}
details{margin-top:8px}summary{cursor:pointer;font-size:14px;color:var(--ink-2)}
pre{font-family:var(--mono);font-size:12.5px;background:#0f172a;color:#e2e8f0;border-radius:6px;padding:12px 14px;white-space:pre-wrap;margin-top:8px}
.attaques{font-size:14px;color:var(--ink-2)}
"""


def charger(dossier: Path) -> List[dict]:
    lignes = []
    for f in sorted(dossier.glob("*.jsonl")):
        modele = f.stem.replace("openai_", "openai/")
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                r["modele"] = modele
                lignes.append(r)
    return lignes


def _etat(verdict: str) -> str:
    return f'<span class="etat {COULEURS.get(verdict, "neutre")}">{MOTS.get(verdict, verdict)}</span>'


def construire(resultats: List[dict]) -> str:
    textes = {r.id: r.texte for r in CATALOGUE}
    cartes = []
    for r in resultats:
        tours = r.get("historique") or [{"tour": 1, "verdict": r["verdict"], "detail": r["detail"],
                                         "source": r.get("source", "")}]
        parcours = ' <span class="fleche">→</span> '.join(_etat(t["verdict"]) for t in tours)
        etapes = "".join(f"<li><b>Essai {t['tour']}</b> · {html.escape(t['detail'])}</li>" for t in tours)
        fuites = r.get("attaques_fuite") or []
        attaques = (f"{len(fuites)} attaque(s) passent : {html.escape(', '.join(fuites))}" if fuites
                    else "Aucune des attaques rejouées ne passe.")
        cartes.append(f"""<section class="carte">
  <h2>{html.escape(r['regle'])} <span class="modele">· {html.escape(r['modele'])}</span></h2>
  <p class="regle">« {html.escape(textes.get(r['regle'], ''))} »</p>
  <div class="parcours">{parcours}</div>
  <ol>{etapes}</ol>
  <p class="attaques">{attaques}</p>
  <details><summary>Code final de la politique</summary><pre>{html.escape(r.get('source') or '')}</pre></details>
</section>""")
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Phase 3 — politiques prouvées</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono&display=swap">
<style>{STYLE}</style></head><body><div class="wrap">
<h1>Règles d'accès écrites par un modèle, prouvées par le banc</h1>
<p class="these">Chaque politique est posée sur une copie du schéma, jamais sur HR. Le juge compare, compte par compte,
les lignes qu'elle laisse voir à celles d'une référence écrite à la main. Le modèle ne se juge jamais.</p>
{''.join(cartes) or '<p>Aucun résultat : lancer python -m borne.phase3.</p>'}
</div></body></html>"""


def main() -> int:
    dossier = Path("journal/phase3")
    page = construire(charger(dossier))
    (dossier / "rapport.html").write_text(page, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"écrit : {dossier / 'rapport.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
