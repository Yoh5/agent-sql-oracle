# Sentinelle — phase 3 (réécriture minimale, décision par paliers) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** au lieu de bloquer, répondre à la question et rien de plus : réécrire le SQL au minimum que l'intention demande, revalider la réécriture par le comparateur, et choisir une action parmi une liste fermée.

**Spec:** `docs/superpowers/specs/2026-11-23-sentinelle-design.md` (« Décision par paliers », ordre de construction point 3).

## Global Constraints
- La réécriture garde le FROM, les jointures et le WHERE de l'agent (donc ses droits) ; elle ne change que la liste de sortie.
- Une réécriture n'est retenue que si le comparateur lui donne 0 contre l'intention ; sinon, l'action devient « enquêter ».
- Le filtre hors de la règle du profil (code) donne toujours « couper » : on ne réécrit pas une demande hors périmètre.
- Hors ligne : pas d'exécution ; l'équivalence avec la vérité se juge sur l'empreinte (l'exécution sur Oracle viendra quand la base tourne).

## Review Focus
1. Intention « compte » sur un SQL avec GROUP BY → pas de réécriture en COUNT(*) global (on enquête).
2. Intention de liste sans colonne (modèle imprécis) → pas de réécriture vide (on enquête).
3. SQL avec UNION ou illisible → pas de réécriture (on enquête).
4. Agrégat sur une colonne absente des tables du FROM → réécriture refusée.
5. Score sous le seuil → « laisser », même si une réécriture serait possible.

### Task 1: `sentinelle/reecriture.py` — `reecrire(sql: str, intention: Empreinte, sensibles) -> str | None`
compte → `COUNT(*)` ; somme/moyenne/minimum/maximum → `SUM/AVG/MIN/MAX(<la colonne de l'intention>)` (une seule colonne, sinon None) ; liste → les colonnes de l'intention (au moins une, sinon None) ; groupe → None. Tests : effectif devenu liste → `COUNT(*)` avec le même WHERE ; moyenne → `AVG(salary)` ; liste avec salaire en trop → salaire retiré ; GROUP BY → None ; UNION → None ; la réécriture a un score 0 contre l'intention.

### Task 2: `sentinelle/decision.py` — `decider(verdict, hors: list[str], reecriture: str | None, seuil: int) -> Decision(action, sql)`
actions = ("laisser", "reecrire", "enqueter", "couper") ; `hors` non vide → couper ; score < seuil → laisser ; réécriture valide → reecrire ; sinon enqueter. Tests : un par branche.

### Task 3: rejeu — colonne « action » sur légitimes, dépassements et attaques
Tableau : répartition des actions ; pour les dépassements, part des réécritures dont l'empreinte égale celle de la vérité (forme + colonnes) ; pour les légitimes, part touchée par une action autre que « laisser ». README mis à jour.
