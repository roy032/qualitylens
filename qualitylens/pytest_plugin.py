"""pytest plugin for any QualityLens project, loaded automatically once the package is installed.

- Tests listed in quarantine.toml get the `quarantined` marker. CI deselects them from the blocking run
  (`-m "... and not quarantined"`) and runs them in a separate step that may fail, so they keep
  producing history without turning the build red.
- Before tests marked with one of `[target] requires_app` run, the app's health URL must answer, or the
  session stops at once with the start hint instead of failing every test with a connection error.
- `--base-url` (Playwright's relative `page.goto("/")`) defaults to the project's base URL.
- Fixtures: `ql_project` (the parsed qualitylens.toml) and `api` (an ApiClient on the app's API, logged in
  when `[target.login]` is set). A conftest.py can override either.
"""
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import pytest
import requests

from qualitylens import project as project_config
from qualitylens import quarantine
from qualitylens.http import ApiClient

_KEY = pytest.StashKey[project_config.Project]()


def pytest_addoption(parser):
    parser.addoption("--quarantine-file", default=None,
                     help="flaky-test quarantine list (default: [quarantine] path in qualitylens.toml)")


def pytest_configure(config):
    config.addinivalue_line("markers", "quarantined: listed in quarantine.toml; runs, but must not block CI")
    project = project_config.load(start=Path(config.rootpath))
    config.stash[_KEY] = project
    if hasattr(config.option, "base_url") and not config.option.base_url:
        config.option.base_url = project.base_url


def _project(config) -> project_config.Project:
    return config.stash[_KEY]


@pytest.hookimpl(tryfirst=True)  # before -m deselects, so "not quarantined" sees the marker
def pytest_collection_modifyitems(config, items):
    option = config.getoption("--quarantine-file")
    entries = quarantine.load(Path(option) if option else _project(config).quarantine_path)
    if not entries:
        return
    ids = {e.test_id for e in entries}
    for e in entries:
        if e.expires < date.today():
            warnings.warn(f"quarantine for {e.test_id} expired on {e.expires}", stacklevel=1)
    for item in items:
        if quarantine.is_quarantined(item.nodeid, ids):
            item.add_marker(pytest.mark.quarantined)


@pytest.hookimpl(trylast=True)  # after -m has deselected, so offline runs never need the app
def pytest_collection_finish(session):
    project = _project(session.config)
    needs_app = set(project.requires_app)
    if not project.health_url or session.config.option.collectonly:
        return
    if not any(item.get_closest_marker(m) for item in session.items for m in needs_app):
        return
    try:
        requests.get(project.health_url, timeout=5).raise_for_status()
    except requests.RequestException as exc:
        pytest.exit(f"{project.name} is not reachable at {project.health_url} ({exc.__class__.__name__}). "
                    f"Start it with: {project.start_hint}", returncode=3)


@pytest.fixture(scope="session")
def ql_project(request) -> project_config.Project:
    return _project(request.config)


@pytest.fixture(scope="session")
def api(ql_project) -> ApiClient:
    login = ql_project.login
    auth = (login.user, login.password) if login and login.user else None
    return ApiClient(ql_project.api_url, auth=auth)
