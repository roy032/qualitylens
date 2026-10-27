"""Self-service account registration. Manual cases: TC-REG-*."""
import allure
import pytest
from playwright.sync_api import expect

from pages.register_page import RegisterPage
from suite.config import settings
from suite.data import unique

pytestmark = [pytest.mark.ui, allure.feature("Registration")]


@pytest.fixture
def new_username(api):
    name = unique("reg").replace("-", "_")
    yield name
    api.delete_user(name)  # clean up whether or not the test created it


@pytest.mark.smoke
@allure.title("A new user can register and is signed in straight away")
def test_register_success(page, new_username, db):
    reg = RegisterPage(page).open().register(new_username, f"{new_username}@example.com", "Passw0rd!QA")
    expect(reg.flash_success).to_contain_text("Account was successfully created")
    reg.expect_logged_in()
    # Cross-check the database: the row exists and the password is not stored in plain text.
    row = db.one('SELECT name, email, passwd, is_admin FROM "user" WHERE lower_name = %s', (new_username.lower(),))
    assert row and row["email"] == f"{new_username}@example.com"
    assert row["passwd"] != "Passw0rd!QA" and row["is_admin"] is False


@pytest.mark.parametrize("password, retype, message", [
    pytest.param("short1!", "short1!", "Password length cannot be less than 8 characters.", id="7-chars"),
    pytest.param("Passw0rd!QA", "Passw0rd!QB", "The passwords do not match.", id="mismatch"),
])
@allure.title("Invalid passwords are rejected with a clear message")
def test_register_rejects_bad_password(page, new_username, password, retype, message):
    reg = RegisterPage(page).open().register(new_username, f"{new_username}@example.com", password, retype)
    expect(reg.flash_error).to_have_text(message)
    expect(page).to_have_url(f"{settings.base_url}/user/sign_up")


@allure.title("Password of exactly 8 characters (minimum boundary) is accepted")
def test_register_min_password_boundary(page, new_username):
    reg = RegisterPage(page).open().register(new_username, f"{new_username}@example.com", "Abcd123!")
    reg.expect_logged_in()


@allure.title("Username that already exists is rejected")
def test_register_duplicate_username(page, temp_user):
    reg = RegisterPage(page).open().register(temp_user["username"], "other-" + temp_user["email"], "Passw0rd!QA")
    expect(reg.flash_error).to_have_text("The username is already taken.")


@allure.title("Email that already exists is rejected, regardless of letter case")
def test_register_duplicate_email_case_insensitive(page, temp_user, new_username):
    reg = RegisterPage(page).open().register(new_username, temp_user["email"].upper(), "Passw0rd!QA")
    expect(reg.flash_error).to_have_text("The email address is already used.")


@allure.title("Malformed email is blocked by the browser")
def test_register_invalid_email(page, new_username):
    reg = RegisterPage(page).open().register(new_username, "not-an-email", "Passw0rd!QA")
    assert reg.email.evaluate("el => el.validity.typeMismatch") is True
    expect(page).to_have_url(f"{settings.base_url}/user/sign_up")
