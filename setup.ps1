$ErrorActionPreference = "Stop"
python -m venv .grader-system-venv
& .\.grader-system-venv\Scripts\python.exe -m pip install --upgrade pip
& .\.grader-system-venv\Scripts\pip.exe install -r requirements.txt
Write-Host "[1/2] Grader Python environment ready."
& .\.grader-system-venv\Scripts\python.exe build_runtime_image.py
Write-Host "[2/2] Student runtime Docker image ready."
Write-Host "Set OPENAI_API_KEY in this shell before automatic AI plan resolution."
