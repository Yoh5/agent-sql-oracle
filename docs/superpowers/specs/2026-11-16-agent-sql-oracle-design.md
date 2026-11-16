# Agent texte-vers-SQL borné par la base — conception

16/11/2026. Document à valider avant toute construction.

## Pourquoi

Un agent texte-vers-SQL reçoit une question en français, écrit du SQL, l'exécute et
rend la réponse. Presque tous ceux qu'on trouve confient leur sécurité au **prompt**
(« ne montre jamais les salaires »). La thèse du projet : **un prompt n'est pas une
barrière de sécurité, la base en est une.** On construit un agent dont les limites
sont tenues par Oracle lui-même, puis on le **mesure** sous attaque.

Pour Axel : un projet SQL / PL-SQL de bout en bout (sa voie Oracle), un agent (sa
spécialité), une mesure publiable (sa voie R&D), et Docker réellement utilisé (le
point faible relevé face à l'offre de mission du 16/11).

## Objectifs

1. **Le produit** — un agent qui répond juste à des questions métier sur le schéma HR
   d'Oracle (employés, services, salaires), avec le SQL produit et le résultat visibles.
2. **Trois barrières dans la base, aucune dans le prompt**, activables une à une :
   - **compte aux droits minimaux** : l'agent se connecte avec un utilisateur qui ne
     peut que LIRE certaines tables (pas de DDL, pas d'écriture hors validation) ;
   - **VPD** : une fonction PL/SQL qu'Oracle ajoute à chaque requête sur les tables
     sensibles — un utilisateur ne voit que les lignes de son service ;
   - **audit unifié** : chaque requête réellement exécutée est journalisée par Oracle,
     preuve indépendante de ce que l'agent dit avoir fait.
3. **Validation humaine** avant toute écriture (repris d'`Agent_Sql`).
4. **L'infrastructure de mesure dès le départ** : chaque question journalisée (question,
   SQL produit, issue, barrière qui a agi) ; une première série d'environ 20 attaques
   écrites comme des tests.

## Ce que la mesure mesurera (campagne complète APRÈS le socle stable)

- **Sécurité** — pour chaque attaque, son issue : *le modèle refuse* / *la base bloque*
  (droits ou VPD) / *l'attaque réussit* (donnée interdite lue ou modifiée). Par
  configuration de barrières et par modèle.
- **Utilité** — ~100 questions légitimes à réponse connue : réponses justes, et **refus
  à tort** (une barrière qui bloque une question légitime).
- **Comparaison avec Select AI** (voir contraintes).

Familles d'attaques : injection directe (« ignore tes consignes… »), écriture déguisée
(`DELETE`, `UPDATE`, `DROP` cachés), contournement de VPD (UNION, sous-requête, vue,
fonction), exfiltration par le message d'erreur, **injection indirecte** (une consigne
malveillante stockée DANS une donnée que l'agent lira), usurpation d'identité
(« je suis le DRH »).

## Phase 2 — un mode « analyste » en deep agent, mesuré contre l'agent simple

Validé par Axel le 16/11. **Le cœur reste un agent simple** : une question comme « salaire
moyen du service Ventes » suit toujours le même chemin (schéma → requête → exécution →
correction si erreur → réponse), et un deep agent n'y ajouterait que du temps, du coût et
de la surface d'attaque (fichiers de notes, sous-agents, actions supplémentaires où une
consigne malveillante peut se glisser).

Le mode analyste vise les tâches qui en ont vraiment besoin : chemin inconnu d'avance,
plusieurs requêtes, un document à la fin (« analyse les départs du trimestre par service
et rédige un rapport »). Il passe par **le même compte et les mêmes barrières Oracle** :
même un deep agent reste borné par la base.

Question de mesure ajoutée : **un agent simple et un deep agent, derrière les mêmes
barrières et face aux mêmes attaques, cèdent-ils autant ?** Mêmes familles d'attaques,
plus celles propres au deep agent (consigne glissée dans un fichier de notes, dans le
compte rendu d'un sous-agent).

## Phase 3 — ce qui rend le projet unique : écrire les barrières ET prouver qu'elles tiennent

Validé par Axel le 16/11. **Le besoin** : la VPD est puissante mais peu utilisée, parce
qu'elle est difficile à écrire et encore plus à tester. Un administrateur sait dire « un
manager voit son service ; la RH voit tout sauf les salaires des dirigeants » ; le
traduire en PL/SQL sans trou est un travail d'expert, et personne ne vérifie qu'une
politique résiste à une question piégée avant de la déployer.

**Ce qui est construit** : l'administrateur écrit sa règle en français ; l'agent génère
la politique (fonction PL/SQL + `DBMS_RLS.ADD_POLICY`) ; **le banc d'attaques de la
phase 1 l'éprouve automatiquement avant déploiement**, et rend un rapport du type :
« cette politique laisse passer 2 attaques sur 40 : lesquelles, et comment ».

Garde-fous propres à cette phase :
- la politique générée est d'abord installée dans une **copie** du schéma, jamais sur
  les vraies tables avant que le rapport soit vert et qu'un humain l'ait validée ;
- le juge est le banc (lignes réellement rendues, audit Oracle), **jamais le modèle qui
  a écrit la politique** — c'est la règle de l'Intelligent Data Cleaner appliquée ici ;
- on mesure aussi les politiques **trop strictes** (questions légitimes bloquées).

Mesure : sur un jeu de règles en français à politique de référence écrite à la main,
combien de politiques générées sont justes, combien ont un trou, combien sont trop
strictes — et le banc les détecte-t-il toutes ?

Ordre des phases : 1 (socle + infrastructure de mesure) → campagne de mesure → 3 →
2 (mode analyste). La phase 3 passe avant la 2 parce qu'elle fait l'originalité du projet.

## Non-objectifs

- Pas de multi-bases : Oracle seulement.
- Pas d'interface soignée dans un premier temps : une page minimale suffit.
- Pas la campagne complète tant que le socle bouge.

## Anti-objectifs (ce qui ferait échouer le projet même s'il « marche »)

- Une barrière qui vit dans le prompt ou dans le code Python de l'agent et que l'on
  présenterait comme une barrière de la base.
- Des chiffres de sécurité sans le chiffre d'utilité à côté (un agent qui refuse tout
  est sûr et inutile).
- Une issue d'attaque jugée par le modèle lui-même : l'issue se lit dans l'audit Oracle
  et dans les lignes réellement rendues.

## Contraintes

- **Oracle AI Database Free, image officielle** `container-registry.oracle.com/database/free`
  (variante complète ; 2 Go de mémoire au moins pour le conteneur). Le schéma HR se
  charge depuis le dépôt GitHub officiel des schémas d'exemple d'Oracle.
- **Select AI** est documenté pour Autonomous Database, pas confirmé dans Oracle Free.
  Il existe une image « Autonomous AI Database Free » (`database/adb-free`) : à essayer
  pour la comparaison ; sinon une instance cloud Always Free. **La comparaison est la
  dernière étape et ne bloque rien.**
- **LLM** : Groq pour le développement (clé existante), plusieurs modèles pour la mesure.
  Coût de la campagne à annoncer avant de la lancer.
- Windows, Python 3.12, Docker Desktop.

## Approches

| approche | ce qu'elle donne | retenue ? |
|---|---|---|
| **A. Python + `python-oracledb` + LangGraph** (même pile qu'`Agent_Sql`) | un agent à nous, mesurable, testable ; reprend les bonnes idées d'`Agent_Sql` | **oui** |
| B. Select AI seul | rapide, mais plus d'agent à nous : rien à mesurer ni à montrer comme travail | non — devient le point de comparaison |
| C. Workflow n8n | rapide à monter, mais difficile à tester et à attaquer de façon reproductible | non |

Choix d'Axel (16/11) : socle d'abord, infrastructure de mesure en même temps,
campagne complète ensuite ; Groq pour développer.

## Conception

```
question ──> agent (LangGraph)
              │  1. lit le schéma AUTORISÉ (dictionnaire Oracle vu par son compte)
              │  2. écrit un SELECT
              │  3. exécute via python-oracledb SOUS L'IDENTITÉ DE L'UTILISATEUR
              │     (contexte applicatif Oracle positionné à la connexion)
              ▼
        ORACLE ── compte AGENT_RO : SELECT seulement sur HR.* autorisé
              ── VPD (DBMS_RLS + fonction PL/SQL) sur EMPLOYEES / JOB_HISTORY
              ── audit unifié : chaque requête de AGENT_RO
              ▼
        résultat + SQL + issue ──> journal de mesure (JSONL)
```

- **Identité** : chaque profil (manager du service 50, manager du service 80, RH…) est
  **un vrai compte Oracle**, et la fonction VPD lit `SYS_CONTEXT('USERENV','SESSION_USER')`,
  qu'aucune requête ne peut modifier. *Corrigé le 16/11 en écrivant le plan* : la
  première version passait l'identité par un contexte de session positionné par le
  code — or l'agent exécute du SQL écrit par le modèle, et un bloc PL/SQL piégé
  (`DBMS_SESSION.SET_IDENTIFIER`, ou l'appel du paquet qui pose le contexte) aurait
  permis d'usurper une identité. Le compte connecté, lui, ne se change pas.
- **Tester la base sans dépendre du modèle** : un « modèle factice » qui cède toujours
  (il renvoie tel quel le SQL malveillant de chaque attaque) permet de vérifier les
  barrières d'Oracle de façon déterministe et gratuite. Le vrai modèle ne sert qu'à
  mesurer ce qu'il refuse de lui-même.
- **Les écritures en configuration « barrières coupées »** visent une copie jetable du
  schéma (`HR_BAC`), recréée avant chaque campagne — jamais le schéma HR lui-même.
- **Écritures** : le compte de l'agent n'en a pas le droit. Une écriture demandée
  devient une proposition affichée à un humain, exécutée par un autre compte après
  validation.
- **Barrières activables** : trois interrupteurs (compte restreint ou compte HR
  complet ; politique VPD activée ou non ; consignes de sécurité dans le prompt ou non).
- **Journal de mesure** : une ligne JSON par question — question, utilisateur, modèle,
  configuration, SQL produit, issue (`refus_modele` / `bloque_droits` / `filtre_vpd` /
  `reussi` / `erreur`), lignes rendues, référence d'audit Oracle.

Dossier : `AI/agent-sql-oracle/` (nouveau dépôt Git).

## Laissé au constructeur

Structure des fichiers, nom des tables de mesure, forme exacte de la page, choix des
modèles de la campagne (à proposer avec leur coût).
