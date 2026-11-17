# Campagne complète via OpenRouter (crédit payé à l'usage, pas de quota journalier).
#
#   powershell -File scripts/campagne_openrouter.ps1
#
# Les modèles passent l'un après l'autre (ils manipulent tous la VPD de HR : jamais en
# parallèle). La reprise saute ce qui est déjà mesuré ; une panne arrête proprement.
param([string[]]$Modeles = @("openrouter:openai/gpt-oss-120b", "openrouter:openai/gpt-oss-20b"))
$d = Split-Path -Parent $PSScriptRoot
Set-Location $d
$py = Join-Path $d ".venv\Scripts\python.exe"
$log = Join-Path $d "journal\campagne-openrouter.log"
New-Item -ItemType Directory -Force (Join-Path $d "journal") | Out-Null
foreach ($m in $Modeles) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $m lancé" | Out-File -Append -Encoding utf8 $log
    $nom = $m -replace '[/:]', '_'
    # Jusqu'à 3 passages : une panne arrête un passage sans rien enregistrer de faux, et la
    # reprise saute ce qui est déjà mesuré.
    for ($essai = 1; $essai -le 3; $essai++) {
    $p = Start-Process -FilePath $py -ArgumentList "-u", "-m", "borne.campagne", "--modele", $m, "--sortie", "journal/campagne" `
        -WorkingDirectory $d -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput "journal\campagne-run.$nom.$essai.out" -RedirectStandardError "journal\campagne-run.$nom.$essai.err"
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $m passage $essai code=$($p.ExitCode)" | Out-File -Append -Encoding utf8 $log
    if ($p.ExitCode -eq 0) { break }
    Start-Sleep -Seconds 120
    }
}
"$(Get-Date -Format 'yyyy-MM-dd HH:mm') FINI" | Out-File -Append -Encoding utf8 $log
