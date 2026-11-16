# Phase 3 — écrire une règle d'accès, et la prouver avant de la déployer

Conception : section « Phase 3 » de `specs/2026-11-16-agent-sql-oracle-design.md`.
Commencée le 16/11/2026, pendant que la campagne attend le quota Groq.

## Choix de construction

1. **Une copie isolée.** Schéma `HR_ESSAI` (copie de HR), comptes de test `ESSAI_M50`,
   `ESSAI_M80`, `ESSAI_RH` dont les synonymes visent la copie seulement, et une table
   `ESSAI_POL.PROFILS` (compte → service, rôle, employé). Une politique candidate n'est
   jamais posée sur HR.
2. **Le code généré est confiné.** La fonction de politique est créée DANS `ESSAI_POL`,
   un schéma qui ne peut que lire `PROFILS` : en droits du définisseur, même une
   fonction malveillante ne peut que rendre un prédicat. Avant création, un contrôle
   statique refuse : SQL dynamique, paquets système (`DBMS_`, `UTL_`, `SYS.`), écritures,
   DDL, `PRAGMA AUTONOMOUS_TRANSACTION`, plus d'une unité, tout ce qui n'est pas une
   `FUNCTION … RETURN VARCHAR2`.
3. **Le juge compare des lignes, pas du texte.** Pour chaque profil et chaque table
   protégée : identifiants visibles avec la politique candidate contre identifiants que
   rend la politique de RÉFÉRENCE (écrite à la main). En trop = **trou** ; en moins =
   **trop stricte**. Puis les 20 attaques du banc sont rejouées sur la copie.
4. **Le banc est validé sans modèle.** Chaque règle du catalogue a sa référence et des
   **mutants** écrits à la main (un trou, un excès). Le banc doit tous les attraper :
   c'est la question « le banc les détecte-t-il toutes ? », et elle ne coûte aucun appel.
5. **Le modèle vient en dernier.** Générer la politique depuis la règle en français
   (Groq, quota gratuit) se branche sur le même juge.

## Tâches

1. `sql/04_essai.sql` : copie, comptes de test, `ESSAI_POL`, profils ; installateur `--essai`.
2. `borne/politique.py` : contrôle statique ; installer / retirer une politique candidate
   sur la copie (via `SEC_ADMIN`).
3. `borne/preuve.py` : le juge (lignes visibles par profil contre la référence ; attaques).
4. `borne/regles.py` : catalogue de règles en français, références, mutants ; test réel :
   chaque référence est jugée juste, chaque mutant est attrapé.
5. Génération par le modèle + rapport ; mesure sur le catalogue.
