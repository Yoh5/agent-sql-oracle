# Comparaison Select AI / notre agent, MÊME modèle (gpt-4.1-mini), MÊME base (Autonomous Database Free).
# Les deux manipulent la VPD de la même base : ils passent l'un après l'autre, jamais ensemble.
#   powershell -File scripts/campagne_select_ai.ps1
$d = Split-Path -Parent $PSScriptRoot
Set-Location $d
$py = Join-Path $d ".venv\Scripts\python.exe"
$log = Join-Path $d "journal\select_ai.log"
New-Item -ItemType Directory -Force (Join-Path $d "journal\select_ai") | Out-Null
# La base : Docker, puis le conteneur adb-free (prêt quand « healthy »).
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
for ($i = 0; $i -lt 60; $i++) { docker info *> $null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 10 }
docker start adb-free *> $null
for ($i = 0; $i -lt 60; $i++) { if ((docker ps --filter name=adb-free --format "{{.Status}}") -match "\(healthy\)") { break }; Start-Sleep 15 }
$passes = @(
    @("selectai:gpt-4.1-mini", "C1V1P0", "C1V0P0", "C0V1P0", "C0V0P0"),
    @("openrouter:openai/gpt-4.1-mini", "C1V1P1", "C1V1P0", "C1V0P1", "C1V0P0", "C0V1P1", "C0V1P0", "C0V0P1", "C0V0P0")
)
foreach ($p in $passes) {
    $m = $p[0]; $cfg = $p[1..($p.Length - 1)]
    for ($essai = 1; $essai -le 3; $essai++) {
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $m passage $essai" | Out-File -Append -Encoding utf8 $log
        $nom = $m -replace '[/:]', '_'
        $args = @("-u", "-m", "borne.campagne", "--adb", "--modele", $m, "--configs") + $cfg
        $pr = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $d -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput "journal\select_ai\$nom.$essai.out" -RedirectStandardError "journal\select_ai\$nom.$essai.err"
        "$(Get-Date -Format 'yyyy-MM-dd HH:mm') $m code=$($pr.ExitCode)" | Out-File -Append -Encoding utf8 $log
        if ($pr.ExitCode -eq 0) { break }
        Start-Sleep 120
    }
}
"$(Get-Date -Format 'yyyy-MM-dd HH:mm') FINI" | Out-File -Append -Encoding utf8 $log
