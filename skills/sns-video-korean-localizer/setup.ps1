$ErrorActionPreference = "Stop"
$setupScript = Join-Path $PSScriptRoot "assets\app\setup.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setupScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
