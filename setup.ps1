$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-CompatiblePython {
    foreach ($version in @("3.12", "3.11", "3.10")) {
        try {
            $path = py "-$version" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $path) { return $path.Trim() }
        } catch { }
    }
    return $null
}

function Find-DenoExecutable {
    $command = Get-Command deno -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $file = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter deno.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($file) { return $file.FullName }
    return $null
}

function Test-DenoVersion($executable) {
    if (-not $executable) { return $false }
    $line = (& $executable --version | Select-Object -First 1)
    if ($line -notmatch '^deno\s+(\d+)\.(\d+)') { return $false }
    return ([int]$Matches[1] -gt 2) -or ([int]$Matches[1] -eq 2 -and [int]$Matches[2] -ge 3)
}

$pythonExe = Find-CompatiblePython
if (-not $pythonExe) {
    Write-Host "Python 3.10~3.12가 필요합니다. Python 3.12 설치를 시작합니다."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget을 찾지 못했습니다. https://python.org 에서 Python 3.12를 설치한 뒤 다시 실행하세요."
    }
    winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements
    $pythonExe = Find-CompatiblePython
    if (-not $pythonExe) { throw "Python 설치 후 새 PowerShell 창에서 setup.ps1을 다시 실행하세요." }
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "FFmpeg 설치를 시작합니다."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget을 찾지 못했습니다. FFmpeg를 직접 설치하고 PATH에 추가하세요."
    }
    winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
}

$denoExe = Find-DenoExecutable
if (-not (Test-DenoVersion $denoExe)) {
    Write-Host "YouTube 지원용 Deno 설치를 시작합니다."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget을 찾지 못했습니다. https://deno.com 에서 Deno 2.3 이상을 설치하세요."
    }
    winget install --id DenoLand.Deno --exact --accept-package-agreements --accept-source-agreements
    $denoExe = Find-DenoExecutable
}
if (-not (Test-DenoVersion $denoExe)) { throw "Deno 2.3 이상을 찾지 못했습니다. 설치 후 setup.ps1을 다시 실행하세요." }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pythonExe -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "설치 완료. .\run.ps1 로 실행하세요. 첫 처리 때 AI 모델을 다운로드합니다."
