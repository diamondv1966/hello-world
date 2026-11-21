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
    # The owner pastes the key into .env by hand; a bot must never type or see it.
    "GEMINI_API_KEY=`nGEMINI_MODEL=gemini-2.5-flash" | Out-File -Encoding utf8 .env
    Write-Host "OWNER: open .env in Notepad and paste your Gemini key after GEMINI_API_KEY= (same key as AURIX)"
}

python -m unittest tests/test_pipeline.py
python aff.py doctor
Write-Host "`nDone. Daily run: run_daily.bat"
