"""Authentication and authorisation on the REST API. Manual cases: TC-API-AUTH-*."""
import allure
import pytest

from suite.api_client import GiteaApi
from suite.config import settings
from suite.data import unique

pytestmark = [pytest.mark.api, allure.feature("API: Authentication")]


@pytest.mark.smoke
def test_basic_auth_returns_current_user(api):
    resp = api.me()
    assert resp.status_code == 200
    body = resp.json()
    assert body["login"] == settings.admin_user
    assert body["is_admin"] is True


@pytest.mark.parametrize("auth", [None, ("qa_admin", "wrong-password"), ("ghost_user", "x")],
                         ids=["no-credentials", "wrong-password", "unknown-user"])
def test_protected_endpoint_rejects_bad_credentials(auth):
    resp = GiteaApi(auth=auth).me()
    assert resp.status_code == 401


def test_invalid_token_rejected():
    assert GiteaApi(token="0" * 40).me().status_code == 401


def test_scoped_token_allows_read_but_blocks_write(api, repo):
    """Least privilege: a read-only token must not be able to create data."""
    token = api._ok(api.create_token(settings.admin_user, unique("ro"), ["read:repository", "read:user"]))
    try:
        ro = GiteaApi(token=token["sha1"])
        assert ro.get_repo(settings.admin_user, repo["name"]).status_code == 200
        assert ro.create_issue(settings.admin_user, repo["name"], "should be blocked").status_code == 403
    finally:
        api.delete(f"/users/{settings.admin_user}/tokens/{token['id']}")


def test_token_with_unknown_scope_rejected(api):
    resp = api.create_token(settings.admin_user, unique("bad"), ["bogus:scope"])
    assert resp.status_code == 400
    assert "invalid access token scope" in resp.json()["message"]


def test_non_admin_cannot_use_admin_api(temp_user):
    user_api = GiteaApi(auth=(temp_user["username"], temp_user["password"]))
    assert user_api.get("/admin/users").status_code == 403
