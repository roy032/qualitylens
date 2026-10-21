"""The CI run summary: layer counts, known bugs, and flaky-test detection across repeated runs."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("ci_summary", ROOT / "scripts" / "ci_summary.py")
ci_summary = sys.modules["ci_summary"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_summary)

pytestmark = pytest.mark.unit


def junit(tmp_path, name, cases: str) -> Path:
    path = tmp_path / name
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{cases}</testsuite></testsuites>')
    return path


PASS = '<testcase classname="tests.api.test_x" name="test_ok" time="1.5"/>'
XFAIL = ('<testcase classname="tests.api.test_x" name="test_bug" time="0.5">'
         '<skipped type="pytest.xfail" message="BUG-003: duplicate labels"/></testcase>')
SKIP = ('<testcase classname="tests.ui.test_y" name="test_skip" time="0">'
        '<skipped type="pytest.skip" message="no browser"/></testcase>')
FAIL = ('<testcase classname="tests.ui.test_y" name="test_flaky" time="3.0">'
        '<failure message="Timeout 5000ms exceeded"/></testcase>')
FLAKY_PASS = '<testcase classname="tests.ui.test_y" name="test_flaky" time="2.0"/>'


def test_outcomes_and_layers(tmp_path):
    results = ci_summary.parse(junit(tmp_path, "a.xml", PASS + XFAIL + SKIP + FAIL))
    assert [(r.layer, r.outcome) for r in results] == [
        ("api", "passed"), ("api", "known bug"), ("ui", "skipped"), ("ui", "failed")]
    assert results[0].test_id == "tests/api/test_x.py::test_ok"


def test_summary_of_one_run(tmp_path):
    text = ci_summary.summarize([ci_summary.parse(junit(tmp_path, "a.xml", PASS + XFAIL + FAIL))])
    assert "## QualityLens test run: ❌ failures" in text
    assert "| api | 2 | 1 | 0 | 1 | 0 | 2 s |" in text
    assert "| **all** | **3** | **1** | **1** | **1** | **0** | **5 s** |" in text
    assert "`tests/ui/test_y.py::test_flaky`: Timeout 5000ms exceeded" in text
    assert "BUG-003" in text
    assert "Flaky" not in text


def test_green_run(tmp_path):
    assert "✅ green" in ci_summary.summarize([ci_summary.parse(junit(tmp_path, "a.xml", PASS))])


def test_flaky_detection_across_runs(tmp_path):
    runs = [ci_summary.parse(junit(tmp_path, f"{i}.xml", PASS + XFAIL + case))
            for i, case in enumerate([FLAKY_PASS, FAIL, FLAKY_PASS])]
    assert ci_summary.flaky(runs) == {"tests/ui/test_y.py::test_flaky": ["passed", "failed", "passed"]}
    assert "- `tests/ui/test_y.py::test_flaky`: passed → failed → passed" in ci_summary.summarize(runs)


def test_stable_runs_report_no_flaky_tests(tmp_path):
    runs = [ci_summary.parse(junit(tmp_path, f"{i}.xml", PASS + XFAIL)) for i in range(3)]
    assert "None: every test gave the same result in every run." in ci_summary.summarize(runs)


def test_missing_files_are_not_an_error(tmp_path, capsys):
    assert ci_summary.main([str(tmp_path / "nope.xml")]) == 0
    assert "nothing to summarise" in capsys.readouterr().out


def test_parts_of_one_run_are_merged(tmp_path, capsys):
    smoke, full = junit(tmp_path, "smoke.xml", PASS), junit(tmp_path, "full.xml", XFAIL + SKIP)
    assert ci_summary.main([str(smoke), str(full)]) == 0
    out = capsys.readouterr().out
    assert "| **all** | **3** |" in out
    assert "Flaky" not in out


def test_runs_mode_fails_on_flaky_tests(tmp_path, capsys):
    first, second = junit(tmp_path, "run-1.xml", FLAKY_PASS), junit(tmp_path, "run-2.xml", FAIL)
    assert ci_summary.main(["--runs", str(first), str(second)]) == 1
    assert "### Flaky tests (1)" in capsys.readouterr().out
    assert ci_summary.main(["--runs", str(first), str(first)]) == 0
