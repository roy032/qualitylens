"""`qualitylens init`: a ready-to-run QualityLens suite for any web app or HTTP API.

    qualitylens init my-shop-qa --url http://localhost:8000 --health /health --api-prefix /api

writes a project that passes on a healthy app out of the box and is meant to be extended:

    qualitylens.toml          target URL, health check, layers, profiles (see qualitylens/project.py)
    pytest.ini                markers: smoke, api, ui
    requirements-qa.txt       the QualityLens engine with its browser extras
    quarantine.toml           flaky-test quarantine, empty
    tests/conftest.py         a `site` client for paths outside the API prefix
    tests/api/test_basics.py  health check is up and fast, unknown paths give 404
    tests/ui/test_pages.py    home page renders, no console errors, no broken same-site links,
                              no critical accessibility violations (axe-core, WCAG 2.1 AA)
    .github/workflows/qualitylens.yml   smoke, full run, history, flaky report, trends dashboard
    QUALITYLENS.md            how to run and extend it

Existing files are kept unless `force` is set, so it is safe to run inside an existing repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qualitylens import __version__


@dataclass(frozen=True)
class Options:
    name: str
    base_url: str
    health_path: str = "/"
    api_prefix: str = ""


ACTIONS = {  # same SHA-pinned versions as QualityLens' own CI
    "checkout": "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09  # v5.1.0",
    "setup-python": "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1  # v6.3.0",
    "cache-restore": "actions/cache/restore@0057852bfaa89a56745cba8c7296529d2fc39830  # v4.3.0",
    "cache-save": "actions/cache/save@0057852bfaa89a56745cba8c7296529d2fc39830  # v4.3.0",
    "upload": "actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4  # v5.0.0",
}


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def files(o: Options) -> dict[str, str]:
    base_url = o.base_url.rstrip("/")
    health = o.health_path if o.health_path.startswith("/") else f"/{o.health_path}"
    prefix = o.api_prefix.rstrip("/")
    return {
        "qualitylens.toml": f'''# QualityLens project file. Reference: https://github.com/roy032/qualitylens/blob/main/docs/toolkit.md

[project]
name = {_toml_string(o.name)}
layers = ["smoke", "api", "ui"]          # pytest markers; tests/<layer>/ belongs to its marker

[target]
base_url = {_toml_string(base_url)}      # QL_BASE_URL overrides it (CI, staging)
health_path = {_toml_string(health)}     # must answer 2xx before tests that need the app run
requires_app = ["smoke", "api", "ui"]
start_hint = {_toml_string(f"start {o.name}, or point QL_BASE_URL at a running copy")}
api_prefix = {_toml_string(prefix)}      # the `api` fixture's paths are relative to this

# Credentials for the `api` fixture and `qualitylens doctor`. Never write a real password here:
# put it in the environment (or a CI secret) under the names below.
# [target.login]
# path = "{prefix}/me"
# user_env = "QL_USER"
# password_env = "QL_PASSWORD"

[doctor]
packages = ["pytest", "requests", "playwright", "axe_playwright_python"]
browser = true

[profiles]
smoke = [["-m", "smoke and not quarantined"]]
full = [["-m", "not quarantined"]]
''',
        "pytest.ini": '''[pytest]
testpaths = tests
addopts = -ra --strict-markers
markers =
    smoke: fast, critical-path checks run first
    api: HTTP API tests
    ui: browser tests (Playwright)
''',
        "requirements-qa.txt": f'''# The QualityLens engine with browser and accessibility support.
# Pin to a release tag once one exists (https://github.com/roy032/qualitylens/releases), e.g. @v{__version__}.
qualitylens[ui] @ git+https://github.com/roy032/qualitylens@main
''',
        "quarantine.toml": '''# Flaky tests that must not block CI. Each entry needs an owner, a reason and an expiry at most 30 days
# ahead; `qualitylens quarantine check` fails once it has expired.
#
# [[test]]
# id = "tests/ui/test_pages.py::test_home_page_renders"
# reason = "..."
# owner = "your-github-name"
# expires = 2030-01-31
''',
        "tests/__init__.py": "",
        "tests/api/__init__.py": "",
        "tests/ui/__init__.py": "",
        "tests/conftest.py": '''"""Fixtures for this suite. QualityLens' pytest plugin already provides:

- `ql_project`: the parsed qualitylens.toml (base_url, api_url, login, ...)
- `api`: an HTTP client on the app's API ([target] api_prefix), logged in when [target.login] is set
- `page`, `browser`: Playwright, with relative URLs (`page.goto("/")`) resolved against base_url

Add your own here: data factories that create what a test needs through the API and delete it afterwards
keep tests independent and fast.
"""
import pytest

from qualitylens.http import ApiClient


@pytest.fixture(scope="session")
def site(ql_project) -> ApiClient:
    """HTTP client on the app's root, for pages and endpoints outside the API prefix."""
    return ApiClient(ql_project.base_url)
''',
        "tests/api/test_basics.py": '''"""Baseline API checks that hold for any healthy HTTP service. Add one file per feature next to it."""
import uuid

import pytest

pytestmark = pytest.mark.api

MAX_HEALTH_SECONDS = 1.0


@pytest.mark.smoke
def test_health_check_is_up(site, ql_project):
    response = site.get(ql_project.health_path)
    assert response.status_code < 300, f"{ql_project.health_url} answered {response.status_code}"


def test_health_check_is_fast(site, ql_project):
    response = site.get(ql_project.health_path)
    assert response.elapsed.total_seconds() < MAX_HEALTH_SECONDS


def test_unknown_path_is_404(site):
    response = site.get(f"/qualitylens-missing-{uuid.uuid4().hex}")
    assert response.status_code == 404
''',
        "tests/ui/test_pages.py": '''"""Baseline browser checks for the home page. Copy them for each important page, then add the flows
(sign-in, search, checkout, ...) as Page Objects plus tests."""
from urllib.parse import urljoin, urlparse

import pytest
from playwright.sync_api import expect

from qualitylens import a11y

pytestmark = pytest.mark.ui
MAX_LINKS = 25


@pytest.mark.smoke
def test_home_page_renders(page):
    response = page.goto("/")
    assert response is not None and response.status < 400
    expect(page).not_to_have_title("")


def test_home_page_has_no_console_errors(page):
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto("/")
    page.wait_for_load_state("networkidle")
    assert errors == []


def test_no_broken_links_on_home_page(page, site, ql_project):
    page.goto("/")
    own_host = urlparse(ql_project.base_url).netloc
    hrefs = page.eval_on_selector_all("a[href]", "links => links.map(a => a.getAttribute('href'))")
    targets = sorted({urljoin(page.url, h).split("#")[0] for h in hrefs
                      if urlparse(urljoin(page.url, h)).netloc == own_host})[:MAX_LINKS]
    broken = [(url, status) for url in targets if (status := site.session.get(url, timeout=10).status_code) >= 400]
    assert broken == []


def test_home_page_has_no_critical_accessibility_violations(page):
    page.goto("/")
    critical = [v for v in a11y.scan(page) if v.impact == "critical"]
    assert critical == [], "\\n".join(v.describe() for v in critical)
''',
        ".github/workflows/qualitylens.yml": f'''name: QualityLens

# Runs the suite against the app at the repository variable QL_BASE_URL (Settings > Secrets and
# variables > Actions > Variables), keeps a per-test history and publishes the trends dashboard.
on:
  push:
  pull_request:
  schedule:
    - cron: "0 6 * * *"   # daily, so flaky tests show up even without pushes
  workflow_dispatch:

permissions:
  contents: read

jobs:
  qa:
    runs-on: ubuntu-latest
    env:
      QL_BASE_URL: ${{{{ vars.QL_BASE_URL }}}}
      QL_USER: ${{{{ secrets.QL_USER }}}}
      QL_PASSWORD: ${{{{ secrets.QL_PASSWORD }}}}
    steps:
      - uses: {ACTIONS["checkout"]}
      - uses: {ACTIONS["setup-python"]}
        with: {{ python-version: "3.12" }}
      # QualityLens is installed from GitHub; for a private copy add a QUALITYLENS_TOKEN secret (read access).
      - name: Install QualityLens
        env:
          QUALITYLENS_TOKEN: ${{{{ secrets.QUALITYLENS_TOKEN }}}}
        run: |
          if [ -n "$QUALITYLENS_TOKEN" ]; then
            git config --global url."https://x-access-token:$QUALITYLENS_TOKEN@github.com/".insteadOf "https://github.com/"
          fi
          pip install -r requirements-qa.txt
          python -m playwright install --with-deps chromium
      - run: qualitylens doctor
      - run: qualitylens quarantine check
      - name: Smoke tests
        run: qualitylens run smoke --junit-dir results
      - name: Full suite
        run: qualitylens run full --junit-dir results -- --screenshot=only-on-failure --output=test-results
      - name: Quarantined tests (non-blocking)
        if: success() || failure()
        continue-on-error: true
        run: qualitylens run quarantined --junit-dir results
      - name: Run summary
        if: always()
        run: qualitylens summary results/*.xml >> "$GITHUB_STEP_SUMMARY"
      - uses: {ACTIONS["cache-restore"]}
        if: always()
        with:
          path: test-history
          key: test-history-${{{{ github.ref_name }}}}-${{{{ github.run_id }}}}
          restore-keys: |
            test-history-${{{{ github.ref_name }}}}-
            test-history-main-
      - name: History, flaky tests, trends dashboard
        if: always() && hashFiles('results/*.xml') != ''
        shell: bash
        run: |
          qualitylens history add results/*.xml --label "${{GITHUB_SHA::7}} (run ${{{{ github.run_number }}}})"
          qualitylens flaky | tee -a "$GITHUB_STEP_SUMMARY"
          qualitylens dashboard
      - uses: {ACTIONS["cache-save"]}
        if: always() && hashFiles('test-history/history.json') != ''
        with:
          path: test-history
          key: test-history-${{{{ github.ref_name }}}}-${{{{ github.run_id }}}}
      - uses: {ACTIONS["upload"]}
        if: always()
        with:
          name: qualitylens
          path: |
            results
            test-history
            test-results
''',
        "QUALITYLENS.md": f'''# {o.name}: QualityLens suite

Tests for {base_url}, run by [QualityLens](https://github.com/roy032/qualitylens).

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-qa.txt && python -m playwright install chromium
qualitylens doctor              # Python, packages, browser, is the app up?
qualitylens run smoke           # seconds
qualitylens run full --record   # everything, and add the results to test-history/
qualitylens dashboard           # test-history/trends.html
```

Point it somewhere else with `QL_BASE_URL=https://staging.example.com qualitylens run smoke`.
Anything after `--` goes to pytest: `qualitylens run ui -- --headed -x`.

## What is checked out of the box

| Test | Why |
|---|---|
| health check answers 2xx, in under a second | the app is up and not struggling |
| unknown paths give 404 | routing and error handling are not swallowing mistakes |
| home page renders with a title | the front end builds and serves |
| no console errors on the home page | JavaScript errors users never report |
| no broken same-site links on the home page | 404s from navigation |
| no critical accessibility violations (axe-core, WCAG 2.1 AA) | blockers for keyboard and screen-reader users |

## Extend it

- One file per feature under `tests/api/` or `tests/ui/`; mark it with its layer (`pytestmark = pytest.mark.api`).
- New layer (for example `security`): add the marker to `pytest.ini` and to `layers` in `qualitylens.toml`,
  and put the tests in `tests/security/`.
- Logged-in tests: uncomment `[target.login]` in `qualitylens.toml` and export `QL_USER` / `QL_PASSWORD`;
  the `api` fixture then sends those credentials.
- A test that fails at random: quarantine it in `quarantine.toml` (owner, reason, expiry) and fix it;
  `qualitylens flaky` lists candidates once there is history.
- `qualitylens run impacted` runs only the layers your branch can affect; tune it with `[[impact.rule]]`.

## CI

`.github/workflows/qualitylens.yml` runs smoke, the full suite and the quarantined tests against the
repository variable `QL_BASE_URL`, records the history, writes the flaky-test report into the job
summary and uploads the dashboard. Set `QL_BASE_URL` (variable) and, if needed, `QL_USER`, `QL_PASSWORD`
and `QUALITYLENS_TOKEN` (secrets) under Settings > Secrets and variables > Actions.
''',
    }


def write(target: Path, options: Options, force: bool = False) -> tuple[list[Path], list[Path]]:
    """Create the project under `target`; returns (written, kept because they existed)."""
    written, skipped = [], []
    for relative, content in files(options).items():
        path = target / relative
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written.append(path)
    return written, skipped
