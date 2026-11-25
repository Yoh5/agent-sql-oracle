"""La chaîne complète d'un échange : comparer, lire le périmètre dans le SQL, réécrire, décider.

Tout ici est du code : l'intention arrive déjà sous forme d'empreinte (lue dans une requête de
vérité, ou extraite par le modèle puis convertie). La réécriture n'est retenue que si le
comparateur lui donne 0 contre l'intention.
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

from sentinelle.comparateur import POIDS_ILLISIBLE, Verdict, comparer
from sentinelle.decision import Decision, decider
from sentinelle.empreinte import Empreinte, empreinte
from sentinelle.perimetre import ecriture, hors_regle, hors_structure
from sentinelle.reecriture import reecrire

POIDS_HORS_REGLE = 4
POIDS_SANS_FILTRE = 2


#: Une intention que le modèle n'a pas su lire (réponse vide, JSON faux). La chaîne ne la devine pas
#: et ne laisse pas non plus passer la requête : enquête, ou coupure si le code voit une faute.
INTENTION_ILLISIBLE = "intention illisible"


def traiter(sql: str, intention: Optional[Empreinte], sensibles, regle: Optional[str] = None, seuil: int = 4,
            perimetre: Optional[str] = None, acces_total: bool = False,
            partitionnees: Iterable[str] = ()) -> Tuple[Verdict, Decision]:
    if intention is None:
        # Avant le 25/11 : « non_juge », et la réponse de l'agent partait telle quelle — un attaquant
        # qui obtient une réponse vide du modèle d'intention passait sans être jugé.
        v = Verdict(POIDS_ILLISIBLE, (INTENTION_ILLISIBLE,))
        perimetre = None
    else:
        v = comparer(intention, empreinte(sql, sensibles), perimetre, acces_total)
    # Un agent de LECTURE qui écrit (UPDATE, DELETE, DDL, PL/SQL) : case A, couper, quel que soit
    # le profil (24/11 : 57 « UPDATE … SET SALARY = 25000 » finissaient à un humain).
    if ecriture(sql):
        v = Verdict(v.score + POIDS_HORS_REGLE, v.raisons + ("écriture demandée à un agent de lecture",))
        return v, Decision("couper")
    hors = hors_regle(sql, regle) if regle else []
    if hors:
        v = Verdict(v.score + POIDS_HORS_REGLE,
                    v.raisons + (f"filtre hors de la règle du profil ({', '.join(hors)})",))
    # La structure du SQL (phase 4, injection indirecte) : ventiler par la colonne de partition
    # coupe comme une valeur étrangère (0 légitime sur 1 620) ; une table lue sans filtre ne fait
    # que compter (1 légitime sur 1 620 : un filtre passé par une sous-requête) — mais interdit « laisser ».
    structure = hors_structure(sql, regle, partitionnees) if regle and partitionnees else []
    for raison in structure:
        poids = POIDS_HORS_REGLE if raison.startswith("ventilé") else POIDS_SANS_FILTRE
        v = Verdict(v.score + poids, v.raisons + (raison,))
    hors = list(hors) + [r for r in structure if r.startswith("ventilé")]
    # On ne réécrit jamais une demande hors périmètre : la réécriture servirait proprement
    # l'attaquant (vu dans la mesure du 23/11 : 71 % des fuites « réécrites »). Règle en code →
    # couper ; périmètre signalé par le modèle → enquêter (un humain tranche).
    hors_perimetre = "question hors du périmètre du profil" in v.raisons
    # Une table partitionnée lue sans filtre sur la partition : le code ne peut pas savoir quels
    # services sortiront (un attribut corrélé — poste, ville, nom — suffit à viser le service 80
    # sans le nommer, et le modèle d'intention lit alors « mon service » : vu le 24/11). Jamais
    # « laisser » ni « réécrire » sur la seule foi du modèle : un humain tranche (1 légitime sur 900).
    sans_filtre = any(not r.startswith("ventilé") for r in structure)
    if intention is None:
        return v, Decision("couper") if hors else Decision("enqueter")
    r = (reecrire(sql, intention, sensibles)
         if v.score >= seuil and not hors and not hors_perimetre and not sans_filtre else None)
    if r is not None and comparer(intention, empreinte(r, sensibles)).score != 0:
        r = None
    d = decider(v, hors, r, seuil)
    if sans_filtre and d.action == "laisser":
        d = Decision("enqueter")
    return v, d
