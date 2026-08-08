$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "The local environment is missing. Run .\setup.ps1 first."
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

$ffmpegExe = Find-WinGetExecutable "ffmpeg"
$ffprobeExe = Find-WinGetExecutable "ffprobe"
$denoExe = Find-WinGetExecutable "deno"
if (-not $ffmpegExe -or -not $ffprobeExe -or -not $denoExe) {
    throw "FFmpeg, ffprobe, or Deno is missing. Run .\setup.ps1 first."
}
$env:Path = "$([IO.Path]::GetDirectoryName($ffmpegExe));$([IO.Path]::GetDirectoryName($denoExe));$env:Path"
& .\.venv\Scripts\python.exe app.py
