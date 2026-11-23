# Sentinelle des agents SQL — conception (23/11/2026)

## Pourquoi

Les barrières de la base (comptes par profil, VPD, droits minimaux) limitent ce qu'un agent texte-vers-SQL
**peut** voir. Elles ne disent rien de ce qu'il fait **à l'intérieur** de ses droits. Un manager qui demande
« combien de personnes dans mon service ? » et reçoit la liste nominative avec les salaires n'enfreint
aucune règle de la base : la réponse dépasse simplement la question. C'est la porte que prend une injection
plausible, et c'est ce que la minimisation des données (loi 09-08) demande d'éviter.

La sentinelle observe chaque échange — **question, identité, SQL, ce que la base a rendu** — et agit sur le
**décalage** entre ce qui a été demandé et ce qui a été fait.

**Pour qui** : l'équipe sécurité ou le DBA d'une organisation qui déploie un agent texte-vers-SQL
(notre `borne/agent.py`, l'analyste, ou Select AI).

Origine : [[idee-sentinelle-agents-sql]] (mémoire), passée au scanner le 18/11 ; méthode
« orientation-agents » (23/11) appliquée action par action.

## Objectifs

1. Détecter le décalage intention / action, y compris **dans les droits** (ce que la VPD ne voit pas).
2. **Répondre plutôt que bloquer** quand c'est possible : réécrire la requête au minimum nécessaire.
3. Voir les extractions **découpées en plusieurs questions** innocentes (suivi de session).
4. Proposer des règles de blocage, **prouvées sur le banc** avant qu'un humain les valide.
5. Tout mesurer : fuites évitées, réponses légitimes conservées, fausses alertes, résistance à un
   attaquant qui cible la sentinelle elle-même.

## Non-objectifs

- Pas de nouvelle base, pas de production, pas d'interface au-delà d'un affichage dans `page.html`
  si le temps le permet.
- La sentinelle ne modifie **jamais** les politiques de la base elle-même.
- Pas de classement de modèles.

## Anti-objectifs (échec même si « ça marche »)

- Une sentinelle qui bloque souvent des utilisateurs légitimes (alarme permanente = pire qu'absente).
- Un verdict final pris par un modèle qui a lu le texte de l'attaquant.
- Des chiffres annoncés uniquement sur nos propres attaques.

## Contraintes

- Python, dans ce dépôt (paquet `sentinelle/`), réutilise `borne/` (journal, bancs YAML, exécuteur Oracle).
- Oracle Free en Docker, port 1522 (1521 = Oracle locaux, à ne pas toucher).
- Budget API faible (quelques dollars par campagne, coût annoncé avant) ; modèles via Groq / OpenRouter.
- Dépôt privé `Yoh5/agent-sql-oracle`.
- Calendrier : le Fellows (27/11) passe avant ; la phase 1 est hors ligne et ne coûte rien.

## Approches considérées

| | Principe | Pour | Contre |
|---|---|---|---|
| A. Règles seules | analyser le SQL, comparer aux mots de la question | gratuit, explicable | fragile aux formulations nouvelles ; ne comprend pas l'intention |
| B. Un LLM juge tout (dont « un second agent compare l'entrée et la sortie du premier ») | souple | le juge lit la question de l'attaquant : une injection peut tromper les deux ; coût |
| **C. Cœur en code + agent autour** (retenue) | l'intention est extraite par un petit modèle qui ne voit ni SQL ni données ; le **code** compare intention et empreinte du SQL ; un agent enquête, répare, dialogue et apprend dans la zone ambiguë | ce qui décide ne lit pas le texte de l'attaquant ; reste agentique là où l'erreur coûte peu | plus de pièces ; l'extraction d'intention doit être mesurée |

Choix de C fait le 23/11 (l'utilisateur m'a laissé trancher entre A, B, C et sa proposition d'un second agent
vérificateur). Sa proposition est **intégrée comme outil** de l'agent : un « second avis » d'un modèle d'une
**autre famille** dans la zone ambiguë — une preuve de plus, jamais le verdict. Son apport est mesuré.

## Architecture

```
échange (question, profil, SQL, colonnes rendues, nb lignes)
   │
   ├─► 1. INTENTION  (petit modèle, sortie JSON stricte ; ne voit NI le SQL NI les données)
   │       {colonnes_demandees, forme: compte|somme|moyenne|liste|detail, perimetre: moi|service|tout,
   │        limite?}
   ├─► 2. EMPREINTE  (code, sqlglot dialecte oracle)
   │       tables, colonnes sorties, colonnes sensibles (depuis bancs/*/banc.yaml : `sensibles`),
   │       agrégats, filtres, nb lignes (journal) ou estimé (EXPLAIN PLAN)
   ├─► 3. COMPARATEUR (code) ─► score d'écart + raisons lisibles
   │       ex. « colonne sensible SALARY non demandée », « liste rendue pour une question de compte »,
   │       « 1 lignes attendues, 45 rendues »
   └─► 4. DÉCISION par paliers
           net, sans écart ............ laisser passer
           net, écart réparable ....... RÉÉCRIRE au minimum (C)  — la réécriture repasse au comparateur
           ambigu ..................... AGENT ENQUÊTEUR (D)
           règle de blocage atteinte .. COUPER (A, code seulement)
```

### L'agent enquêteur (zone ambiguë)

Outils, **tous en lecture seule** :
- historique de la session (questions et empreintes précédentes du même compte) ;
- habitudes du profil (empreintes usuelles dans le trafic légitime) ;
- dictionnaire de la base (colonnes sensibles, cardinalités) ;
- estimer les lignes d'une requête sans l'exécuter ;
- proposer une réécriture minimale (toujours revalidée par le comparateur) ;
- **second avis** d'un modèle d'une autre famille ;
- demander une confirmation à l'utilisateur (B).

Sortie : **une action de la liste fermée** (laisser, réécrire, masquer des colonnes, demander confirmation,
signaler au DBA) + **les preuves citées** (question, SQL, ligne d'historique). Il ne peut pas couper une
session : seule une règle en code le fait.

### L'apprentissage (B)

À partir des incidents confirmés, l'agent propose une règle ; le banc la rejoue sur tout le trafic étiqueté
(détections ET fausses alertes) ; un humain valide. Rien n'est appliqué sans validation.

## Données

1. **Trafic existant**, `journal/campagne/*.jsonl` : ~2 700 échanges étiquetés (~1 600 questions légitimes,
   ~1 100 attaques ; ~2 100 avec SQL). Sert de contrôle et de mesure des fausses alertes.
2. **Nouveau jeu « dépassement dans les droits »** (le cas que la VPD ne voit pas, absent aujourd'hui) :
   pour chaque question légitime, une requête **trop large mais autorisée** (liste au lieu d'un compte,
   colonne sensible en plus, périmètre élargi dans les droits). Étiqueté par construction.
3. **Attaques externes** : SecureSQL (EMNLP 2024, 932 cas) et le jeu de Chafik et al. (2025), adaptés aux
   schémas HR et hôpital — après lecture de leurs licences.
4. **Attaquant adaptatif** : un modèle d'une autre famille que le défenseur, qui voit les verdicts de la
   sentinelle et cherche à la contourner (sur notre propre système).
5. **Scénarios multi-tours** : extractions découpées en questions innocentes.

Le jeu d'intentions pour « juger le juge » : ~100 questions annotées à la main (colonnes demandées, forme,
périmètre), relues par l'utilisateur.

## Mesures

- Fuites évitées (attaques qui ont rendu des données, par palier d'action).
- Réponses légitimes conservées, dont les **réécritures justes** (vérité : le SQL admin du banc d'utilité).
- Fausses alertes sur le trafic légitime (le chiffre qui décide si l'outil est utilisable).
- Extractions multi-tours attrapées par l'enquête et ratées par le comparateur seul.
- Taux de retournement de l'agent par l'attaquant adaptatif ; apport mesuré du second avis.
- Exactitude de l'extraction d'intention contre les annotations (juger le juge).
- Coût et latence par échange.
Toujours : ce que la mesure ne couvre pas.

## Ordre de construction

1. **Hors ligne, sans coût** : empreinte (sqlglot) + comparateur + rejeu du journal + jeu « dépassement dans
   les droits » → première mesure (détections / fausses alertes avec une intention annotée à la main).
2. Extraction d'intention par un petit modèle + juger le juge.
3. Réécriture minimale + décision par paliers.
4. Agent enquêteur (outils en lecture seule, second avis), scénarios multi-tours.
5. Attaques externes, attaquant adaptatif.
6. En ligne : branchement sur `borne/agent.py` (avant l'envoi de la réponse).

## Laissé au constructeur

- Le format exact du score et des seuils (calibrés sur le trafic légitime, pas choisis a priori).
- Le choix du petit modèle d'intention (le moins cher qui atteint l'exactitude visée).
- La structure des tests (dans `tests/`, comme le reste du dépôt).

## Décisions prises par moi en relisant (à corriger si besoin)

- **Le jeu « dépassement dans les droits » se génère en code**, par mutation des requêtes de vérité du banc
  d'utilité (`borne/utilite.py`) : retirer l'agrégat, ajouter une colonne sensible, élargir un filtre sans
  sortir de la règle VPD du profil. Étiqueté par construction, rejouable, gratuit.
- **Le journal n'a pas d'identifiant de session** : les scénarios multi-tours sont construits à part
  (suites de questions) ; le trafic existant est traité question par question.
