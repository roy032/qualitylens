# One command from a fresh clone to a full, summarised test run (Windows PowerShell + Docker Desktop):
#   powershell -ExecutionPolicy Bypass -File scripts\run.ps1          # install, start Gitea, smoke, full suite, summary
#   powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Down    # same, then stop Gitea and delete its data
#   powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Report  # same, then open the Allure report (needs Java)
# Safe to re-run: installed pieces are skipped.
param([switch]$Down, [switch]$Report)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
$admin = if ($env:QL_ADMIN_USER) { $env:QL_ADMIN_USER } else { "qa_admin" }
$password = if ($env:QL_ADMIN_PASSWORD) { $env:QL_ADMIN_PASSWORD } else { "QaAdmin#2026" }

Step "1/5 Python environment"
if (-not (Test-Path .venv)) { python -m venv .venv }
. .venv\Scripts\Activate.ps1
$marker = ".venv\.installed"
if (-not (Test-Path $marker) -or (Get-FileHash requirements.txt).Hash -ne (Get-Content $marker -Raw).Trim()) {
    pip install -q -r requirements.txt
    python -m playwright install chromium
    (Get-FileHash requirements.txt).Hash | Set-Content $marker
} else { Write-Host "dependencies already installed" }

Step "2/5 Start Gitea + PostgreSQL"
docker compose up -d --wait
if ($LASTEXITCODE -ne 0) { Write-Host "Could not start the app. Is Docker Desktop running?" -ForegroundColor Red; exit 3 }
$users = docker compose exec -T -u git gitea gitea admin user list
if (-not ($users | Select-String -Pattern "\s$admin\s" -Quiet)) {
    docker compose exec -T -u git gitea gitea admin user create --admin --username $admin `
        --password $password --email "$admin@example.com" --must-change-password=false
}

Remove-Item -Recurse -Force results, allure-results -ErrorAction SilentlyContinue
$ErrorActionPreference = "Continue"   # from here on, test failures are reported, not fatal

Step "3/5 Smoke tests"
pytest -m smoke -n auto -q --alluredir=allure-results --junitxml=results/smoke.xml
if ($LASTEXITCODE -ne 0) {
    Write-Host "Smoke tests failed, so the full run was skipped." -ForegroundColor Red
    python -m qualitylens summary (Get-ChildItem results\*.xml).FullName; exit 1
}

Step "4/5 Full suite (parallel), then whole-database integrity rules"
pytest -m "not smoke and not serial and not visual and not quarantined" -n auto -q --alluredir=allure-results --junitxml=results/regression.xml
$suite = $LASTEXITCODE
pytest -m serial -q --alluredir=allure-results --junitxml=results/integrity.xml
$integrity = $LASTEXITCODE

Step "5/5 Summary"
$env:PYTHONIOENCODING = "utf-8"
python -m qualitylens summary (Get-ChildItem results\*.xml).FullName | Tee-Object -FilePath results\summary.md
Write-Host "`nSummary: results\summary.md   Gitea: http://localhost:3000 ($admin / $password)"
if ($Report) { npx --yes allure-commandline@2.30.0 serve allure-results }
if ($Down) { docker compose down -v }
if ($suite -ne 0 -or $integrity -ne 0) { exit 1 }
