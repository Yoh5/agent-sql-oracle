# Relance planifiée de la campagne (tâche Windows « AgentSQL-Campagne », toutes les 4 h).
#
# Pourquoi : l'offre gratuite de Groq plafonne chaque modèle à 200 000 jetons et 1 000
# requêtes par jour (16/11/2026). La campagne s'arrête proprement quand le quota est
# atteint et se reprend là où elle en était : il suffit de la relancer régulièrement.
# Chaque modèle a son propre quota : on passe au suivant même si le premier s'arrête.
#
# Supprimer la tâche : Unregister-ScheduledTask -TaskName AgentSQL-Campagne -Confirm:$false
$ErrorActionPreference = "Continue"
$d = Split-Path -Parent $PSScriptRoot
Set-Location $d
$log = Join-Path $d "journal\campagne-planifiee.log"
New-Item -ItemType Directory -Force (Join-Path $d "journal") | Out-Null
function Ecrire($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $m" | Out-File -Append -Encoding utf8 $log }

Ecrire "démarrage"

# Terminé ? (les deux journaux complets : rien à faire)
if (Test-Path (Join-Path $d "journal\campagne\FINIE")) { Ecrire "campagne déjà finie"; exit 0 }

# Docker et Oracle
docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    for ($i = 0; $i -lt 60; $i++) { Start-Sleep 5; docker info 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { break } }
}
docker compose up -d 2>&1 | Out-Null
# Prêt = on peut s'y connecter. (Chercher « DATABASE IS READY » dans les dernières lignes
# du journal du conteneur ne marche pas : quand Oracle tourne depuis longtemps, la ligne
# est remontée, et le script attendait 7 min 30 pour rien — vu le 16/11/2026.)
$py = Join-Path $d ".venv\Scripts\python.exe"
$sonde = "import os,oracledb;from dotenv import load_dotenv;load_dotenv('.env');oracledb.connect(user='SEC_ADMIN',password=os.environ['PERSONA_PASSWORD'],dsn=os.environ['ORACLE_DSN']).close()"
$pret = $false
for ($i = 0; $i -lt 60; $i++) {
    & $py -c $sonde 2>$null
    if ($LASTEXITCODE -eq 0) { $pret = $true; break }
    Start-Sleep 10
}
if (-not $pret) { Ecrire "Oracle injoignable après 10 min : abandon"; exit 1 }
Ecrire "Oracle prêt, reprise"

$finis = 0
foreach ($m in @("openai/gpt-oss-120b", "openai/gpt-oss-20b")) {
    $sortie = & $py -m borne.campagne --modele $m --sortie journal/campagne 2>&1 | Out-String
    $code = $LASTEXITCODE
    Ecrire "$m code=$code $(($sortie -split "`n" | Where-Object { $_ -match 'fait|panne|reprise' }) -join ' / ')"
    if ($code -eq 0) { $finis++ }
}
if ($finis -eq 2) { New-Item -ItemType File -Force (Join-Path $d "journal\campagne\FINIE") | Out-Null; Ecrire "CAMPAGNE FINIE" }
