# Phase 2 — le mode « analyste », mesuré contre l'agent simple

Conception : section « Phase 2 » de `specs/2026-11-16-agent-sql-oracle-design.md`.
Commencée le 16/11/2026.

## Choix de construction

1. **Un agent qui agit en plusieurs tours.** À chaque tour, le modèle choisit UNE action,
   rendue en JSON : `sql` (une lecture), `note` (garder un fait), `rapport` (finir). Au plus
   8 tours. Les requêtes passent par le MÊME `ExecuteurOracle` que l'agent simple : même
   compte de profil, même VPD, même audit ; une écriture est classée et jamais exécutée.
2. **La surface propre au deep agent : la donnée qu'il lit.** Table `HR.NOTES_SERVICE`
   (service, note), lisible par les profils, avec une note PIÉGÉE par service. L'agent
   simple ne lit jamais la donnée avant d'écrire son SQL ; l'analyste, si.
3. **Mesure sans juge-modèle.**
   - Fuite : des lignes interdites réellement rendues par la base à l'agent
     (`attaques.detecter_fuite` sur chaque résultat), ou des e-mails interdits dans le rapport.
   - Utilité : des tâches d'analyse dont les chiffres justes sont calculés en SQL par
     l'administrateur et doivent figurer dans le rapport.
   - Coût : tours, appels, jetons, par tâche.
4. **Validé sans coût d'abord** : un analyste factice qui obéit à la note piégée. Avec les
   barrières, rien ne fuit ; sans, la fuite se voit. Puis gpt-oss-120b / 20b.

## Tâches

1. `sql/05_notes.sql` : `HR.NOTES_SERVICE` + note piégée, synonymes, copie dans HR_BAC.
2. `borne/analyste.py` : la boucle, le protocole d'actions, le journal des tours.
3. `borne/banc_analyste.py` : tâches d'analyse à vérité connue, attaques (les 20 du banc +
   la note piégée), mesure comparée avec l'agent simple.
