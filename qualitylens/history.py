"""Test-result history across runs: which tests are flaky, which are failing, which are getting slower.

A single run cannot tell a flaky test from a broken one, and retries hide both. Every CI run of the
e2e suite is appended to a JSON store (newest last, at most `keep` runs), and each test is scored on
how often its outcome flips between consecutive runs in which it executed:

    flip rate = outcome changes / (executions - 1)

A real regression that is then fixed flips twice in the whole window (pass -> fail -> pass), which
stays under the default threshold; a test that alternates at random does not. Skipped runs are
ignored, and "known bug" (strict xfail) counts as its own outcome, so a pinned bug that starts
passing on and off shows up too.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from qualitylens.junit import Result

DEFAULT_KEEP = 50
DEFAULT_MIN_RUNS = 10
DEFAULT_THRESHOLD = 0.1
EXECUTED = ("passed", "failed", "known bug")
SYMBOL = {"passed": "✓", "failed": "✗", "known bug": "◌", "skipped": "·"}


def load(path: Path) -> list[dict]:
    """Runs stored at `path`, oldest first; a missing or unreadable store is an empty history."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return []
    return [run for run in data if isinstance(run, dict) and "results" in run] if isinstance(data, list) else []


def save(path: Path, runs: list[dict], keep: int = DEFAULT_KEEP) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(runs[-keep:], separators=(",", ":")))


def make_run(results: Iterable[Result], label: str, when: datetime | None = None) -> dict:
    """One stored run: {label, time, results: {test_id: [outcome, seconds]}}."""
    stamp = (when or datetime.now(UTC)).isoformat(timespec="seconds")
    return {"label": label, "time": stamp,
            "results": {r.test_id: [r.outcome, round(r.seconds, 3)] for r in results}}


@dataclass(frozen=True)
class TestStats:
    __test__ = False  # not a pytest test class

    test_id: str
    outcomes: tuple[str, ...]  # oldest first, one per run in which the test appeared
    mean_seconds: float
    last_seconds: float

    @property
    def executed(self) -> tuple[str, ...]:
        return tuple(o for o in self.outcomes if o in EXECUTED)

    @property
    def runs(self) -> int:
        return len(self.executed)

    @property
    def failures(self) -> int:
        return self.executed.count("failed")

    @property
    def flips(self) -> int:
        seq = self.executed
        return sum(a != b for a, b in pairwise(seq))

    @property
    def flip_rate(self) -> float:
        return self.flips / (self.runs - 1) if self.runs > 1 else 0.0

    @property
    def last(self) -> str:
        return self.outcomes[-1] if self.outcomes else "skipped"

    def timeline(self, width: int = 20) -> str:
        return "".join(SYMBOL.get(o, "?") for o in self.outcomes[-width:])


def stats(runs: list[dict]) -> dict[str, TestStats]:
    outcomes: dict[str, list[str]] = {}
    seconds: dict[str, list[float]] = {}
    for run in runs:
        for test_id, (outcome, secs) in run["results"].items():
            outcomes.setdefault(test_id, []).append(outcome)
            seconds.setdefault(test_id, []).append(float(secs))
    return {t: TestStats(t, tuple(outcomes[t]), sum(seconds[t]) / len(seconds[t]), seconds[t][-1])
            for t in sorted(outcomes)}


def classify(s: TestStats, min_runs: int = DEFAULT_MIN_RUNS, threshold: float = DEFAULT_THRESHOLD) -> str:
    """flaky | failing | new (not enough runs to judge) | stable.

    A test that was stable until it broke, and is still broken, is failing: a real regression, not noise.
    """
    if s.last == "failed" and s.flips <= 1:
        return "failing"
    if s.runs < min_runs:
        return "new"
    if s.flip_rate >= threshold:
        return "flaky"
    return "stable"


def flaky_tests(runs: list[dict], min_runs: int = DEFAULT_MIN_RUNS,
                threshold: float = DEFAULT_THRESHOLD) -> list[TestStats]:
    """Flaky tests, most unstable first."""
    found = [s for s in stats(runs).values() if classify(s, min_runs, threshold) == "flaky"]
    return sorted(found, key=lambda s: (-s.flip_rate, s.test_id))


def pass_rate(run: dict) -> float:
    """Share of executed tests that ended as expected (passed or a pinned known bug), in percent."""
    executed = [o for o, _ in run["results"].values() if o in EXECUTED]
    if not executed:
        return 100.0
    return 100 * sum(o != "failed" for o in executed) / len(executed)


def flaky_report(runs: list[dict], quarantined: set[str], min_runs: int = DEFAULT_MIN_RUNS,
                 threshold: float = DEFAULT_THRESHOLD) -> tuple[str, list[TestStats]]:
    """Markdown report and the flaky tests that are not quarantined yet (the action items)."""
    flaky = flaky_tests(runs, min_runs, threshold)
    open_items = [s for s in flaky if s.test_id not in quarantined]
    if len(runs) < min_runs:
        verdict = f"⏳ collecting history ({len(runs)} of {min_runs} runs)"
    elif open_items:
        verdict = f"❌ {len(open_items)} flaky test(s) not quarantined"
    else:
        verdict = "✅ no unhandled flaky tests"
    out = [f"## Flaky tests: {verdict}", "",
           f"{len(runs)} run(s) in history; a test is flaky when its outcome flips in at least "
           f"{threshold:.0%} of consecutive runs (minimum {min_runs} runs).", ""]
    if flaky:
        out += ["| Test | Flip rate | Failures | Timeline (oldest → newest) | Quarantined |",
                "|---|---:|---:|---|:---:|"]
        out += [f"| `{s.test_id}` | {s.flip_rate:.0%} | {s.failures}/{s.runs} | `{s.timeline()}` | "
                f"{'yes' if s.test_id in quarantined else '**no**'} |" for s in flaky]
    else:
        out.append("None found.")
    return "\n".join(out) + "\n", open_items
