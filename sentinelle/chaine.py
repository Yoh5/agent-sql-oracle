"""La chaîne complète d'un échange : comparer, lire le périmètre dans le SQL, réécrire, décider.

Tout ici est du code : l'intention arrive déjà sous forme d'empreinte (lue dans une requête de
vérité, ou extraite par le modèle puis convertie). La réécriture n'est retenue que si le
comparateur lui donne 0 contre l'intention.
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

from sentinelle.comparateur import Verdict, comparer
from sentinelle.decision import Decision, decider
from sentinelle.empreinte import Empreinte, empreinte
from sentinelle.perimetre import hors_regle, hors_structure
from sentinelle.reecriture import reecrire

POIDS_HORS_REGLE = 4
POIDS_SANS_FILTRE = 2


def traiter(sql: str, intention: Empreinte, sensibles, regle: Optional[str] = None, seuil: int = 4,
            perimetre: Optional[str] = None, acces_total: bool = False,
            partitionnees: Iterable[str] = ()) -> Tuple[Verdict, Decision]:
    v = comparer(intention, empreinte(sql, sensibles), perimetre, acces_total)
    hors = hors_regle(sql, regle) if regle else []
    if hors:
        v = Verdict(v.score + POIDS_HORS_REGLE,
                    v.raisons + (f"filtre hors de la règle du profil ({', '.join(hors)})",))
    # La structure du SQL (phase 4, injection indirecte) : ventiler par la colonne de partition
    # coupe comme une valeur étrangère (0 légitime sur 1 620) ; une table lue sans filtre ne fait
    # que compter (1 légitime sur 1 620 : un filtre passé par une sous-requête).
    structure = hors_structure(sql, regle, partitionnees) if regle and partitionnees else []
    for raison in structure:
        poids = POIDS_HORS_REGLE if raison.startswith("ventilé") else POIDS_SANS_FILTRE
        v = Verdict(v.score + poids, v.raisons + (raison,))
    hors = list(hors) + [r for r in structure if r.startswith("ventilé")]
    # On ne réécrit jamais une demande hors périmètre : la réécriture servirait proprement
    # l'attaquant (vu dans la mesure du 23/11 : 71 % des fuites « réécrites »). Règle en code →
    # couper ; périmètre signalé par le modèle → enquêter (un humain tranche).
    hors_perimetre = "question hors du périmètre du profil" in v.raisons
    r = reecrire(sql, intention, sensibles) if v.score >= seuil and not hors and not hors_perimetre else None
    if r is not None and comparer(intention, empreinte(r, sensibles)).score != 0:
        r = None
    return v, decider(v, hors, r, seuil)
