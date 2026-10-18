"""Login / logout through the browser. Manual cases: TC-LOGIN-*."""
import allure
import pytest
from playwright.sync_api import expect

from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage
from qualitylens.config import settings

pytestmark = [pytest.mark.ui, allure.feature("Authentication")]


@pytest.mark.smoke
@allure.title("Valid credentials log the user in and land on the dashboard")
def test_login_with_valid_credentials(page):
    login = LoginPage(page).open().login(settings.admin_user, settings.admin_password)
    login.expect_logged_in()
    expect(page).to_have_title(f"{settings.admin_user} - Dashboard - Gitea: Git with a cup of tea")


@allure.title("Login also accepts the email address in the username field")
def test_login_with_email(page, temp_user):
    LoginPage(page).open().login(temp_user["email"], temp_user["password"]).expect_logged_in()


@pytest.mark.parametrize("username, password", [
    pytest.param("qa_admin", "wrong-password", id="wrong-password"),
    pytest.param("no_such_user_xyz", "whatever123", id="unknown-user"),
    pytest.param("QA_ADMIN ", "wrong-password", id="trailing-space-wrong-password"),
])
@allure.title("Invalid credentials show one generic error and do not log in")
def test_login_rejects_invalid_credentials(page, username, password):
    login = LoginPage(page).open().login(username, password)
    # Same message for unknown user and wrong password: the page must not reveal which accounts exist.
    expect(login.flash_error).to_have_text("Username or password is incorrect.")
    expect(page).to_have_url(f"{settings.base_url}/user/login")


@allure.title("Empty username is blocked by the browser before submitting")
def test_login_requires_username(page):
    login = LoginPage(page).open()
    login.password.fill("anything")
    login.submit.click()
    assert login.username.evaluate("el => el.validity.valueMissing") is True
    expect(page).to_have_url(f"{settings.base_url}/user/login")


@allure.title("Password field masks input")
def test_password_is_masked(page):
    expect(LoginPage(page).open().password).to_have_attribute("type", "password")


@pytest.mark.smoke
@allure.title("Sign out ends the session")
def test_logout(page):
    LoginPage(page).open().login(settings.admin_user, settings.admin_password).expect_logged_in()
    DashboardPage(page).logout()
    DashboardPage(page).expect_logged_out()
    # A protected page now redirects back to the login form.
    page.goto(f"{settings.base_url}/repo/create")
    expect(page).to_have_url(f"{settings.base_url}/user/login")
