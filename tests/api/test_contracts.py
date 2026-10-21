"""Response contracts: every key endpoint returns the documented shape. Manual cases: TC-API-CONTRACT-*.

Status-code tests prove the server accepted a request; these prove a client can still read the
answer. Each failure lists every broken field at once, so one run shows the whole drift.
"""
import allure
import pytest

from qualitylens import schemas
from qualitylens.config import settings
from qualitylens.data import unique

pytestmark = [pytest.mark.api, allure.feature("API: Contracts")]
OWNER = settings.admin_user


def assert_contract(resp, schema, status=200):
    assert resp.status_code == status, resp.text[:300]
    errors = schemas.contract_errors(resp.json(), schema)
    assert errors == [], "Contract broken:\n" + "\n".join(errors)


@pytest.mark.smoke
def test_current_user_contract(api):
    assert_contract(api.me(), schemas.USER)


def test_repository_contract(api, repo):
    assert_contract(api.get_repo(OWNER, repo["name"]), schemas.REPOSITORY)


def test_repository_search_contract(api, repo):
    resp = api.get("/repos/search", params={"q": repo["name"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert schemas.contract_errors(body["data"], schemas.list_of(schemas.REPOSITORY)) == []
    assert [r["name"] for r in body["data"]] == [repo["name"]]


def test_issue_contract_with_label_and_milestone(api, repo):
    label = api._ok(api.create_label(OWNER, repo["name"], "bug"))
    milestone = api._ok(api.create_milestone(OWNER, repo["name"], "v1.0"))
    resp = api.create_issue(OWNER, repo["name"], unique("contract"), labels=[label["id"]],
                            milestone=milestone["id"])
    assert_contract(resp, schemas.ISSUE, status=201)
    body = resp.json()
    assert [lb["name"] for lb in body["labels"]] == ["bug"]
    assert body["milestone"]["title"] == "v1.0"


def test_issue_list_contract(api, repo, issue):
    assert_contract(api.list_issues(OWNER, repo["name"]), schemas.list_of(schemas.ISSUE))


def test_comment_contract(api, repo, issue):
    assert_contract(api.add_comment(OWNER, repo["name"], issue["number"], "contract check"),
                    schemas.COMMENT, status=201)


def test_label_contract(api, repo):
    assert_contract(api.create_label(OWNER, repo["name"], "needs-triage", "#00AAFF"), schemas.LABEL, status=201)


def test_milestone_contract(api, repo):
    resp = api.create_milestone(OWNER, repo["name"], "Sprint 1", due_on="2026-12-31T00:00:00Z")
    assert_contract(resp, schemas.MILESTONE, status=201)
    assert resp.json()["due_on"] == "2026-12-31T00:00:00Z"


@pytest.mark.parametrize("call", [
    pytest.param(lambda api: api.get_repo(OWNER, "missing-" + unique("x")), id="missing-repo"),
    pytest.param(lambda api: api.create_repo("has space"), id="validation"),
    pytest.param(lambda api: api.create_token(OWNER, unique("t"), ["bogus:scope"]), id="bad-scope"),
])
def test_errors_share_one_shape(api, call):
    """Clients parse errors in one place, so every 4xx must carry the same {message, url} body."""
    resp = call(api)
    assert 400 <= resp.status_code < 500
    assert schemas.contract_errors(resp.json(), schemas.ERROR) == []


def test_json_content_type(api):
    resp = api.me()
    assert resp.headers["Content-Type"].startswith("application/json")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
