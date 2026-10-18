"""Repository API: create, read, delete and name validation. Manual cases: TC-API-REPO-*."""
import allure
import pytest

from qualitylens.config import settings
from qualitylens.data import unique

pytestmark = [pytest.mark.api, allure.feature("API: Repositories")]
OWNER = settings.admin_user


@pytest.fixture
def cleanup(api):
    names = []
    yield names
    for name in names:
        api.delete_repo(OWNER, name)


@pytest.mark.smoke
def test_create_and_get_repo(api, cleanup):
    name = unique("api-repo")
    cleanup.append(name)
    created = api.create_repo(name, description="desc", private=True, auto_init=True)
    assert created.status_code == 201
    fetched = api.get_repo(OWNER, name).json()
    assert fetched["full_name"] == f"{OWNER}/{name}"
    assert fetched["private"] is True
    assert fetched["description"] == "desc"
    assert fetched["default_branch"] == "main"
    assert fetched["empty"] is False  # auto_init created a first commit


def test_duplicate_repo_returns_409(api, repo):
    resp = api.create_repo(repo["name"])
    assert resp.status_code == 409
    assert resp.json()["message"] == "The repository with the same name already exists."


@pytest.mark.parametrize("length, status", [(1, 201), (100, 201), (101, 422)], ids=["1", "100", "101"])
def test_repo_name_length_boundaries(api, cleanup, length, status):
    name = ("r" + unique("")[1:] + "x" * 100)[:length]
    cleanup.append(name)
    assert api.create_repo(name).status_code == status


@pytest.mark.parametrize("name, message", [
    ("", "[Name]: Required"),
    ("has space", "[Name]: AlphaDashDot"),
    ("x.git", "name pattern is not allowed [pattern: *.git]"),
    ("..", "name is reserved [name: ..]"),
])
def test_invalid_repo_names(api, name, message):
    resp = api.create_repo(name)
    assert resp.status_code == 422
    assert resp.json()["message"] == message


def test_delete_repo(api):
    name = unique("api-del")
    api._ok(api.create_repo(name))
    assert api.delete_repo(OWNER, name).status_code == 204
    assert api.get_repo(OWNER, name).status_code == 404


def test_delete_missing_repo_returns_404(api):
    assert api.delete_repo(OWNER, "does-not-exist-" + unique("x")).status_code == 404


def test_private_repo_hidden_from_anonymous(api, anon_api, cleanup):
    name = unique("secret")
    cleanup.append(name)
    api._ok(api.create_repo(name, private=True))
    assert anon_api.get_repo(OWNER, name).status_code == 404  # 404, not 403: don't confirm it exists
