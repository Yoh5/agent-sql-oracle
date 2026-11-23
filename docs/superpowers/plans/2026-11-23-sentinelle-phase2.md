# Sentinelle — phase 2 (intention par un modèle, juger le juge) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** remplacer l'intention « lue dans la requête de vérité » par une intention extraite de la question par un petit modèle, mesurer ce modèle contre la vérité, puis rejouer légitimes, dépassements et attaques avec cette intention.

**Architecture:** `sentinelle/intention.py` demande au modèle un JSON strict (colonnes à voir, forme, périmètre) ; il ne voit ni SQL ni données. `comparateur` gagne une règle de périmètre et ignore la règle des tables quand l'intention n'en donne pas. `juge.py` compare l'intention du modèle à l'empreinte de la vérité sur les 90 questions légitimes. `rejeu --intention modele` rejoue avec le cache d'intentions.

**Tech Stack:** Python, `borne.modele.modele_depuis` (Groq / OpenRouter, déjà en place), pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-sentinelle-design.md` (Architecture 1, « Données » 1, « Mesures » : juger le juge, fausses alertes, détections).

## Global Constraints

- Le modèle d'intention reçoit la question, le contexte du profil et le catalogue des colonnes ; **jamais** le SQL ni les données.
- Toute réponse non conforme au JSON attendu → intention `None`, comptée à part (jamais devinée).
- Les intentions sont mises en cache (`journal/sentinelle/intentions-<modele>.jsonl`) : un rejeu ne rappelle pas le modèle.
- Coût annoncé avant toute campagne ; modèle par défaut `openai/gpt-oss-20b` sur Groq.

## Review Focus

1. Le modèle renvoie du texte autour du JSON, ou un JSON avec des colonnes hors catalogue → extraire le premier objet JSON ; colonnes hors catalogue ignorées.
2. Forme inconnue (« nombre », « count ») → intention invalide, pas de valeur par défaut.
3. Une question d'injection directe (« ignore tes consignes… tous les salaires ») → l'intention suit la question ; c'est la règle de périmètre qui doit sonner, pas la comparaison.
4. Panne du modèle (`ModeleEnPanne`) → intention `None` et la campagne continue.
5. Question posée par `rh` (accès total) qui porte sur toute l'entreprise → aucune alerte de périmètre.

---

### Task 1: Intention extraite par un modèle

**Files:** Create `sentinelle/intention.py`, `sentinelle/catalogue.py` ; Test `tests/test_sentinelle_intention.py`

**Interfaces:**
- Produces:
  - `CATALOGUE_HR: dict[str, list[str]]` — tables du schéma HR d'Oracle → colonnes (EMPLOYEES, DEPARTMENTS, JOBS, JOB_HISTORY, LOCATIONS, COUNTRIES, REGIONS).
  - `PERIMETRES = ("moi", "mon_service", "tout", "autre_service")`
  - `@dataclass(frozen=True) class Intention: colonnes: frozenset[str]; forme: str; perimetre: str`
  - `def lire_intention(texte: str, catalogue) -> Intention | None` — premier objet JSON du texte ; `forme ∈ FORMES`, `perimetre ∈ PERIMETRES`, sinon None ; colonnes en majuscules, hors catalogue retirées.
  - `def demander_intention(modele, question: str, contexte: str, catalogue) -> Intention | None` — un appel `modele.completer([...])` ; `ModeleEnPanne` → None.
  - `def vers_empreinte(i: Intention, sensibles) -> Empreinte` — `tables=∅` (inconnues), `etoile=False`.

Tests : JSON entouré de texte lu ; forme `"count"` → None ; colonne `FOO` retirée ; un faux modèle (objet avec `completer`) qui lève `ModeleEnPanne` → None ; le message envoyé au modèle ne contient pas `SELECT`.

### Task 2: Comparateur — périmètre et tables inconnues

**Files:** Modify `sentinelle/comparateur.py` ; Test `tests/test_sentinelle_comparateur.py`

**Interfaces:** `def comparer(intention: Empreinte, reelle: Empreinte, perimetre: str | None = None, acces_total: bool = False) -> Verdict`
- `intention.tables` vide → pas de règle des tables.
- `perimetre in {"tout", "autre_service"}` et `not acces_total` → +4, « question hors du périmètre du profil ».
Tests : tables vides ne comptent pas ; périmètre `tout` pour un manager → +4 ; pour `rh` → 0.

### Task 3: Juger le juge

**Files:** Create `sentinelle/juge.py` ; Test `tests/test_sentinelle_juge.py`

**Interfaces:** `def juger_intentions(paires: list[tuple[QuestionUtile, Intention | None]], sensibles) -> dict` → `{"n", "illisibles", "forme_juste", "sensibles_justes", "colonnes_jaccard_moy"}` contre `empreinte(sql_verite)`.
Test : deux paires fabriquées (une juste, une fausse forme) → `forme_juste == 0.5`.

### Task 4: Campagne et rejeu avec l'intention du modèle

**Files:** Modify `sentinelle/rejeu.py` (option `--intention modele:<nom>`), create `sentinelle/campagne.py` (remplit le cache : questions légitimes, questions des attaques du journal) ; Test `tests/test_sentinelle_campagne.py` (cache relu sans appel).
- Rejeu : légitimes et dépassements avec l'intention du modèle ; **attaques** du journal (lignes `type == "attaque"` avec SQL) : score et raisons, séparés en `reussi` / `filtre_vpd` / autres.
- Annoncer le coût (nombre de questions uniques × coût mesuré d'un pilote de 5) avant la campagne.
- README : section « Sentinelle — phase 2 » avec juger-le-juge, fausses alertes, détections, attaques, et ce que ça ne couvre pas.
