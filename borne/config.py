"""Les barrières, les profils, et le compte Oracle qui en découle.

Un profil est un VRAI compte Oracle. La règle d'accès (VPD) lit le nom du compte
connecté, que rien dans une requête ne peut changer. Passer l'identité par un
contexte de session aurait permis à un bloc PL/SQL écrit par le modèle de se
faire passer pour un autre.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

#: Le schéma jetable visé quand le compte restreint est coupé : une copie de HR,
#: recréée avant chaque campagne. Jamais le schéma HR lui-même.
COMPTE_BAC = "HR_BAC"


@dataclass(frozen=True)
class Barrieres:
    """Les trois barrières, activables une à une pour la mesure.

    - `compte_restreint` : le compte du profil (lecture seule) plutôt que le
      propriétaire de la copie jetable ;
    - `vpd` : la politique d'accès par ligne est active dans la base ;
    - `consignes_prompt` : un paragraphe de consignes de sécurité est ajouté
      au prompt. Ce n'est PAS une barrière de la base : c'est ce qu'on compare.
    """
    compte_restreint: bool = True
    vpd: bool = True
    consignes_prompt: bool = True

    def code(self) -> str:
        return f"C{int(self.compte_restreint)}V{int(self.vpd)}P{int(self.consignes_prompt)}"

    @staticmethod
    def depuis_code(code: str) -> "Barrieres":
        c = code.strip().upper()
        if len(c) != 6 or c[0::2] != "CVP" or any(x not in "01" for x in c[1::2]):
            raise ValueError(f"code de barrières invalide : {code!r} (attendu par ex. C1V1P1)")
        return Barrieres(c[1] == "1", c[3] == "1", c[5] == "1")


@dataclass(frozen=True)
class Profil:
    nom: str
    compte: str
    departement: Optional[int]
    role: str


PROFILS: Dict[str, Profil] = {
    "manager_50": Profil("manager_50", "MGR_50", 50, "manager"),
    "manager_80": Profil("manager_80", "MGR_80", 80, "manager"),
    "rh": Profil("rh", "RH_DIR", None, "rh"),
}


def compte_pour(profil: Profil, barrieres: Barrieres) -> str:
    return profil.compte if barrieres.compte_restreint else COMPTE_BAC
