$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (!(Test-Path ".grader-system-venv")) {
    py -m venv .grader-system-venv
}
& .\.grader-system-venv\Scripts\python.exe -m pip install --upgrade pip
& .\.grader-system-venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.grader-system-venv\Scripts\python.exe datasets\prepare_hidden_tests.py
Write-Host ""
Write-Host "Checking environment..."
& .\.grader-system-venv\Scripts\python.exe doctor.py
Write-Host ""
Write-Host "If MongoDB is not running and Docker Desktop is installed:"
Write-Host "docker compose -f docker-compose.mongo.yml up -d"
