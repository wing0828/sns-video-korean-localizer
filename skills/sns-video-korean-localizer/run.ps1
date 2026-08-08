$ErrorActionPreference = "Stop"
$runScript = Join-Path $PSScriptRoot "assets\app\run.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
