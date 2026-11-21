# One-time setup on Windows. Run in PowerShell from this folder:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

if (-not (Have python)) {
    Write-Host "Installing Python 3.12 ..."
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
}
if (-not (Have ffmpeg)) {
    Write-Host "Installing FFmpeg ..."
    winget install -e --id Gyan.FFmpeg.Essentials --accept-source-agreements --accept-package-agreements
}
# winget installs need a fresh PATH in this window
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

python -m pip install --upgrade edge-tts pythainlp

if (-not (Test-Path .env)) {
    $key = Read-Host "Paste your GEMINI_API_KEY (same key as AURIX .env.local; free at aistudio.google.com)"
    "GEMINI_API_KEY=$key`nGEMINI_MODEL=gemini-2.5-flash" | Out-File -Encoding utf8 .env
}

python -m unittest tests/test_pipeline.py
python aff.py doctor
Write-Host "`nDone. Daily run: run_daily.bat"
