$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "먼저 PowerShell에서 .\setup.ps1 을 실행하세요."
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $ffmpeg) {
        throw "FFmpeg를 찾을 수 없습니다. .\setup.ps1 을 다시 실행하세요."
    }
    $env:Path = "$($ffmpeg.DirectoryName);$env:Path"
}

$deno = Get-Command deno -ErrorAction SilentlyContinue
$denoExe = if ($deno) { $deno.Source } else {
    $file = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter deno.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($file) { $file.FullName }
}
if (-not $denoExe) { throw "YouTube 지원용 Deno를 찾지 못했습니다. .\setup.ps1 을 다시 실행하세요." }
$denoVersion = (& $denoExe --version | Select-Object -First 1)
if ($denoVersion -notmatch '^deno\s+(\d+)\.(\d+)' -or ([int]$Matches[1] -lt 2) -or ([int]$Matches[1] -eq 2 -and [int]$Matches[2] -lt 3)) {
    throw "Deno 2.3 이상이 필요합니다. .\setup.ps1 을 다시 실행하세요."
}
$env:Path = "$([IO.Path]::GetDirectoryName($denoExe));$env:Path"
& .\.venv\Scripts\python.exe app.py
