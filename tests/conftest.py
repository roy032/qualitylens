"""Shared fixtures.

Data is created through the API (fast, reliable) and torn down after each test,
so UI tests spend their time on the behaviour under test, not on setup.
"""
from __future__ import annotations

import allure
import pytest
import requests

from pages.login_page import LoginPage
from qualitylens.api_client import GiteaApi
from qualitylens.config import settings
from qualitylens.data import new_user_payload, unique
from qualitylens.db import Database


def pytest_collection_modifyitems(session, config, items):
    """Fail fast with a clear message if the app is not running (skipped for offline unit tests)."""
    if not any(item.get_closest_marker(m) for item in items for m in ("ui", "api", "db", "security", "a11y")):
        return
    try:
        requests.get(f"{settings.api_url}/version", timeout=5).raise_for_status()
    except requests.RequestException as exc:
        pytest.exit(f"Gitea is not reachable at {settings.base_url} ({exc}). "
                    f"Start it with: bash scripts/bootstrap.sh", returncode=3)


# --- API / DB ------------------------------------------------------------
@pytest.fixture(scope="session")
def api() -> GiteaApi:
    return GiteaApi(auth=(settings.admin_user, settings.admin_password))


@pytest.fixture(scope="session")
def anon_api() -> GiteaApi:
    return GiteaApi()


@pytest.fixture(scope="session")
def db():
    database = Database()
    yield database
    database.close()


@pytest.fixture
def repo(api):
    """A fresh repository owned by the admin, deleted after the test."""
    name = unique("repo")
    data = api._ok(api.create_repo(name, auto_init=True, description="QualityLens fixture"))
    yield data
    api.delete_repo(settings.admin_user, name)


@pytest.fixture
def issue(api, repo):
    data = api._ok(api.create_issue(settings.admin_user, repo["name"], unique("issue"), body="Fixture issue"))
    return data


@pytest.fixture
def temp_user(api):
    """A regular (non-admin) user, deleted after the test."""
    payload = new_user_payload()
    api._ok(api.create_user(payload))
    yield payload
    api.delete_user(payload["username"])


# --- Browser ---------------------------------------------------------------
@pytest.fixture(scope="session")
def admin_storage_state(browser, tmp_path_factory):
    """Log in through the UI once per run and reuse the session cookie."""
    path = tmp_path_factory.mktemp("auth") / "admin.json"
    context = browser.new_context()
    page = context.new_page()
    LoginPage(page).open().login(settings.admin_user, settings.admin_password)
    LoginPage(page).expect_logged_in()
    context.storage_state(path=str(path))
    context.close()
    return str(path)


@pytest.fixture
def admin_page(browser, admin_storage_state):
    context = browser.new_context(storage_state=admin_storage_state)
    page = context.new_page()
    yield page
    context.close()


# --- Reporting -------------------------------------------------------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach a screenshot and the page URL to the Allure report when a UI test fails."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    for name in ("admin_page", "page"):
        page = item.funcargs.get(name)
        if page is not None and not page.is_closed():
            allure.attach(page.screenshot(full_page=True), name="screenshot",
                          attachment_type=allure.attachment_type.PNG)
            allure.attach(page.url, name="url", attachment_type=allure.attachment_type.TEXT)
            break
