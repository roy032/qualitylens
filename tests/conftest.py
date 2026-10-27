"""Shared fixtures.

Data is created through the API (fast, reliable) and torn down after each test,
so UI tests spend their time on the behaviour under test, not on setup.
"""
from __future__ import annotations

import os

import allure
import pytest
from hypothesis import settings as hypothesis_settings

from pages.login_page import LoginPage
from suite.api_client import GiteaApi
from suite.config import settings
from suite.data import new_user_payload, unique
from suite.db import Database

# The QualityLens engine plugin (quarantine, app reachability check from qualitylens.toml). Installing the
# package loads it too, under the same name, so this line also works from a plain checkout.
pytest_plugins = ["qualitylens.pytest_plugin", "pytester"]  # pytester: tests of the plugin itself

# Property-based tests (tests/api/test_properties.py). "ci": same examples on every run, so a red build
# is reproducible and never a coin toss; "deep": random seeds and ten times the examples (make fuzz).
hypothesis_settings.register_profile("ci", max_examples=40, derandomize=True, deadline=None, print_blob=True)
hypothesis_settings.register_profile("deep", max_examples=400, deadline=None, print_blob=True)
hypothesis_settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "ci"))


def pytest_addoption(parser):
    parser.addoption("--update-snapshots", action="store_true",
                     help="visual tests: save the current screenshots as the new baselines")


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
