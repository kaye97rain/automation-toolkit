# One-time setup (safe to re-run): create virtual env, install libraries, create .env.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

if (-not (Test-Path ".venv")) { & $python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m playwright install chromium

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Write-Host "`nSetup complete. Activate with:  .\.venv\Scripts\Activate.ps1"
