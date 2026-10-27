#!/usr/bin/env bash
# One command from a fresh clone to a full, summarised test run:
#   bash scripts/run.sh            # install, start Gitea, smoke, full suite, summary
#   bash scripts/run.sh --down     # same, then stop Gitea and delete its data
# Needs Docker and Python 3.12+. Safe to re-run: installed pieces are skipped.
set -uo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
PY=python3; command -v "$PY" >/dev/null || PY=python

step "1/5 Python environment"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
if ! cmp -s requirements.txt .venv/.installed 2>/dev/null; then
  pip install -q -r requirements.txt && python -m playwright install chromium && cp requirements.txt .venv/.installed
else
  echo "dependencies already installed"
fi

step "2/5 Start Gitea ${GITEA_VERSION:-1.22.6} + PostgreSQL"
bash scripts/bootstrap.sh || { echo "Could not start the app. Is Docker running?"; exit 3; }

rm -rf results allure-results
step "3/5 Smoke tests"
pytest -m smoke -n auto -q --alluredir=allure-results --junitxml=results/smoke.xml || {
  echo "Smoke tests failed, so the full run was skipped."; python scripts/ci_summary.py results/*.xml; exit 1; }

step "4/5 Full suite (parallel), then whole-database integrity rules"
pytest -m "not smoke and not serial and not visual and not quarantined" -n auto -q --alluredir=allure-results --junitxml=results/regression.xml
suite=$?
pytest -m serial -q --alluredir=allure-results --junitxml=results/integrity.xml
integrity=$?

step "5/5 Summary"
python scripts/ci_summary.py results/*.xml | tee results/summary.md
echo
echo "Summary: results/summary.md   Allure: make report (or npx allure-commandline serve allure-results)"
echo "Gitea:   http://localhost:3000 (qa_admin / QaAdmin#2026)"
[ "${1:-}" = "--down" ] && docker compose down -v
[ $suite -eq 0 ] && [ $integrity -eq 0 ]
