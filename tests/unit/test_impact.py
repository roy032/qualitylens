"""Test impact selection: a change selects the layers it can affect, and anything unknown selects everything."""
import subprocess

import pytest

from qualitylens import impact

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("path, layers", [
    ("README.md", set()),
    ("load/README.md", set()),
    ("docs/test-plan.md", set()),
    ("docs/img/x.png", set()),
    ("bug-reports/evidence/BUG-001.txt", set()),
    ("LICENSE", set()),
    (".github/ISSUE_TEMPLATE/bug.yml", set()),
    ("test-cases/manual_test_cases.csv", {"unit"}),
    ("tests/unit/test_history.py", {"unit"}),
    ("tests/ui/test_login.py", {"ui"}),
    ("tests/api/test_properties.py", {"property"}),
    ("tests/api/test_issues_api.py", {"api"}),
    ("tests/db/test_db_consistency.py", {"db"}),
    ("tests/security/test_web_security.py", {"security"}),
    ("tests/a11y/baseline.json", {"a11y"}),
    ("tests/visual/baseline/1.22.6/login.png", {"visual"}),
    ("pages/login_page.py", {"ui", "a11y", "visual", "security"}),
    ("qualitylens/schemas.py", {"unit", "api"}),
    ("qualitylens/oracles.py", {"unit", "property"}),
    ("qualitylens/a11y.py", {"unit", "a11y"}),
    ("qualitylens/visual.py", {"unit", "visual"}),
    ("qualitylens/db.py", {"db"}),
    ("sql/integrity_checks.sql", {"db"}),
    ("load/locustfile.py", {"load"}),
    ("ai/evaluate.py", {"unit"}),
    ("scripts/bootstrap.sh", {"all"}),
    ("scripts/ci_summary.py", {"unit"}),
    ("quarantine.toml", {"unit"}),
    ("qualitylens/junit.py", {"unit"}),
    ("qualitylens/history.py", {"unit"}),
    ("qualitylens/quarantine.py", {"unit"}),
    ("qualitylens/impact.py", {"unit"}),
    ("qualitylens/dashboard.py", {"unit"}),
    ("qualitylens/doctor.py", {"unit"}),
    ("qualitylens/cli.py", {"unit"}),
    # shared by every layer, or unknown: everything
    ("tests/conftest.py", {"all"}),
    ("qualitylens/api_client.py", {"all"}),
    ("qualitylens/config.py", {"all"}),
    ("requirements.txt", {"all"}),
    ("docker-compose.yml", {"all"}),
    (".github/workflows/ci.yml", {"all"}),
    ("something/new.py", {"all"}),
])
def test_layers_for(path, layers):
    assert impact.layers_for(path) == layers


def test_select_combines_layers():
    assert impact.select(["tests/ui/test_login.py", " tests/db/test_db_consistency.py ", "README.md"]) == {"ui", "db"}


def test_select_all_wins():
    assert impact.select(["tests/ui/test_login.py", "requirements.txt"]) == {"all"}


def test_select_nothing():
    assert impact.select([]) == set()
    assert impact.select(["README.md"]) == set()


def test_marker_expression():
    assert impact.marker_expression({"all", "ui"}) == "all"
    assert impact.marker_expression({"ui", "db", "a11y"}) == "a11y or db or ui"
    assert impact.marker_expression({"load"}) == "none"
    assert impact.marker_expression(set()) == "none"
    assert impact.marker_expression({"load", "api"}) == "api"


def test_changed_files_merges_branch_and_working_tree(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        assert kwargs == {"capture_output": True, "text": True, "check": True}
        calls.append(cmd)
        out = "a.py\nb.py\n" if "main...HEAD" in cmd else "b.py\n\nc.py\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out)

    monkeypatch.setattr(impact.subprocess, "run", fake_run)
    assert impact.changed_files("main") == ["a.py", "b.py", "c.py"]
    assert calls == [["git", "diff", "--name-only", "main...HEAD"], ["git", "diff", "--name-only", "HEAD"]]
