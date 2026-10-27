"""Mutation score from mutmut's stats file, as Markdown; exit code 1 when it is below the minimum.

    mutmut run && mutmut export-cicd-stats
    qualitylens mutation-score mutants/mutmut-cicd-stats.json --min 90 >> "$GITHUB_STEP_SUMMARY"

Score = killed / (killed + survived + no tests + timeout). A mutant that times out is counted as
not killed, so a slow test suite cannot inflate the score.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def score(stats: dict) -> float:
    judged = stats["killed"] + stats["survived"] + stats["no_tests"] + stats["timeout"]
    return 100.0 * stats["killed"] / judged if judged else 0.0


def report(stats: dict, minimum: float) -> str:
    value = score(stats)
    verdict = "✅" if value >= minimum else "❌"
    return "\n".join([
        f"## Mutation testing: {verdict} {value:.1f} % (minimum {minimum:.0f} %)", "",
        "| Mutants | Killed | Survived | No tests | Timeout |", "|---:|---:|---:|---:|---:|",
        f"| {stats['total']} | {stats['killed']} | {stats['survived']} | {stats['no_tests']} | {stats['timeout']} |",
        "",
        "A surviving mutant is a small change to the code that no unit test noticed. "
        "List them with `mutmut results` and inspect one with `mutmut show <name>`.", "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stats", type=Path)
    parser.add_argument("--min", type=float, default=90.0, dest="minimum")
    args = parser.parse_args(argv)
    stats = json.loads(args.stats.read_text())
    sys.stdout.write(report(stats, args.minimum))
    return 0 if score(stats) >= args.minimum else 1


if __name__ == "__main__":
    sys.exit(main())
