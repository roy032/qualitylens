"""Authorisation between two ordinary accounts (OWASP A01 Broken Access Control). Manual cases: TC-SEC-AUTHZ-*.

`victim` data belongs to the admin; `attacker` is a regular signed-in user with no rights on it.
Each test is one thing the attacker must not be able to do, checked by status code *and* by
reading the data back as the owner, so a 403 that still changed something is caught.
"""
import allure
import pytest

from suite.api_client import GiteaApi
from suite.config import settings
from suite.data import unique

pytestmark = [pytest.mark.security, pytest.mark.api, allure.feature("Security: Access control")]
OWNER = settings.admin_user


@pytest.fixture
def attacker(temp_user) -> GiteaApi:
    return GiteaApi(auth=(temp_user["username"], temp_user["password"]))


@pytest.fixture
def private_repo(api):
    name = unique("private")
    data = api._ok(api.create_repo(name, private=True, auto_init=True))
    yield data
    api.delete_repo(OWNER, name)


@pytest.mark.smoke
@pytest.mark.parametrize("path", [
    "/repos/{owner}/{repo}",
    "/repos/{owner}/{repo}/issues",
    "/repos/{owner}/{repo}/labels",
    "/repos/{owner}/{repo}/raw/README.md",
], ids=["repo", "issues", "labels", "raw-file"])
def test_private_repo_invisible_to_other_users(attacker, private_repo, path):
    """404 rather than 403, so the attacker cannot even confirm the repository exists."""
    resp = attacker.get(path.format(owner=OWNER, repo=private_repo["name"]))
    assert resp.status_code == 404


@pytest.mark.parametrize("query", ["{name}", "%", "_"], ids=["exact-name", "wildcard-percent", "wildcard-underscore"])
def test_private_repo_not_in_search_results(attacker, private_repo, query):
    """Includes the LIKE wildcards from BUG-010, which match every name: still no private repositories."""
    found = attacker.get("/repos/search", params={"q": query.format(name=private_repo["name"]), "limit": 50})
    assert private_repo["name"] not in [r["name"] for r in found.json()["data"]]


def test_cannot_edit_someone_elses_issue(api, attacker, repo, issue):
    resp = attacker.edit_issue(OWNER, repo["name"], issue["number"], title="defaced", state="closed")
    assert resp.status_code == 403
    after = api.get_issue(OWNER, repo["name"], issue["number"]).json()
    assert (after["title"], after["state"]) == (issue["title"], "open")


def test_cannot_edit_or_delete_someone_elses_comment(api, attacker, repo, issue):
    comment = api._ok(api.add_comment(OWNER, repo["name"], issue["number"], "owner's words"))
    assert attacker.edit_comment(OWNER, repo["name"], comment["id"], "defaced").status_code == 403
    assert attacker.delete_comment(OWNER, repo["name"], comment["id"]).status_code == 403
    bodies = [c["body"] for c in api.list_comments(OWNER, repo["name"], issue["number"]).json()]
    assert bodies == ["owner's words"]


def test_can_comment_on_public_issue(attacker, repo, issue):
    """The positive control: the attacker is a real, working account, so the 403s above mean something."""
    assert attacker.add_comment(OWNER, repo["name"], issue["number"], "me too").status_code == 201


@pytest.mark.parametrize("action", [
    pytest.param(lambda u, r: u.delete_repo(OWNER, r), id="delete-repo"),
    pytest.param(lambda u, r: u.patch(f"/repos/{OWNER}/{r}", json={"private": True}), id="change-settings"),
    pytest.param(lambda u, r: u.create_label(OWNER, r, "spam"), id="create-label"),
    pytest.param(lambda u, r: u.create_milestone(OWNER, r, "spam"), id="create-milestone"),
    pytest.param(lambda u, r: u.request("PUT", f"/repos/{OWNER}/{r}/collaborators/{u.session.auth[0]}",
                                        json={"permission": "admin"}), id="self-add-collaborator"),
])
def test_cannot_administer_someone_elses_repo(api, attacker, repo, action):
    assert action(attacker, repo["name"]).status_code == 403
    after = api.get_repo(OWNER, repo["name"]).json()
    assert after["private"] is False
    assert api.list_labels(OWNER, repo["name"]).json() == []


@pytest.mark.parametrize("action", [
    pytest.param(lambda u, me: u.patch(f"/admin/users/{me}", json={"admin": True, "login_name": me, "source_id": 0}),
                 id="promote-self-to-admin"),
    pytest.param(lambda u, me: u.delete_user(OWNER), id="delete-admin"),
    pytest.param(lambda u, me: u.get(f"/users/{OWNER}/tokens"), id="list-admin-tokens"),
    pytest.param(lambda u, me: u.create_token(OWNER, unique("steal"), ["all"]), id="mint-admin-token"),
])
def test_no_privilege_escalation(api, attacker, temp_user, action):
    resp = action(attacker, temp_user["username"])
    assert resp.status_code in (401, 403), resp.text[:200]
    assert api.get(f"/users/{temp_user['username']}").json()["is_admin"] is False


def test_email_hidden_from_anonymous_visitors(anon_api, temp_user):
    """Profiles are public, but the real address is replaced by a no-reply alias."""
    profile = anon_api.get(f"/users/{temp_user['username']}").json()
    assert profile["email"] != temp_user["email"]
    assert profile["email"].endswith("@noreply.localhost")


@pytest.mark.parametrize("call", [
    pytest.param(lambda a, r: a.create_issue(OWNER, r, "anon"), id="create-issue"),
    pytest.param(lambda a, r: a.add_comment(OWNER, r, 1, "anon"), id="comment"),
    pytest.param(lambda a, r: a.create_repo(unique("anon")), id="create-repo"),
    pytest.param(lambda a, r: a.me(), id="read-own-profile"),
])
def test_anonymous_writes_require_login(anon_api, repo, issue, call):
    assert call(anon_api, repo["name"]).status_code == 401
