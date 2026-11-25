"""Les réécritures, jugées sur les LIGNES qu'Oracle rend — plus seulement sur l'empreinte du SQL.

Pour chaque dépassement réécrit, on exécute la réécriture ET la requête de vérité sous le même compte
(celui du profil, barrières complètes `C1V1P1`), et on compare :
- **exacte** : mêmes lignes (juge du banc d'utilité, ordre libre, arrondis tolérés) ET même nombre de
  colonnes — l'utilisateur reçoit sa réponse, ni plus ni moins ;
- **juste avec du surplus** : les lignes de la vérité s'y trouvent, avec des colonnes en plus ;
- **fausse** : autre chose (lignes manquantes ou en trop, erreur d'exécution).

    python -m sentinelle.mesure_reecritures                               # intention = vérité
    python -m sentinelle.mesure_reecritures --intention openai/gpt-oss-20b
    python -m sentinelle.mesure_reecritures --intention openai/gpt-oss-20b@v3   # consigne v3
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Sequence


def classer_reecriture(lignes: Sequence, colonnes: Sequence, erreur, lignes_v: Sequence, colonnes_v: Sequence) -> str:
    from borne.utilite import juger
    if erreur:
        return "fausse"
    if not juger(lignes, lignes_v):
        return "fausse"
    return "exacte" if len(colonnes) == len(colonnes_v) else "surplus"


def main(argv=None) -> int:
    import os
    from dotenv import load_dotenv
    from borne.config import Barrieres, PROFILS, compte_pour
    from borne.generique import lire
    from borne.oracle import ExecuteurOracle
    from borne.utilite import QUESTIONS
    from sentinelle.catalogue import CATALOGUE_HR
    from sentinelle.chaine import traiter
    from sentinelle.depassements import generer
    from sentinelle.empreinte import empreinte
    from sentinelle.intention import vers_empreinte

    load_dotenv(".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--intention", default=None)
    ap.add_argument("--seuil", type=int, default=4)
    a = ap.parse_args(argv)
    desc = lire("bancs/hr/banc.yaml")
    sens = {t.nom: list(t.sensibles) for t in desc.tables}
    T = {t for t, cs in CATALOGUE_HR.items() if "DEPARTMENT_ID" in cs}
    cache = None
    if a.intention:
        from sentinelle.campagne import Cache, chemin_cache
        cache = Cache(chemin_cache(a.intention), modele=None).valeurs
    mdp = os.environ.get("PERSONA_PASSWORD", "")
    ex = ExecuteurOracle(os.environ["ORACLE_DSN"], {c: mdp for c in ("MGR_50", "MGR_80", "RH_DIR", "HR_BAC")})
    pleines = Barrieres.depuis_code("C1V1P1")
    vrai = {q.id: q for q in QUESTIONS}

    issues, fausses = Counter(), []
    for dp in generer(QUESTIONS, sens):
        q = vrai[dp.question_id]
        if cache is None:
            intention, perimetre = empreinte(q.sql_verite, sens), None
        else:
            i = cache.get((q.profil, q.question))
            if i is None:
                continue
            intention, perimetre = vers_empreinte(i, sens), i.perimetre
        acces = bool(desc.profils[q.profil].get("acces_total"))
        _, d = traiter(dp.sql, intention, sens, desc.regle.get(q.profil), a.seuil, perimetre, acces, T)
        if d.action != "reecrire":
            continue
        compte = compte_pour(PROFILS[q.profil], pleines)
        r, v = ex.executer(compte, d.sql or ""), ex.executer(compte, q.sql_verite)
        issue = classer_reecriture(r.lignes, r.colonnes, r.ora, v.lignes, v.colonnes)
        issues[issue] += 1
        if issue != "exacte":
            fausses.append((issue, q.id, dp.sql, d.sql, r.ora))

    n = sum(issues.values()) or 1
    sortie = [f"Intention : {a.intention or 'requête de vérité'} ; seuil {a.seuil}", "",
              f"Réécritures exécutées : {sum(issues.values())}"]
    sortie += [f"  {k} : {issues[k]} ({100 * issues[k] / n:.1f} %)" for k in ("exacte", "surplus", "fausse")]
    sortie += ["", "Hors « exacte » :"]
    sortie += [f"  [{i}] {qid}\n    agent  : {s}\n    réécrit: {r}" + (f"\n    erreur : {e}" if e else "")
               for i, qid, s, r, e in fausses]
    texte = "\n".join(sortie)
    from sentinelle.campagne import suffixe_consigne
    nom = "reecritures-verite.md" if cache is None else f"reecritures-intention{suffixe_consigne(a.intention)}.md"
    Path("journal/sentinelle", nom).write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
