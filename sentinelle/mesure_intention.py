"""Juger une consigne d'intention sur un jeu de questions, erreurs nommées.

    python -m sentinelle.mesure_intention --modele openai/gpt-oss-20b --jeu dev        # consigne v1
    python -m sentinelle.mesure_intention --modele openai/gpt-oss-20b@v2 --jeu dev     # retouche
    python -m sentinelle.mesure_intention --modele openai/gpt-oss-20b@v2 --jeu mesure  # UNE fois, à la fin

On retouche une consigne en ne lisant que les erreurs du jeu `dev` ; le jeu `mesure` (les 90 du banc
d'utilité) ne se lit qu'une fois la consigne arrêtée. Les intentions passent par le cache du modèle et
de la consigne : relancer ne coûte rien.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main(argv=None) -> int:
    from dotenv import load_dotenv
    from borne.generique import lire
    from borne.modele import modele_depuis
    from borne.utilite import QUESTIONS
    from sentinelle.campagne import BANC, Cache, chemin_cache, separer_consigne
    from sentinelle.juge import juger_intentions
    from sentinelle.questions_dev import QUESTIONS_DEV
    from sentinelle.questions_superlatifs import QUESTIONS_SUPERLATIFS

    load_dotenv(".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--modele", default="openai/gpt-oss-20b")
    ap.add_argument("--jeu", choices=("dev", "mesure", "superlatifs"), required=True)
    a = ap.parse_args(argv)
    nom, consigne = separer_consigne(a.modele)
    desc = lire(str(BANC))
    sens = {t.nom: list(t.sensibles) for t in desc.tables}
    jeu = {"dev": QUESTIONS_DEV, "mesure": QUESTIONS, "superlatifs": QUESTIONS_SUPERLATIFS}[a.jeu]
    modele = modele_depuis(nom)
    cache = Cache(chemin_cache(a.modele), modele, consigne)
    paires = [(q, cache.intention(q.profil, desc.profils[q.profil]["contexte"], q.question)) for q in jeu]
    r = juger_intentions(paires, sens)
    par_id = {q.id: (q, i) for q, i in paires}

    sortie = [f"Consigne {consigne}, modèle {nom}, jeu {a.jeu} ({r['n']} questions)", "",
              f"illisibles : {r['illisibles']}",
              f"forme juste : {100 * r['forme_juste']:.1f} %",
              f"colonnes sensibles justes : {100 * r['sensibles_justes']:.1f} %",
              f"colonnes (Jaccard moyen) : {r['colonnes_jaccard_moy']:.2f}",
              f"réécritures altérées : {r['reecritures_alterees']}", "", "Erreurs :"]
    for qid, quoi in r["erreurs"]:
        q, i = par_id[qid]
        assert i is not None   # une erreur nommée vient toujours d'une intention lue
        sortie.append(f"  [{quoi}] {qid} — {q.question}\n    modèle : {i.forme} {sorted(i.colonnes)}"
                      f"\n    vérité : {q.sql_verite}")
    sortie += [f"  [illisible] {q.id} — {q.question}" for q, i in paires if i is None]
    sortie.append(f"\nappels au modèle : {getattr(modele, 'appels', '?')}")
    texte = "\n".join(sortie)
    Path("journal/sentinelle", f"intention-{a.jeu}-{consigne}.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
