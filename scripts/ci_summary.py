"""Turn pytest JUnit XML into a Markdown run summary (GitHub job summary, PR comment, or terminal).

    python scripts/ci_summary.py results/*.xml >> "$GITHUB_STEP_SUMMARY"
    python scripts/ci_summary.py --runs runs/run-*.xml

Default: the files are parts of one run (smoke, regression, ...) and are merged into results per
layer (ui, api, db, security, a11y, unit), failures, pinned known bugs and the slowest tests.
--runs: the files are repeated runs of the same suite; the summary also lists tests whose outcome
changed between runs, which is how flaky tests are found without hiding them behind retries, and
the exit code is 1 when there are any.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

OUTCOMES = ("passed", "failed", "known bug", "skipped")


@dataclass(frozen=True)
class Result:
    test_id: str
    layer: str
    outcome: str
    seconds: float
    message: str = ""


def parse(path: Path) -> list[Result]:
    results = []
    for case in ET.parse(path).getroot().iter("testcase"):
        classname = case.get("classname", "")
        parts = classname.split(".")
        layer = parts[1] if len(parts) > 2 and parts[0] == "tests" else "other"
        outcome, message = "passed", ""
        for child in case:
            if child.tag in ("failure", "error"):
                outcome, message = "failed", child.get("message", "")
            elif child.tag == "skipped":
                is_xfail = child.get("type") == "pytest.xfail"
                outcome, message = ("known bug" if is_xfail else "skipped"), child.get("message", "")
        test_id = f"{classname.replace('.', '/')}.py::{case.get('name')}"
        results.append(Result(test_id, layer, outcome, float(case.get("time") or 0), message))
    return results


def layer_table(results: list[Result]) -> list[str]:
    by_layer: dict[str, Counter] = defaultdict(Counter)
    seconds: Counter = Counter()
    for r in results:
        by_layer[r.layer][r.outcome] += 1
        seconds[r.layer] += r.seconds
    lines = ["| Layer | Tests | " + " | ".join(o.capitalize() for o in OUTCOMES) + " | Time |",
             "|---|---:|" + "---:|" * len(OUTCOMES) + "---:|"]
    total: Counter = Counter()
    for layer in sorted(by_layer):
        counts = by_layer[layer]
        total.update(counts)
        lines.append(f"| {layer} | {sum(counts.values())} | "
                     + " | ".join(str(counts[o]) for o in OUTCOMES) + f" | {seconds[layer]:.0f} s |")
    lines.append(f"| **all** | **{sum(total.values())}** | "
                 + " | ".join(f"**{total[o]}**" for o in OUTCOMES) + f" | **{sum(seconds.values()):.0f} s** |")
    return lines


def flaky(runs: list[list[Result]]) -> dict[str, list[str]]:
    """Tests that ran in every run but did not always end the same way."""
    outcomes: dict[str, list[str]] = defaultdict(list)
    for run in runs:
        for r in run:
            outcomes[r.test_id].append(r.outcome)
    return {t: o for t, o in sorted(outcomes.items()) if len(o) == len(runs) and len(set(o)) > 1}


def summarize(runs: list[list[Result]], slowest: int = 5) -> str:
    latest = runs[-1]
    failed = [r for r in latest if r.outcome == "failed"]
    known = [r for r in latest if r.outcome == "known bug"]
    status = "❌ failures" if failed else "✅ green"
    out = [f"## QualityLens test run: {status}", ""]
    if len(runs) > 1:
        out += [f"Combined view of {len(runs)} runs; the table shows the last one.", ""]
    out += layer_table(latest) + [""]
    if failed:
        out += ["### Failures", ""] + [f"- `{r.test_id}`: {r.message[:200]}" for r in failed] + [""]
    if len(runs) > 1:
        unstable = flaky(runs)
        out += [f"### Flaky tests ({len(unstable)})", ""]
        out += [f"- `{t}`: {' → '.join(o)}" for t, o in unstable.items()] or ["None: every test gave the same result in every run."]
        out += [""]
    if known:
        bugs = sorted({r.message.split(":", 1)[0] for r in known if r.message.startswith("BUG-")})
        out += [f"### Known bugs still reproducing ({len(bugs)})", "", ", ".join(bugs) or "-", ""]
    out += [f"### Slowest {slowest}", ""]
    out += [f"- {r.seconds:.1f} s `{r.test_id}`" for r in sorted(latest, key=lambda r: -r.seconds)[:slowest]]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    repeated = "--runs" in argv
    paths = sorted(Path(p) for p in argv if p != "--runs" and Path(p).is_file())
    if not paths:
        print("No JUnit XML found; nothing to summarise.")
        return 0
    parts = [parse(p) for p in paths]
    runs = parts if repeated else [[r for part in parts for r in part]]
    sys.stdout.write(summarize(runs))
    return 1 if repeated and flaky(runs) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
