"""Accessibility (WCAG 2.1 A/AA) of the main screens, checked with axe-core. Manual cases: TC-A11Y-*.

Each page is scanned and compared with tests/a11y/baseline.json. A rule that is not in the
baseline fails the test (a regression); baseline rules that still fire are attached to the
report as known issues; a baseline rule that stops firing is reported so the baseline can be
tightened. The full axe output is attached to Allure for every page.
"""
import json
import warnings

import allure
import pytest
from playwright.sync_api import expect

from pages.login_page import LoginPage
from qualitylens import a11y
from suite.config import settings

pytestmark = [pytest.mark.a11y, pytest.mark.ui, allure.feature("Accessibility")]
OWNER = settings.admin_user
BASELINE = a11y.load_baseline()

ANONYMOUS_PAGES = {
    "login": "/user/login",
    "register": "/user/sign_up",
    "explore": "/explore/repos",
}
SIGNED_IN_PAGES = {
    "dashboard": "/",
    "new-repository": "/repo/create",
    "repository-home": "/{owner}/{repo}",
    "issue-list": "/{owner}/{repo}/issues",
    "new-issue": "/{owner}/{repo}/issues/new",
    "issue": "/{owner}/{repo}/issues/{number}",
}


def check_page(page, name: str):
    found = a11y.scan(page)
    allure.attach("\n".join(v.describe() for v in found) or "no violations", name=f"axe: {name}",
                  attachment_type=allure.attachment_type.TEXT)
    allure.attach(json.dumps([v.__dict__ for v in found], indent=2), name=f"axe json: {name}",
                  attachment_type=allure.attachment_type.JSON)
    fixed = a11y.fixed_rules(found, BASELINE[name])
    if fixed:
        warnings.warn(f"{name}: baseline rules no longer fire, remove them from baseline.json: {fixed}", stacklevel=2)
    regressions = a11y.new_violations(found, BASELINE[name])
    assert regressions == [], "New accessibility violations:\n" + "\n".join(v.describe() for v in regressions)


@pytest.mark.parametrize("name", ANONYMOUS_PAGES)
def test_anonymous_page_has_no_new_violations(page, name):
    page.goto(settings.base_url + ANONYMOUS_PAGES[name])
    check_page(page, name)


@pytest.mark.parametrize("name", SIGNED_IN_PAGES)
def test_signed_in_page_has_no_new_violations(admin_page, repo, issue, name):
    path = SIGNED_IN_PAGES[name].format(owner=OWNER, repo=repo["name"], number=issue["number"])
    admin_page.goto(settings.base_url + path)
    check_page(admin_page, name)


def test_baseline_covers_every_scanned_page():
    assert sorted(BASELINE) == sorted({**ANONYMOUS_PAGES, **SIGNED_IN_PAGES})


@pytest.mark.smoke
@allure.title("Sign in works with the keyboard alone")
def test_keyboard_only_login(page):
    """WCAG 2.1.1: everything must be operable without a mouse."""
    login = LoginPage(page).open()
    login.username.focus()
    page.keyboard.type(settings.admin_user)
    page.keyboard.press("Tab")
    expect(login.password).to_be_focused()
    page.keyboard.type(settings.admin_password)
    page.keyboard.press("Enter")
    login.expect_logged_in()


@pytest.mark.parametrize("path", ["/user/login", "/user/sign_up"])
def test_form_fields_have_visible_labels(page, path):
    """WCAG 3.3.2: every text input on the sign-in and sign-up forms has a <label> tied to it."""
    page.goto(settings.base_url + path)
    unlabeled = page.locator("form.ui.form input:visible:not([type=hidden]):not([type=checkbox])").evaluate_all(
        "els => els.filter(e => !(e.labels && e.labels.length)).map(e => e.name || e.id)")
    assert unlabeled == []
