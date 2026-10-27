"""Compare the same suite run against several Gitea versions: an upgrade-readiness report.

    qualitylens compat 1.22.6=results-1.22.6 28.2.0=results-28.2.0 > compat.md

Each argument is VERSION=PATH, where PATH is a JUnit XML file or a folder of them (one run per
version). The report lists, per version, the totals per outcome and which known bugs still
reproduce, then every test whose outcome is not the same on all versions. A strict xfail that
starts passing shows up as "failed" with an XPASS message: that is a bug fixed upstream.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from qualitylens.junit import OUTCOMES, Result, parse

BUG_ID = re.compile(r"BUG-\d+")


def load(spec: str) -> tuple[str, dict[str, Result]]:
    version, _, path = spec.partition("=")
    if not path:
        raise SystemExit(f"expected VERSION=PATH, got {spec!r}")
    root = Path(path)
    files = sorted(root.glob("*.xml")) if root.is_dir() else [root]
    return version, {r.test_id: r for f in files if f.is_file() for r in parse(f)}


def bug_status(results: dict[str, Result]) -> dict[str, str]:
    """BUG-xxx -> 'reproduces' (xfail held) or 'fixed?' (the strict xfail passed unexpectedly)."""
    status: dict[str, str] = {}
    for r in results.values():
        bug = BUG_ID.search(r.message)
        if not bug:
            continue
        if r.outcome == "known bug":
            status.setdefault(bug.group(), "reproduces")
        elif r.outcome == "failed" and "XPASS" in r.message:
            status[bug.group()] = "fixed?"
    return status


def label(r: Result | None) -> str:
    if r is None:
        return "not run"
    if r.outcome == "failed" and "XPASS" in r.message:
        return "bug fixed (XPASS)"
    return r.outcome


def report(runs: list[tuple[str, dict[str, Result]]]) -> str:
    versions = [v for v, _ in runs]
    out = ["## Gitea compatibility", "",
           "| Gitea | Tests | " + " | ".join(o.capitalize() for o in OUTCOMES) + " |",
           "|---|---:|" + "---:|" * len(OUTCOMES)]
    for version, results in runs:
        counts = [sum(r.outcome == o for r in results.values()) for o in OUTCOMES]
        out.append(f"| {version} | {len(results)} | " + " | ".join(map(str, counts)) + " |")

    bugs = [bug_status(results) for _, results in runs]
    all_bugs = sorted(set().union(*bugs), key=lambda b: int(b.split("-")[1]))
    if all_bugs:
        out += ["", "### Known bugs", "", "| Bug | " + " | ".join(versions) + " |",
                "|---|" + "---|" * len(versions)]
        out += [f"| {b} | " + " | ".join(s.get(b, "not run") for s in bugs) + " |" for b in all_bugs]

    every_test = sorted(set().union(*(results for _, results in runs)))
    differ = [t for t in every_test if len({label(results.get(t)) for _, results in runs}) > 1]
    out += ["", f"### Tests with a different result across versions ({len(differ)})", ""]
    if differ:
        out += ["| Test | " + " | ".join(versions) + " |", "|---|" + "---|" * len(versions)]
        out += [f"| `{t}` | " + " | ".join(label(results.get(t)) for _, results in runs) + " |" for t in differ]
    else:
        out.append("None: every test behaves the same on every version.")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    sys.stdout.write(report([load(a) for a in argv]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
