# Use QualityLens on your own app

QualityLens is two things in this repository: an **engine** (the `qualitylens` package: CLI, pytest
plugin, project config, test history, flaky-test quarantine, impact selection, reports) and a **suite**
that uses it to test Gitea (`suite/`, `pages/`, `tests/`). The engine knows nothing about Gitea; everything
app-specific is in `qualitylens.toml` and the suite. This page is about pointing the engine at your app.

## Five minutes to a running suite

```bash
python -m venv .venv && source .venv/bin/activate
pip install "qualitylens[ui] @ git+https://github.com/roy032/qualitylens@main"
python -m playwright install chromium

qualitylens init my-app-qa --url http://localhost:8000 --health /health --api-prefix /api
cd my-app-qa
qualitylens doctor        # Python, packages, browser, is the app up?
qualitylens run smoke     # seconds
qualitylens run full --record && qualitylens dashboard
```

The repository is private, so `pip install` needs GitHub access (an SSH key, or a token in the URL).
Inside an existing repository, run `qualitylens init . --url ...`: files that already exist are kept
(`--force` overwrites them).

`init` writes a suite that passes on any healthy web app and fails on the common ways one breaks:

| Test | Catches |
|---|---|
| health check answers 2xx, in under a second (smoke) | the app is down or struggling |
| unknown paths give 404 | routing that swallows mistakes |
| home page renders with a title (smoke) | a broken front-end build |
| no console errors on the home page | JavaScript errors users never report |
| no broken same-site links on the home page | 404s from navigation |
| no critical accessibility violations (axe-core, WCAG 2.1 AA) | blockers for keyboard and screen-reader users |

CI proves this on every push: the **toolkit** job scaffolds a suite for
[`examples/sample-app`](../examples/sample-app), runs it (all pass), seeds a broken link, a JavaScript
error and an image without alt text (each is caught, nothing else fails), then stops the app (the run
stops at once with the start hint). See [`scripts/toolkit_selftest.sh`](../scripts/toolkit_selftest.sh).

It also writes `.github/workflows/qualitylens.yml`: smoke, full and quarantined runs against the
repository variable `QL_BASE_URL`, per-test history in the Actions cache, the flaky-test report in the
job summary and the trends dashboard as an artifact.

## qualitylens.toml

Every section is optional; the defaults give a working runner for a plain pytest suite.

```toml
[project]
name = "My shop"
layers = ["smoke", "api", "ui"]      # pytest markers; tests/<layer>/ belongs to its marker

[target]
base_url = "http://localhost:8000"   # QL_BASE_URL overrides it (staging, CI)
health_path = "/health"              # must answer 2xx before tests that need the app run
requires_app = ["smoke", "api", "ui"]
start_hint = "docker compose up -d"  # printed when the app is not reachable
api_prefix = "/api"                  # the `api` fixture's paths are relative to this

[target.login]                       # credentials come from the environment, never from this file
path = "/api/me"                     # `doctor` checks the login works
user_env = "QL_USER"
password_env = "QL_PASSWORD"

[target.database]                    # optional; `doctor` checks it is reachable (needs qualitylens[db])
dsn_env = "QL_DB_DSN"

[doctor]
packages = ["pytest", "requests", "playwright"]
browser = true

[profiles]                           # `qualitylens run <name>`: one pytest call per list
smoke = [["-m", "smoke and not quarantined"]]
full = [["-m", "not quarantined"]]
nightly = [["-m", "api and not quarantined"], ["-m", "ui and not quarantined", "--browser", "firefox"]]

[impact]                             # `qualitylens run impacted`
fallback_profile = "full"            # when a change can affect everything

[[impact.rule]]                      # first match wins; unmatched files select everything
glob = "src/payments/*"
layers = ["api"]

[history]
path = "test-history/history.json"
keep = 50

[flaky]
min_runs = 10                        # runs before a test can be called flaky
threshold = 0.1                      # outcome flips in at least 10 % of consecutive runs

[quarantine]
path = "quarantine.toml"
```

`qualitylens run <layer>` works for any layer in `layers` without a profile. The Gitea suite's
[`qualitylens.toml`](../qualitylens.toml) is a complete real example, with login, database and 20
impact rules.

## What the pytest plugin gives every suite

Installing the package registers a pytest plugin (no conftest needed):

- **App health gate.** If a selected test carries a `requires_app` marker and the health URL does not
  answer, the session stops before the first test with exit code 3 and the start hint, instead of
  hundreds of connection errors. Offline selections (`-m unit`) never touch the network.
- **Quarantine.** Tests listed in `quarantine.toml` get the `quarantined` marker, so the blocking run
  deselects them and a separate non-blocking step keeps their history; expired entries warn.
- **Base URL.** Playwright's relative `page.goto("/")` resolves against `base_url`.
- **Fixtures.** `ql_project` (the parsed config) and `api` (a `qualitylens.http.ApiClient` on
  `base_url + api_prefix`, logged in when `[target.login]` is set). Override either in a conftest.

## Engine modules you can use from tests

| Module | Use |
|---|---|
| `qualitylens.http.ApiClient` | `api.get("/items")`, `ApiClient.ok(resp, 201)` for set-up calls that must succeed |
| `qualitylens.a11y.scan(page)` | axe-core violations of a Playwright page, with `describe()` for messages |
| `qualitylens.visual` | pixel comparison against approved baselines, diff images |
| `qualitylens.junit`, `history`, `dashboard` | results history and the trends page, behind `qualitylens history`/`dashboard` |

## Growing the suite

1. Add flows as Page Objects plus tests (`tests/ui/`), one file per feature.
2. Create test data through the API in fixtures and delete it afterwards; it is faster and steadier than
   clicking through the UI.
3. Add a layer (for example `security`): marker in `pytest.ini`, name in `layers`, tests in
   `tests/security/`.
4. Let history accumulate in CI; `qualitylens flaky` names tests to fix or quarantine.

The Gitea suite in this repository shows each of these at scale: 589 tests over UI, API, database,
security, accessibility, visual, property-based and load layers.
