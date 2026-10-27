"""Label API. Manual cases: TC-API-LABEL-*."""
import allure
import pytest

from suite.config import settings

pytestmark = [pytest.mark.api, allure.feature("API: Labels")]
OWNER = settings.admin_user


def test_create_label_normalises_color(api, repo):
    resp = api.create_label(OWNER, repo["name"], "bug", "#FF0000")
    assert resp.status_code == 201
    assert resp.json()["color"].lower() == "ff0000"


@pytest.mark.parametrize("color", ["zzzzzz", "#12345", "red"])
def test_invalid_color_rejected(api, repo, color):
    assert api.create_label(OWNER, repo["name"], "bad", color).status_code == 422


def test_label_can_be_applied_to_issue(api, repo, issue):
    label = api._ok(api.create_label(OWNER, repo["name"], "priority-high"))
    resp = api.post(f"/repos/{OWNER}/{repo['name']}/issues/{issue['number']}/labels", json={"labels": [label["id"]]})
    assert resp.status_code == 200
    assert [lbl["name"] for lbl in api.get_issue(OWNER, repo["name"], issue["number"]).json()["labels"]] == ["priority-high"]


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-003: duplicate label names are allowed in one repository")
def test_duplicate_label_name_rejected(api, repo):
    api._ok(api.create_label(OWNER, repo["name"], "bug"))
    assert api.create_label(OWNER, repo["name"], "bug").status_code in (409, 422)
