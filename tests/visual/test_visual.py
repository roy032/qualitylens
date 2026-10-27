"""Visual regression of the main screens. Manual cases: TC-VIS-*.

Each screen is captured and compared with its approved baseline for the running Gitea version
(tests/visual/baseline/<version>/). Text that changes on every run (timestamps, page render times)
is masked. On a mismatch the actual image, the baseline and a diff with the changed pixels in
magenta are attached to the Allure report.

Run with `make visual`; approve intended changes with `make visual-update` and review the new
PNGs in the pull request like any other diff.
"""
from pathlib import Path

import allure
import pytest

from pages.login_page import LoginPage
from qualitylens import visual
from suite.config import settings

pytestmark = [pytest.mark.visual, pytest.mark.ui, allure.feature("Visual regression")]
OWNER = settings.admin_user

FAILURES = Path("test-results/visual")   # uploaded by CI when a screen changed

# Content that legitimately differs between runs.
DYNAMIC = ["relative-time", ".time-since", "footer .left-links", "#navbar .notification_count"]


@pytest.fixture
def signed_in(browser, browser_context_args, admin_storage_state):
    context = browser.new_context(**browser_context_args, storage_state=admin_storage_state)
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def fixed_repo(api, request):
    """A repository whose name is stable across runs (so it can appear in a screenshot) and unique per test."""
    name = "visual-" + request.node.callspec.params["screen"]
    api.delete_repo(OWNER, name)
    yield name
    api.delete_repo(OWNER, name)


def check_screen(page, name: str, version: str, update: bool):
    # Not "networkidle": signed-in pages keep an event stream open to the server.
    page.wait_for_load_state("load")
    page.evaluate("document.fonts.ready")
    actual = page.screenshot(full_page=True, animations="disabled", caret="hide",
                             mask=[page.locator(sel) for sel in DYNAMIC], mask_color="#808080")
    baseline = visual.baseline_path(version, name)
    if update or not baseline.exists():
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(actual)
        if not update:
            pytest.skip(f"no baseline for Gitea {version}: recorded {baseline.name}, review and commit it")
        return
    result = visual.compare(actual, baseline)
    allure.attach(actual, name=f"{name}: actual", attachment_type=allure.attachment_type.PNG)
    if not result.passed():
        allure.attach(baseline.read_bytes(), name=f"{name}: baseline", attachment_type=allure.attachment_type.PNG)
        FAILURES.mkdir(parents=True, exist_ok=True)
        (FAILURES / f"{name}-actual.png").write_bytes(actual)
        if result.diff_image:
            allure.attach(result.diff_image, name=f"{name}: diff", attachment_type=allure.attachment_type.PNG)
            (FAILURES / f"{name}-diff.png").write_bytes(result.diff_image)
    assert result.passed(), f"{name} looks different from the baseline: {result.describe()}"


@allure.title("Anonymous screen looks unchanged: {screen}")
@pytest.mark.parametrize("screen, path", [
    ("login", "/user/login"),
    ("register", "/user/sign_up"),
    ("not-found", "/no-such-user-qualitylens"),
])
def test_anonymous_screen(page, gitea_version, update_snapshots, screen, path):
    page.goto(settings.base_url + path)
    check_screen(page, screen, gitea_version, update_snapshots)


@allure.title("Failed sign-in error looks unchanged")
def test_login_error(page, gitea_version, update_snapshots):
    LoginPage(page).open().login(settings.admin_user, "wrong-password")
    LoginPage(page).flash_error.wait_for()
    check_screen(page, "login-error", gitea_version, update_snapshots)


@allure.title("New repository form looks unchanged")
def test_new_repository_form(signed_in, gitea_version, update_snapshots):
    signed_in.goto(settings.base_url + "/repo/create")
    # Gitea remembers whether the last repository was private; pin it so the screen is stable.
    signed_in.locator("input[name=private]").set_checked(False)
    check_screen(signed_in, "new-repository", gitea_version, update_snapshots)


@allure.title("Signed-in screen looks unchanged: {screen}")
@pytest.mark.parametrize("screen", ["empty-repository", "issue-list", "issue"])
def test_repository_screen(signed_in, api, fixed_repo, gitea_version, update_snapshots, screen):
    if screen == "empty-repository":
        api._ok(api.create_repo(fixed_repo, description="Visual baseline: empty repository"))
        path = f"/{OWNER}/{fixed_repo}"
    else:
        api._ok(api.create_repo(fixed_repo, auto_init=True, description="Visual baseline fixture"))
        titles = ["Login button misaligned on mobile", "Crash when label name has emoji",
                  "Add dark mode to settings page"]
        for title in titles:
            api._ok(api.create_issue(OWNER, fixed_repo, title, body="Steps:\n1. Open the page\n2. Look closely"))
        path = f"/{OWNER}/{fixed_repo}/issues" + ("/1" if screen == "issue" else "")
    signed_in.goto(settings.base_url + path)
    check_screen(signed_in, screen, gitea_version, update_snapshots)


@allure.title("The comparison catches a one-button colour change")
def test_comparison_detects_a_small_change(page, gitea_version, update_snapshots):
    """Guards the guard: a visual check that never fails is worse than none."""
    baseline = visual.baseline_path(gitea_version, "login")
    if update_snapshots or not baseline.exists():
        pytest.skip("needs the login baseline")
    page.goto(settings.base_url + "/user/login")
    page.add_style_tag(content=".ui.primary.button { background: #d9534f !important; }")
    page.wait_for_load_state("load")
    actual = page.screenshot(full_page=True, animations="disabled", caret="hide",
                             mask=[page.locator(sel) for sel in DYNAMIC], mask_color="#808080")
    result = visual.compare(actual, baseline)
    if result.diff_image:
        allure.attach(result.diff_image, name="diff of the injected change", attachment_type=allure.attachment_type.PNG)
    assert not result.passed(), "a red Sign In button was not detected"
