# Shortcuts. Each target is one command you could also type yourself.
.PHONY: install run up down test fast smoke ui api db security a11y unit coverage mutation load evidence report ai-eval flake-hunt visual visual-update

install:            ## Python deps + browser
	pip install -r requirements.txt
	python -m playwright install chromium

run:                ## one command: install, start Gitea, smoke, full suite, summary (Windows: scripts\run.ps1)
	bash scripts/run.sh

up:                 ## start Gitea + Postgres and create the admin user
	bash scripts/bootstrap.sh

down:               ## stop everything and delete all data
	docker compose down -v

test:               ## full suite with Allure results
	pytest --alluredir=allure-results

fast:               ## same suite on every CPU core, integrity rules last (how CI runs it)
	pytest -m "not unit and not serial" -n auto --alluredir=allure-results
	pytest -m serial --alluredir=allure-results

smoke: ; pytest -m smoke
ui:    ; pytest -m ui
api:   ; pytest -m api
db:    ; pytest -m db
security: ; pytest -m security
a11y:  ; pytest -m a11y
unit:  ; pytest -m unit

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
