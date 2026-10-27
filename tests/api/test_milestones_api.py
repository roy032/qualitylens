"""Milestones: create, link issues, progress counters, validation. Manual cases: TC-API-MILESTONE-*."""
import allure
import pytest

from suite.config import settings

pytestmark = [pytest.mark.api, allure.feature("API: Milestones")]
OWNER = settings.admin_user


@pytest.fixture
def milestone(api, repo):
    return api._ok(api.create_milestone(OWNER, repo["name"], "Release 1"))


def test_create_milestone_defaults(api, repo):
    resp = api.create_milestone(OWNER, repo["name"], "Release 1", description="first cut")
    assert resp.status_code == 201
    body = resp.json()
    assert (body["title"], body["description"], body["state"]) == ("Release 1", "first cut", "open")
    assert (body["open_issues"], body["closed_issues"]) == (0, 0)
    assert body["due_on"] is None


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-008: milestones can be created with an empty or whitespace-only title")
@pytest.mark.parametrize("title", ["", "   "], ids=["empty", "spaces"])
def test_milestone_title_required(api, repo, title):
    resp = api.create_milestone(OWNER, repo["name"], title)
    assert resp.status_code == 422


def test_milestone_counts_follow_issue_state(api, repo, milestone):
    """Two linked issues, one closed: the milestone must report 1 open / 1 closed."""
    numbers = [api._ok(api.create_issue(OWNER, repo["name"], f"task {i}", milestone=milestone["id"]))["number"]
               for i in range(2)]
    api._ok(api.edit_issue(OWNER, repo["name"], numbers[0], state="closed"))
    body = api.get_milestone(OWNER, repo["name"], milestone["id"]).json()
    assert (body["open_issues"], body["closed_issues"]) == (1, 1)


def test_close_milestone(api, repo, milestone):
    resp = api.patch(f"/repos/{OWNER}/{repo['name']}/milestones/{milestone['id']}", json={"state": "closed"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "closed"
    assert resp.json()["closed_at"] is not None


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-009: unknown milestone or label IDs are silently dropped on issue create")
@pytest.mark.parametrize("fields", [{"milestone": 999999}, {"labels": [999999]}], ids=["milestone", "label"])
def test_issue_with_unknown_reference_rejected(api, repo, fields):
    resp = api.create_issue(OWNER, repo["name"], "orphan", **fields)
    assert resp.status_code in (404, 422), f"got {resp.status_code}; stored: {resp.text[:200]}"
