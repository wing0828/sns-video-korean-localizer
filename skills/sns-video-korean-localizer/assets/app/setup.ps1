$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Find-CompatiblePython {
    foreach ($version in @("3.12", "3.11", "3.10")) {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            $candidate = & $launcher.Source "-$version" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate) { return $candidate.Trim() }
        }
    }
    return $null
}

function Find-WinGetExecutable([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $packageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -LiteralPath $packageRoot) {
        $file = Get-ChildItem -LiteralPath $packageRoot -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($file) { return $file.FullName }
    }
    return $null
}

function Install-WinGetPackage([string]$Id, [string]$Label) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw "winget is required to install $Label. Install App Installer from Microsoft Store, then run setup.ps1 again." }
    & $winget.Source install --id $Id --exact --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "$Label installation failed with exit code $LASTEXITCODE." }
}

$pythonExe = Find-CompatiblePython
if (-not $pythonExe) {
    Install-WinGetPackage "Python.Python.3.12" "Python 3.12"
    $pythonExe = Find-CompatiblePython
    if (-not $pythonExe) { throw "Python was installed but is not visible yet. Open a new PowerShell window and run setup.ps1 again." }
}

if (-not (Find-WinGetExecutable "ffmpeg")) { Install-WinGetPackage "Gyan.FFmpeg" "FFmpeg" }
if (-not (Find-WinGetExecutable "deno")) { Install-WinGetPackage "DenoLand.Deno" "Deno" }

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    & $pythonExe -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the local Python environment." }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Python package installation failed." }

Write-Host "Setup complete. Run .\run.ps1 to open the local app."
