"""The CI run summary: layer counts, known bugs, and flaky-test detection across repeated runs."""
from pathlib import Path

import pytest

from scripts import ci_summary

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
    assert "\n### Flaky tests (0)\n\nNone: every test gave the same result in every run.\n\n" in ci_summary.summarize(runs)


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


# The cases below were added after mutation testing (make mutation) showed that small changes to
# the summary's wording, ordering and edge cases went unnoticed.
ERROR = ('<testcase classname="tests.db.test_z" name="test_err" time="2.25">'
         '<error message="' + "x" * 205 + '"/></testcase>')
XFAIL_2 = ('<testcase classname="tests.api.test_x" name="test_bug" time="0.5">'
           '<skipped type="pytest.xfail" message="BUG-003: duplicate labels: see report"/></testcase>')


def test_full_summary_of_repeated_runs_is_exact(tmp_path):
    runs = [ci_summary.parse(junit(tmp_path, "1.xml", PASS + FLAKY_PASS)),
            ci_summary.parse(junit(tmp_path, "2.xml", PASS + XFAIL_2 + ERROR + FAIL.replace("Timeout 5000ms exceeded", "Timeout")))]
    assert ci_summary.summarize(runs, slowest=2) == "\n".join([
        "## QualityLens test run: ❌ failures", "",
        "Combined view of 2 runs; the table shows the last one.", "",
        "| Layer | Tests | Passed | Failed | Known bug | Skipped | Time |",
        "|---|---:|---:|---:|---:|---:|---:|",
        "| api | 2 | 1 | 0 | 1 | 0 | 2 s |",
        "| db | 1 | 0 | 1 | 0 | 0 | 2 s |",
        "| ui | 1 | 0 | 1 | 0 | 0 | 3 s |",
        "| **all** | **4** | **1** | **2** | **1** | **0** | **7 s** |", "",
        "### Failures", "",
        "- `tests/db/test_z.py::test_err`: " + "x" * 200,
        "- `tests/ui/test_y.py::test_flaky`: Timeout", "",
        "### Flaky tests (1)", "",
        "- `tests/ui/test_y.py::test_flaky`: passed → failed", "",
        "### Known bugs still reproducing (1)", "",
        "BUG-003", "",
        "### Slowest 2", "",
        "- 3.0 s `tests/ui/test_y.py::test_flaky`",
        "- 2.2 s `tests/db/test_z.py::test_err`",
    ]) + "\n"


def test_full_summary_of_a_green_run_is_exact(tmp_path):
    no_bug_id = '<testcase classname="tests.api.test_x" name="test_odd" time="0"><skipped type="pytest.xfail" message="flaky upstream"/></testcase>'
    text = ci_summary.summarize([ci_summary.parse(junit(tmp_path, "a.xml", PASS + PASS + no_bug_id))], slowest=1)
    assert text == "\n".join([
        "## QualityLens test run: ✅ green", "",
        "| Layer | Tests | Passed | Failed | Known bug | Skipped | Time |",
        "|---|---:|---:|---:|---:|---:|---:|",
        "| api | 3 | 2 | 0 | 1 | 0 | 3 s |",
        "| **all** | **3** | **2** | **0** | **1** | **0** | **3 s** |", "",
        "### Known bugs still reproducing (0)", "", "-", "",
        "### Slowest 1", "",
        "- 1.5 s `tests/api/test_x.py::test_ok`",
    ]) + "\n"


def test_several_known_bugs_are_listed_once_each(tmp_path):
    bug = '<testcase classname="tests.api.test_x" name="t{0}"><skipped type="pytest.xfail" message="BUG-00{0}: x"/></testcase>'
    text = ci_summary.summarize([ci_summary.parse(junit(tmp_path, "a.xml", bug.format(2) + bug.format(1) + bug.format(2)))])
    assert "### Known bugs still reproducing (2)\n\nBUG-001, BUG-002\n" in text


def test_parse_edge_cases(tmp_path):
    cases = ('<testcase classname="conftest" name="test_setup"/>'
             '<testcase classname="tests.test_top" name="test_a"><failure/></testcase>'
             '<testcase classname="tests.ui.test_y" name="test_b"><skipped/></testcase>'
             '<testcase name="test_c"><error/></testcase>')
    results = ci_summary.parse(junit(tmp_path, "a.xml", cases))
    assert results == [
        ci_summary.Result("conftest.py::test_setup", "other", "passed", 0.0, ""),
        ci_summary.Result("tests/test_top.py::test_a", "other", "failed", 0.0, ""),
        ci_summary.Result("tests/ui/test_y.py::test_b", "ui", "skipped", 0.0, ""),
        ci_summary.Result(".py::test_c", "other", "failed", 0.0, ""),
    ]


def test_repeated_runs_with_a_flaky_test_exit_1(tmp_path, capsys):
    a, b = junit(tmp_path, "1.xml", FLAKY_PASS), junit(tmp_path, "2.xml", FAIL)
    assert ci_summary.main(["--runs", str(a), str(b)]) == 1
    assert "### Flaky tests (1)" in capsys.readouterr().out
    assert ci_summary.main(["--runs", str(a), str(a)]) == 0


def test_no_input_message_is_exact(capsys):
    assert ci_summary.main(["--runs"]) == 0
    assert capsys.readouterr().out == "No JUnit XML found; nothing to summarise.\n"
