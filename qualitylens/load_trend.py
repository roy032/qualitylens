"""Track load-test results across runs and flag a slowdown relative to recent history.

    qualitylens load-trend load/results/run_stats.csv --history load/history/history.json \
           --label "$GITHUB_SHA" [--max-regression 50] [--keep 30] >> "$GITHUB_STEP_SUMMARY"

The fixed SLO in load/locustfile.py (p95 under 1200 ms in CI) only catches a large slowdown, because
shared runners are noisy. This compares each run with the median of the previous runs instead, per
endpoint, so a gradual creep shows up in the table long before it breaks the SLO.

The current run is appended to the history file (newest last, at most --keep runs). The exit code is 1
when the overall p95 is more than --max-regression percent above the median of the previous runs;
with fewer than MIN_HISTORY previous runs there is no gate yet, only the table.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

TOTAL = "Aggregated"
MIN_HISTORY = 3
BARS = "▁▂▃▄▅▆▇█"


def read_stats(path: Path) -> dict[str, dict[str, float]]:
    """Locust's run_stats.csv -> {endpoint: {"requests", "failures", "median", "p95"}}."""
    stats = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            stats[row["Name"]] = {"requests": int(row["Request Count"]), "failures": int(row["Failure Count"]),
                                  "median": float(row["Median Response Time"]), "p95": float(row["95%"])}
    return stats


def load_history(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def baseline(history: list[dict], endpoint: str) -> float | None:
    """Median p95 of an endpoint over the previous runs that measured it."""
    values = [run["stats"][endpoint]["p95"] for run in history if endpoint in run.get("stats", {})]
    return statistics.median(values) if values else None


def change(current: float, base: float | None) -> str:
    if not base:
        return "-"
    pct = (current - base) / base * 100
    return f"{pct:+.0f} %"


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    low, high = min(values), max(values)
    span = high - low
    if span == 0:
        return BARS[0] * len(values)
    return "".join(BARS[round((v - low) / span * (len(BARS) - 1))] for v in values)


def regressed(current: float, base: float | None, history_size: int, max_regression: float) -> bool:
    if base is None or history_size < MIN_HISTORY:
        return False
    return current > base * (1 + max_regression / 100)


def report(stats: dict, history: list[dict], label: str, max_regression: float) -> tuple[str, bool]:
    total = stats[TOTAL]["p95"]
    base = baseline(history, TOTAL)
    failed = regressed(total, base, len(history), max_regression)
    if len(history) < MIN_HISTORY:
        verdict = f"⏳ collecting history ({len(history)} of {MIN_HISTORY} previous runs)"
    elif failed:
        verdict = f"❌ p95 {total:.0f} ms is more than {max_regression:.0f} % above the recent median ({base:.0f} ms)"
    else:
        verdict = f"✅ p95 {total:.0f} ms, within {max_regression:.0f} % of the recent median ({base:.0f} ms)"
    out = [f"## Load trend: {verdict}", "",
           f"Run `{label}` compared with the median of the previous {len(history)} run(s).", "",
           "| Endpoint | Requests | Failures | p95 | Recent median p95 | Change |",
           "|---|---:|---:|---:|---:|---:|"]
    for name in sorted(stats, key=lambda n: (n == TOTAL, n)):
        s = stats[name]
        b = baseline(history, name)
        shown = f"**{name}**" if name == TOTAL else name
        out.append(f"| {shown} | {s['requests']} | {s['failures']} | {s['p95']:.0f} ms | "
                   f"{f'{b:.0f} ms' if b is not None else '-'} | {change(s['p95'], b)} |")
    trend = [run["stats"][TOTAL]["p95"] for run in history if TOTAL in run.get("stats", {})] + [total]
    out += ["", f"Overall p95, oldest to newest ({len(trend)} runs): `{sparkline(trend)}` "
                f"{' → '.join(f'{v:.0f}' for v in trend[-5:])} ms"]
    return "\n".join(out) + "\n", failed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stats", type=Path, help="Locust run_stats.csv")
    parser.add_argument("--history", type=Path, required=True, help="JSON file with previous runs (created if missing)")
    parser.add_argument("--label", default="local", help="name of this run, e.g. the commit SHA")
    parser.add_argument("--max-regression", type=float, default=50, help="allowed p95 increase in percent")
    parser.add_argument("--keep", type=int, default=30, help="runs to keep in the history file")
    args = parser.parse_args(argv)

    stats = read_stats(args.stats)
    if TOTAL not in stats:
        print(f"No '{TOTAL}' row in {args.stats}; nothing to compare.")
        return 0
    history = load_history(args.history)
    text, failed = report(stats, history, args.label, args.max_regression)
    sys.stdout.write(text)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps((history + [{"label": args.label, "stats": stats}])[-args.keep:], indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
