"""Test history and flaky scoring: a test is flaky when its outcome keeps flipping, not when it broke once."""
import json
from datetime import UTC, datetime

import pytest

from qualitylens import history
from qualitylens.junit import Result

pytestmark = pytest.mark.unit


def run(label, **outcomes):
    """run("r1", a="passed", b=("failed", 2.0)) -> stored run."""
    results = {}
    for name, value in outcomes.items():
        outcome, secs = value if isinstance(value, tuple) else (value, 1.0)
        results[f"tests/api/test_x.py::{name}"] = [outcome, secs]
    return {"label": label, "time": "2026-10-22T10:00:00+00:00", "results": results}


def series(name, outcomes):
    return [run(f"r{i}", **{name: o}) for i, o in enumerate(outcomes)]


def stat(outcomes, name="t"):
    return history.stats(series(name, outcomes))[f"tests/api/test_x.py::{name}"]


def test_make_run_keeps_outcome_and_rounded_seconds():
    results = [Result("tests/api/test_x.py::a", "api", "passed", 1.23456),
               Result("tests/api/test_x.py::b", "api", "known bug", 0.5, "BUG-001")]
    stored = history.make_run(results, "abc123", datetime(2026, 10, 22, 9, 30, tzinfo=UTC))
    assert stored == {"label": "abc123", "time": "2026-10-22T09:30:00+00:00",
                      "results": {"tests/api/test_x.py::a": ["passed", 1.235],
                                  "tests/api/test_x.py::b": ["known bug", 0.5]}}


def test_make_run_defaults_to_now():
    stamp = history.make_run([], "x")["time"]
    assert stamp.startswith(str(datetime.now(UTC).year)) and stamp.endswith("+00:00")


def test_save_keeps_the_newest_runs_and_load_reads_them_back(tmp_path):
    store = tmp_path / "a" / "b" / "history.json"
    history.save(store, [run(f"r{i}", a="passed") for i in range(5)], keep=3)
    assert [r["label"] for r in history.load(store)] == ["r2", "r3", "r4"]
    assert store.read_text().startswith('[{"label":"r2","time":')  # compact: the store grows with every run


def test_save_default_keep():
    assert history.DEFAULT_KEEP == 50


@pytest.mark.parametrize("content", ["not json", '{"a": 1}', "[1, {\"label\": \"x\"}]"])
def test_unreadable_or_foreign_store_is_an_empty_history(tmp_path, content):
    store = tmp_path / "h.json"
    store.write_text(content)
    assert history.load(store) == []


def test_load_keeps_valid_runs_only(tmp_path):
    store = tmp_path / "h.json"
    store.write_text(json.dumps([{"label": "bad"}, run("good", a="passed")]))
    assert [r["label"] for r in history.load(store)] == ["good"]


def test_missing_store_is_an_empty_history(tmp_path):
    assert history.load(tmp_path / "nope.json") == []


def test_stats_collects_outcomes_in_order_and_mean_time():
    runs = [run("1", a=("passed", 1.0)), run("2", a=("failed", 3.0)), run("3", b="passed")]
    s = history.stats(runs)
    assert list(s) == ["tests/api/test_x.py::a", "tests/api/test_x.py::b"]
    a = s["tests/api/test_x.py::a"]
    assert a.outcomes == ("passed", "failed")
    assert a.mean_seconds == 2.0 and a.last_seconds == 3.0


def test_skipped_runs_do_not_count_as_executions_or_flips():
    s = stat(["passed", "skipped", "passed", "skipped"])
    assert s.executed == ("passed", "passed")
    assert s.runs == 2 and s.flips == 0 and s.flip_rate == 0.0
    assert s.last == "skipped"


def test_flips_and_flip_rate():
    s = stat(["passed", "failed", "passed", "passed", "failed"])
    assert s.flips == 3
    assert s.failures == 2
    assert s.flip_rate == pytest.approx(3 / 4)


def test_known_bug_is_its_own_outcome():
    assert stat(["known bug", "passed", "known bug"]).flips == 2


def test_single_run_has_no_flip_rate():
    assert stat(["failed"]).flip_rate == 0.0


def test_last_of_empty_stats_is_skipped():
    assert history.TestStats("x", (), 0.0, 0.0).last == "skipped"


def test_timeline_shows_the_most_recent_runs():
    s = stat(["passed", "failed", "known bug", "skipped", "weird"])
    assert s.timeline() == "✓✗◌·?"
    assert s.timeline(width=2) == "·?"
    assert len(stat(["passed"] * 25).timeline()) == 20


def test_a_regression_that_was_fixed_is_not_flaky():
    s = stat(["passed"] * 10 + ["failed"] * 3 + ["passed"] * 10)
    assert s.flip_rate < history.DEFAULT_THRESHOLD
    assert history.classify(s) == "stable"


def test_a_test_that_alternates_is_flaky():
    s = stat(["passed", "failed", "passed", "passed", "passed", "failed", "passed", "passed", "passed", "passed"])
    assert history.classify(s) == "flaky"


def test_failing_now_without_flipping_is_failing_not_flaky():
    assert history.classify(stat(["passed"] * 10 + ["failed"])) == "failing"
    assert history.classify(stat(["passed"] * 3 + ["failed"] * 2)) == "failing"
    assert history.classify(stat(["failed"] * 3)) == "failing"
    assert history.classify(stat(["passed"] * 9 + ["failed", "passed", "failed"])) == "flaky"
    assert history.classify(stat(["failed"] + ["passed"] * 9 + ["failed"])) == "flaky"  # 2 flips
    assert history.classify(stat(["passed", "failed", "passed", "failed"])) == "new"


def test_flaky_wins_over_failing_when_it_flips_a_lot():
    outcomes = ["passed", "failed"] * 6
    assert history.classify(stat(outcomes)) == "flaky"


def test_too_few_runs_is_new():
    assert history.classify(stat(["passed", "failed", "passed"])) == "new"
    assert history.classify(stat(["passed", "failed", "passed"]), min_runs=3) == "flaky"


def test_thresholds_are_inclusive():
    s = stat(["passed"] * 8 + ["failed", "passed"])  # 2 flips in 9 transitions
    assert history.classify(s, min_runs=10, threshold=2 / 9 + 0.001) == "stable"
    s = stat(["passed"] * 8 + ["failed", "passed"])  # 2 flips in 9
    assert history.classify(s, min_runs=10, threshold=2 / 9) == "flaky"
    assert history.classify(s, min_runs=11, threshold=2 / 9) == "new"


def test_defaults():
    assert history.DEFAULT_MIN_RUNS == 10
    assert history.DEFAULT_THRESHOLD == 0.1


def test_flaky_tests_sorted_most_unstable_first():
    runs = []
    for i in range(10):
        runs.append(run(f"r{i}", a="passed" if i % 2 else "failed", b="failed" if i in (3, 7) else "passed",
                        c="passed"))
    found = history.flaky_tests(runs)
    assert [s.test_id.rsplit("::", 1)[1] for s in found] == ["a", "b"]


def test_flaky_tests_tie_breaks_by_name():
    runs = [run(f"r{i}", b="passed" if i % 2 else "failed", a="passed" if i % 2 else "failed") for i in range(10)]
    assert [s.test_id.rsplit("::", 1)[1] for s in history.flaky_tests(runs)] == ["a", "b"]


def test_pass_rate_counts_known_bugs_as_expected_and_ignores_skips():
    assert history.pass_rate(run("x", a="passed", b="known bug", c="failed", d="skipped")) == pytest.approx(200 / 3)
    assert history.pass_rate(run("x", a="skipped")) == 100.0


def flaky_history():
    return [run(f"r{i}", a="passed" if i % 2 else "failed", b="passed") for i in range(10)]


def test_report_lists_unquarantined_flaky_tests_as_action_items():
    text, open_items = history.flaky_report(flaky_history(), quarantined=set())
    assert text.startswith("## Flaky tests: ❌ 1 flaky test(s) not quarantined\n\n")
    assert "10 run(s) in history; a test is flaky when its outcome flips in at least 10% of consecutive " \
           "runs (minimum 10 runs)." in text
    assert "\n| Test | Flip rate | Failures | Timeline (oldest → newest) | Quarantined |\n|---|---:|---:|---|:---:|\n" in text
    assert "| `tests/api/test_x.py::a` | 100% | 5/10 | `✗✓✗✓✗✓✗✓✗✓` | **no** |" in text
    assert [s.test_id for s in open_items] == ["tests/api/test_x.py::a"]


def test_report_with_everything_quarantined_is_green():
    text, open_items = history.flaky_report(flaky_history(), quarantined={"tests/api/test_x.py::a"})
    assert text.startswith("## Flaky tests: ✅ no unhandled flaky tests")
    assert "| yes |" in text
    assert open_items == []


def test_report_while_collecting_history():
    text, _ = history.flaky_report([run("r", a="passed")], quarantined=set())
    assert text == ("## Flaky tests: ⏳ collecting history (1 of 10 runs)\n\n"
                    "1 run(s) in history; a test is flaky when its outcome flips in at least 10% of consecutive "
                    "runs (minimum 10 runs).\n\nNone found.\n")
