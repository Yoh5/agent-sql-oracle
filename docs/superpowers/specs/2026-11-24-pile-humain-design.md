# Vider la pile « humain » en code d'abord — conception courte (24/11/2026)

**Pourquoi.** Sur 182 cas que l'enquêteur rend à un humain, ~70 se tranchent en code (case A) : 57 écritures,
des UNION et des `department_id <> 50` que la règle de périmètre ne voyait pas. Un orchestrateur ne se justifie
que sur ce qui RESTE ; on décide de lui après cette mesure.

**Approches.** (1) orchestrateur directement sur les 182 — écarté : il serait mesuré sur 10 questions uniques,
et paierait un modèle pour ce que le code prouve ; (2) **retenue** : corrections en code, puis nouvelle mesure.

**Ce qui change.**
- `perimetre.ecriture(sql) -> bool` : toute instruction autre que SELECT / WITH (UPDATE, DELETE, INSERT, MERGE,
  DDL, GRANT, bloc PL/SQL, EXEC / CALL), y compris illisible par sqlglot → `traiter` coupe (raison « écriture »).
- `hors_regle` : toute comparaison de la colonne de partition autre que `= valeur permise` est hors règle
  (`<>`, `!=`, `NOT IN`, `>`, `<`, `>=`, `<=`, `IN (…)` avec une autre valeur).
- `construire_sonde` : un UNION est sondé branche par branche (`SELECT 1 FROM dual WHERE EXISTS (b1) OR EXISTS (b2)`).

**Mesure.** Légitimes : toujours 0 coupé. Pile « humain » avant / après.
