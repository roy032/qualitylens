# Shortcuts. Each target is one command you could also type yourself.
.PHONY: install install-dev run up down doctor test fast smoke ui api db security a11y property fuzz cross-browser unit impacted coverage mutation load evidence report ai-eval flake-hunt visual visual-update lint audit trends docker

install:            ## Python deps + browser + the qualitylens command
	pip install -r requirements.txt
	pip install --no-deps -e .
	python -m playwright install chromium

install-dev: install ## + lint/type/audit tools and the pre-commit hooks
	pip install -r requirements-dev.txt
	pre-commit install

doctor:             ## can this machine run the suite? says how to fix what is missing
	python -m qualitylens doctor

run:                ## one command: install, start Gitea, smoke, full suite, summary (Windows: scripts\run.ps1)
	bash scripts/run.sh

up:                 ## start Gitea + Postgres and create the admin user
	bash scripts/bootstrap.sh

down:               ## stop everything and delete all data
	docker compose down -v

test:               ## full suite with Allure results
	pytest --alluredir=allure-results

fast:               ## same suite on every CPU core, integrity rules last (how CI runs it)
	pytest -m "not unit and not serial and not quarantined" -n auto --alluredir=allure-results
	pytest -m "serial and not quarantined" --alluredir=allure-results

smoke: ; pytest -m smoke
ui:    ; pytest -m ui
api:   ; pytest -m api
db:    ; pytest -m db
security: ; pytest -m security
a11y:  ; pytest -m a11y
unit:  ; pytest -m unit

impacted:           ## only the layers your branch can affect (vs origin/main), see qualitylens/impact.py
	python -m qualitylens run impacted

lint:               ## ruff + mypy + quarantine check (what the CI lint job runs)
	ruff check .
	mypy
	python -m qualitylens quarantine check

audit:              ## known vulnerabilities in the pinned dependencies
	pip-audit -r requirements.txt --strict

trends:             ## record results/*.xml in the test history, report flaky tests, write the dashboard
	python -m qualitylens history add results/*.xml
	python -m qualitylens flaky
	python -m qualitylens dashboard --out test-history/trends.html

docker:             ## build the suite image (docker run --rm --network host qualitylens doctor)
	docker build -t qualitylens .
property: ; pytest -m property -n auto

fuzz:               ## property-based API tests with random seeds and 10x the examples (CI uses a fixed seed)
	HYPOTHESIS_PROFILE=deep pytest -m property -n auto

cross-browser:      ## UI suite on Firefox and WebKit (needs: python -m playwright install firefox webkit)
	pytest -m "ui and not visual" --browser firefox --browser webkit -n auto

coverage:           ## unit tests with branch coverage of the framework (fails under 90 %, see .coveragerc)
	pytest tests/unit -m unit --cov --cov-report=term-missing --cov-report=html

mutation:           ## mutate the framework's logic and check the unit tests notice (fails under 90 %)
	pip install -q mutmut==3.8.0
	rm -rf mutants; mutmut run --max-children 4; mutmut export-cicd-stats
	python scripts/mutation_score.py mutants/mutmut-cicd-stats.json --min 90

load:               ## 60 s load test with pass/fail thresholds
	mkdir -p load/results
	locust -f load/locustfile.py --headless -u 20 -r 5 -t 60s --host http://localhost:3000 \
	       --csv load/results/run --html load/results/report.html --only-summary
	python scripts/load_trend.py load/results/run_stats.csv --history load/history/history.json

evidence:           ## re-run every bug reproduction and refresh bug-reports/evidence
	python scripts/capture_evidence.py

report:             ## open the Allure report (needs Java)
	npx --yes allure-commandline@2.30.0 serve allure-results

flake-hunt:         ## run the suite 3 times and list tests whose result changed
	rm -rf runs; for i in 1 2 3; do pytest -m "not unit and not serial" -n auto -q --junitxml=runs/run-$$i.xml; done; \
	python scripts/ci_summary.py --runs runs/run-*.xml

ai-eval:            ## generate (needs ANTHROPIC_API_KEY) and evaluate AI test cases
	python -m ai.generate ai/stories/create_issue.md
	python -m ai.evaluate ai/output/create_issue.ai.json --feature Issues

# Screenshots only match when fonts and renderer are identical, so the visual suite runs inside
# the pinned Playwright image on every machine (and in CI).
PLAYWRIGHT_IMAGE = mcr.microsoft.com/playwright/python:v1.56.0-noble
VISUAL_RUN = docker run --rm --network host --user "$$(id -u):$$(id -g)" -e HOME=/tmp -e QL_VISUAL=1 \
	-e PYTHONDONTWRITEBYTECODE=1 $(VISUAL_DOCKER_ARGS) -v "$(CURDIR)":/work -w /work $(PLAYWRIGHT_IMAGE) \
	bash -c 'pip install -q --user --no-warn-script-location -r requirements.txt && python -m pytest -m visual -p no:cacheprovider $(1)'

visual:             ## screenshot comparison against tests/visual/baseline/<gitea version>/
	$(call VISUAL_RUN,--alluredir=allure-results)

visual-update:      ## accept the current look as the new baseline (review the PNG diff before committing)
	$(call VISUAL_RUN,--update-snapshots)
