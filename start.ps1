# Launch after creating .venv and installing requirements.txt.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    Write-Host 'First run: python -m venv .venv'
    Write-Host 'Then run: .venv\Scripts\python -m pip install -r requirements.txt'
    exit 1
}
& $taskPython -m streamlit run app.py
