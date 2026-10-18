# Test plan

Follows the Software Testing Life Cycle (STLC). One page on purpose.

## 1. Requirement analysis
System under test: **Gitea 1.22.6**, an open-source Git service, with PostgreSQL 16. Chosen because it has
a real web UI, a documented REST API (`/api/swagger`) and a SQL database, so every testing layer can be
exercised against one product.

In scope: sign-in/sign-out, registration, repositories (create, privacy, naming rules), issues (create,
comment, close/reopen, filter, paginate), labels, API authentication and token scopes, data integrity.
Out of scope: Git over SSH/HTTP, pull requests, CI runners, organisations, mail.

## 2. Test planning
| Level | Tool | Why |
|---|---|---|
| Manual | `test-cases/manual_test_cases.csv` | Designed first; every case traces to an automated test |
| UI | Playwright (Python), Page Objects | Real browser, auto-waiting, stable role-based locators |
| API | pytest + requests | Fast, precise checks of status codes, messages and boundaries |
| Database | psycopg + SQL | Proves the UI/API wrote the right data and counters stay consistent |
| Performance | Locust | Python, scriptable user mix, pass/fail thresholds |
| AI assist | Claude API | Generates candidate cases from a story; evaluated against the manual suite |

Entry criteria: app starts with `bash scripts/bootstrap.sh` and `/api/v1/version` answers.
Exit criteria: all smoke tests pass, no unexpected failures, every known bug has a report and a pinned test,
load SLOs met.

## 3. Test case design
Techniques: equivalence partitioning, boundary value analysis (at, below and above every limit: 8-char
passwords, 40-char usernames, 100-char repo names, 255-char titles), negative testing of every validation
rule, error guessing (whitespace, Unicode, HTML, SQL metacharacters), and security basics (authentication,
authorisation, least-privilege tokens, not revealing private data).

## 4. Environment setup
`docker-compose.yml` pins image versions. Data is created per test through the API with unique names and
removed afterwards, so tests are independent and can run in any order.

## 5. Execution
Locally with `make test`; in CI on every push: unit, then smoke, then the full suite, then load.

## 6. Defect reporting and closure
Defects go into `bug-reports/` with severity, priority, steps, expected vs actual and evidence that can be
regenerated (`scripts/capture_evidence.py`). Each defect has a strict-xfail test, so the suite notices
the day it is fixed. Results are summarised in the Allure report.
