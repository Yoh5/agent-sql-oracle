# Agent SQL borné par Oracle

Un agent qui traduit une question en français en SQL Oracle, l'exécute et rend la
réponse — mais dont **les limites sont tenues par la base, pas par le prompt** :
un compte qui ne peut que lire, une règle d'accès par ligne (VPD) écrite en PL/SQL,
et l'audit d'Oracle. Puis on l'attaque, et on mesure qui arrête l'attaque.

Conception : `docs/superpowers/specs/2026-11-16-agent-sql-oracle-design.md`
Plan de la phase 1 : `docs/superpowers/plans/2026-11-16-phase1-socle.md`

## État (16/11/2026)

| tâche | état |
|---|---|
| 0–1 dépôt, barrières, profils | fait |
| 2 classement des instructions (routage, pas sécurité) | fait |
| 3 modèle Groq + modèle factice qui cède toujours | fait, Groq vérifié |
| 4 tour et journal de mesure | fait |
| 5 catalogue de 20 attaques en six familles | fait |
| 6 agent (graphe LangGraph) | fait |
| 7–10 Oracle, exécuteur, banc, page | **attend Oracle** |

## Installer

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # puis remplir les mots de passe et GROQ_API_KEY
pytest                      # sans Oracle, les tests qui en ont besoin se sautent
```

## Démarrer Oracle

Oracle AI Database Free tourne dans Docker. **Sur ce poste, Docker ne démarre pas
(16/11/2026)** : son journal dit `HCS_E_HYPERV_NOT_INSTALLED` — la virtualisation est
bien active dans le BIOS, mais l'hyperviseur de Windows est arrêté. À faire **une fois,
dans un terminal administrateur**, puis redémarrer :

```powershell
wsl --install --no-distribution
# ou : dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
bcdedit /set hypervisorlaunchtype auto
```

Vérification après redémarrage (doit afficher `True`) :

```powershell
(Get-CimInstance Win32_ComputerSystem).HypervisorPresent
```

Ensuite : lancer Docker Desktop, puis

```bash
docker compose up -d            # image container-registry.oracle.com/database/free:latest
python scripts/installer.py --tout
```

## Ce que ce projet ne fait pas encore

La campagne de mesure complète, la comparaison avec Select AI, la génération de
politiques VPD (phase 3) et le mode analyste (phase 2) : voir la conception.
