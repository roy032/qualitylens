"""Comment lifecycle on the API: add, list, edit, delete. Manual cases: TC-API-COMMENT-*."""
import allure
import pytest

from suite.config import settings

pytestmark = [pytest.mark.api, allure.feature("API: Comments")]
OWNER = settings.admin_user


def test_comment_counter_follows_add_and_delete(api, repo, issue):
    first = api._ok(api.add_comment(OWNER, repo["name"], issue["number"], "first"))
    api._ok(api.add_comment(OWNER, repo["name"], issue["number"], "second"))
    assert api.get_issue(OWNER, repo["name"], issue["number"]).json()["comments"] == 2

    assert api.delete_comment(OWNER, repo["name"], first["id"]).status_code == 204
    listed = api.list_comments(OWNER, repo["name"], issue["number"]).json()
    assert [c["body"] for c in listed] == ["second"]
    assert api.get_issue(OWNER, repo["name"], issue["number"]).json()["comments"] == 1


def test_edit_comment(api, repo, issue):
    comment = api._ok(api.add_comment(OWNER, repo["name"], issue["number"], "typo"))
    resp = api.edit_comment(OWNER, repo["name"], comment["id"], "fixed")
    assert resp.status_code == 200
    assert resp.json()["body"] == "fixed"
    assert resp.json()["updated_at"] >= comment["updated_at"]


def test_delete_missing_comment_returns_404(api, repo):
    assert api.delete_comment(OWNER, repo["name"], 99999999).status_code == 404


def test_comments_listed_oldest_first(api, repo, issue):
    for body in ("one", "two", "three"):
        api._ok(api.add_comment(OWNER, repo["name"], issue["number"], body))
    listed = api.list_comments(OWNER, repo["name"], issue["number"]).json()
    assert [c["body"] for c in listed] == ["one", "two", "three"]
