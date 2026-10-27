"""Admin user management API: validation of username, email and password. Manual cases: TC-API-USER-*."""
import allure
import pytest

from suite.data import new_user_payload

pytestmark = [pytest.mark.api, allure.feature("API: Users")]


@pytest.fixture
def payload(api):
    data = new_user_payload()
    yield data
    api.delete_user(data["username"])


@pytest.mark.smoke
def test_create_user(api, payload):
    resp = api.create_user(payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["login"] == payload["username"]
    assert body["email"] == payload["email"]
    assert body["is_admin"] is False
    assert "password" not in body  # never echo secrets


def test_duplicate_username_rejected(api, temp_user, payload):
    payload["username"] = temp_user["username"]
    resp = api.create_user(payload)
    assert resp.status_code == 422
    assert "user already exists" in resp.json()["message"]


def test_duplicate_email_is_case_insensitive(api, temp_user, payload):
    payload["email"] = temp_user["email"].upper()
    resp = api.create_user(payload)
    assert resp.status_code == 422
    assert "e-mail already in use" in resp.json()["message"]


@pytest.mark.parametrize("username, status", [
    ("a" * 40, 201),   # max length boundary
    ("a" * 41, 422),   # max + 1
    ("api", 422),      # reserved name
    ("bad name", 422),  # space not allowed
], ids=["40-chars", "41-chars", "reserved", "space"])
def test_username_validation(api, payload, username, status):
    payload["username"] = username
    resp = api.create_user(payload)
    try:
        assert resp.status_code == status, resp.text
    finally:
        if resp.status_code == 201:
            api.delete_user(username)


@pytest.mark.parametrize("email", ["notanemail", "a@", "@example.com", ""])
def test_invalid_email_rejected(api, payload, email):
    payload["email"] = email
    assert api.create_user(payload).status_code == 422


def test_short_password_rejected(api, payload):
    payload["password"] = "Ab1!"
    assert api.create_user(payload).status_code == 400


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-004: short password reported as 'PasswordIsRequired'")
def test_short_password_error_message_is_accurate(api, payload):
    payload["password"] = "Ab1!"
    message = api.create_user(payload).json()["message"]
    assert message != "PasswordIsRequired"
    assert "8" in message or "length" in message.lower()
