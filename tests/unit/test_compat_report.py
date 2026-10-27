"""The Gitea compatibility report: per-version totals, known-bug status, and tests that changed."""
import pytest

from qualitylens import compat as compat_report

pytestmark = pytest.mark.unit

OK = '<testcase classname="tests.api.test_x" name="test_ok" time="1"/>'
BUG = ('<testcase classname="tests.api.test_x" name="test_bug" time="1">'
       '<skipped type="pytest.xfail" message="BUG-002: truncation"/></testcase>')
BUG_FIXED = ('<testcase classname="tests.api.test_x" name="test_bug" time="1">'
             '<failure message="[XPASS(strict)] BUG-002: truncation"/></testcase>')
BUG_10 = ('<testcase classname="tests.api.test_x" name="test_bug10" time="1">'
          '<skipped type="pytest.xfail" message="BUG-010: wildcards"/></testcase>')
UI = '<testcase classname="tests.ui.test_y" name="test_menu" time="1"/>'
UI_BROKEN = ('<testcase classname="tests.ui.test_y" name="test_menu" time="1">'
             '<failure message="locator not found"/></testcase>')


def junit(path, cases):
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{cases}</testsuite></testsuites>')
    return path


def test_report_compares_versions(tmp_path):
    old = junit(tmp_path / "old.xml", OK + BUG + BUG_10 + UI)
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    junit(new_dir / "a.xml", OK + BUG_FIXED)
    junit(new_dir / "b.xml", BUG_10 + UI_BROKEN)
    text = compat_report.report([compat_report.load(f"1.22.6={old}"), compat_report.load(f"28.2.0={new_dir}")])
    assert text == "\n".join([
        "## Gitea compatibility", "",
        "| Gitea | Tests | Passed | Failed | Known bug | Skipped |",
        "|---|---:|---:|---:|---:|---:|",
        "| 1.22.6 | 4 | 2 | 0 | 2 | 0 |",
        "| 28.2.0 | 4 | 1 | 2 | 1 | 0 |", "",
        "### Known bugs", "",
        "| Bug | 1.22.6 | 28.2.0 |", "|---|---|---|",
        "| BUG-002 | reproduces | fixed? |",
        "| BUG-010 | reproduces | reproduces |", "",
        "### Tests with a different result across versions (2)", "",
        "| Test | 1.22.6 | 28.2.0 |", "|---|---|---|",
        "| `tests/api/test_x.py::test_bug` | known bug | bug fixed (XPASS) |",
        "| `tests/ui/test_y.py::test_menu` | passed | failed |",
    ]) + "\n"


def test_identical_runs(tmp_path):
    run = junit(tmp_path / "r.xml", OK)
    text = compat_report.report([compat_report.load(f"a={run}"), compat_report.load(f"b={run}")])
    assert text.endswith("### Tests with a different result across versions (0)\n\n"
                         "None: every test behaves the same on every version.\n")
    assert "### Known bugs" not in text


def test_a_test_missing_on_one_version_is_reported(tmp_path):
    a, b = junit(tmp_path / "a.xml", OK + UI), junit(tmp_path / "b.xml", OK)
    text = compat_report.report([compat_report.load(f"a={a}"), compat_report.load(f"b={b}")])
    assert "| `tests/ui/test_y.py::test_menu` | passed | not run |" in text


def test_bad_arguments(tmp_path, capsys):
    with pytest.raises(SystemExit, match="VERSION=PATH"):
        compat_report.load("results.xml")
    assert compat_report.main(["only-one=x.xml"]) == 2
    run = junit(tmp_path / "r.xml", OK)
    assert compat_report.main([f"a={run}", f"b={run}"]) == 0
    assert "## Gitea compatibility" in capsys.readouterr().out
