# Shortcuts. Each target is one command you could also type yourself.
.PHONY: install up down test fast smoke ui api db security a11y unit load evidence report ai-eval flake-hunt

install:            ## Python deps + browser
	pip install -r requirements.txt
	python -m playwright install chromium

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
