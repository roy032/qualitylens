"""Issue API: positive, negative and boundary cases. Manual cases: TC-API-ISSUE-*."""
import allure
import pytest

from qualitylens.config import settings

pytestmark = [pytest.mark.api, allure.feature("API: Issues")]
OWNER = settings.admin_user


@pytest.mark.smoke
def test_create_issue(api, repo):
    resp = api.create_issue(OWNER, repo["name"], "Checkout fails", body="Steps...")
    assert resp.status_code == 201
    body = resp.json()
    assert body["number"] == 1
    assert body["state"] == "open"
    assert body["title"] == "Checkout fails"
    assert body["user"]["login"] == OWNER


def test_issue_numbers_increment_per_repo(api, repo):
    numbers = [api._ok(api.create_issue(OWNER, repo["name"], f"issue {i}"))["number"] for i in range(3)]
    assert numbers == [1, 2, 3]


@pytest.mark.parametrize("title", [
    "x",                               # min length
    "x" * 255,                         # max length (DB column is varchar(255))
    "ünïcödé 测试 🐞",                  # multi-byte characters
    "<script>alert(1)</script>",       # stored as text, never executed
    "'; DROP TABLE issue; --",         # SQL metacharacters stored literally
], ids=["1-char", "255-chars", "unicode", "html", "sql"])
def test_title_round_trips_exactly(api, repo, title):
    created = api._ok(api.create_issue(OWNER, repo["name"], title))
    assert api.get_issue(OWNER, repo["name"], created["number"]).json()["title"] == title


def test_empty_title_rejected(api, repo):
    resp = api.create_issue(OWNER, repo["name"], "")
    assert resp.status_code == 422
    assert resp.json()["message"] == "[Title]: Required"


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-001: API accepts whitespace-only title and stores an empty title")
def test_whitespace_title_rejected(api, repo):
    resp = api.create_issue(OWNER, repo["name"], "   ")
    assert resp.status_code == 422


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-002: titles over 255 chars are silently truncated instead of rejected")
def test_title_over_255_rejected(api, repo):
    resp = api.create_issue(OWNER, repo["name"], "x" * 256)
    assert resp.status_code == 422


def test_create_issue_without_auth(anon_api, repo):
    assert anon_api.create_issue(OWNER, repo["name"], "anon").status_code == 401


def test_create_issue_on_missing_repo(api):
    assert api.create_issue(OWNER, "no-such-repo-qualitylens", "x").status_code == 404


@pytest.mark.parametrize("number", ["0", "-1", "999999", "abc"])
def test_get_missing_issue(api, repo, number):
    assert api.get_issue(OWNER, repo["name"], number).status_code == 404


def test_close_and_reopen_issue(api, repo, issue):
    closed = api.edit_issue(OWNER, repo["name"], issue["number"], state="closed")
    assert closed.status_code == 201  # Gitea documents 201 for this PATCH
    assert closed.json()["state"] == "closed" and closed.json()["closed_at"]
    reopened = api.edit_issue(OWNER, repo["name"], issue["number"], state="open").json()
    assert reopened["state"] == "open" and reopened["closed_at"] is None


def test_list_filters_by_state(api, repo):
    open_issue = api._ok(api.create_issue(OWNER, repo["name"], "stays open"))
    closed_issue = api._ok(api.create_issue(OWNER, repo["name"], "gets closed"))
    api.edit_issue(OWNER, repo["name"], closed_issue["number"], state="closed")

    def numbers(state):
        return {i["number"] for i in api.list_issues(OWNER, repo["name"], state=state, type="issues").json()}

    assert numbers("open") == {open_issue["number"]}
    assert numbers("closed") == {closed_issue["number"]}
    assert numbers("all") == {open_issue["number"], closed_issue["number"]}


def test_pagination(api, repo):
    for i in range(5):
        api._ok(api.create_issue(OWNER, repo["name"], f"page item {i}"))
    page1 = api.list_issues(OWNER, repo["name"], limit=2, page=1, type="issues")
    page3 = api.list_issues(OWNER, repo["name"], limit=2, page=3, type="issues")
    assert page1.headers["X-Total-Count"] == "5"
    assert len(page1.json()) == 2
    assert len(page3.json()) == 1


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-005: unknown state filter is ignored and returns 200")
def test_list_rejects_unknown_state(api, repo):
    assert api.list_issues(OWNER, repo["name"], state="bogus").status_code in (400, 422)


def test_invalid_state_on_edit_rejected(api, repo, issue):
    resp = api.edit_issue(OWNER, repo["name"], issue["number"], state="bogus")
    assert resp.status_code == 412
    assert resp.json()["message"] == "unknown state: bogus"


def test_comment_requires_body(api, repo, issue):
    assert api.add_comment(OWNER, repo["name"], issue["number"], "").status_code == 422
    ok = api.add_comment(OWNER, repo["name"], issue["number"], "Looks good")
    assert ok.status_code == 201 and ok.json()["body"] == "Looks good"


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-006: malformed JSON returns 422 with a misleading parser message")
def test_malformed_json_returns_400(api, repo):
    resp = api.post(f"/repos/{OWNER}/{repo['name']}/issues", data='{"title":',
                    headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-007: whitespace-only comment is accepted and shown as an empty comment")
def test_whitespace_comment_rejected(api, repo, issue):
    assert api.add_comment(OWNER, repo["name"], issue["number"], "   ").status_code == 422
