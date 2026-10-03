param(
  [Parameter(Mandatory=$true)][string]$Project,
  [switch]$PrepareEnv,
  [switch]$PlanB,
  [switch]$DraftScore
)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Python = ".\.grader-system-venv\Scripts\python.exe"
if (!(Test-Path $Python)) { $Python = "py" }
$argsList = @("evaluate.py", "--project", $Project, "--runtime")
if ($PrepareEnv) { $argsList += "--prepare-env" }
if ($PlanB) { $argsList += "--plan-b" }
if ($DraftScore) { $argsList += "--score-draft" }
& $Python @argsList
