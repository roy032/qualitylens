"""The `qualitylens` command: one entry point for running the suite and for the reports around it.

    qualitylens doctor                      # can this machine run the suite? what is missing?
    qualitylens run smoke|fast|full|impacted|<layer> [-- extra pytest args] [--record]
    qualitylens impact --base origin/main   # which layers a change can affect
    qualitylens history add results/*.xml   # append a run to the test history
    qualitylens flaky [--strict]            # flaky tests from the history, quarantined or not
    qualitylens quarantine check            # validate quarantine.toml (expiry, owner, test exists)
    qualitylens dashboard --out trends.html # HTML trends: outcomes, time, flaky, failing, slow tests

Also available as `python -m qualitylens`.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from qualitylens import __version__, dashboard, history, impact, quarantine
from qualitylens.junit import parse

DEFAULT_HISTORY = Path("test-history/history.json")
E2E = "(ui or api or db or security or a11y)"

# Each profile is one or more pytest invocations, run in order. Mirrors the Makefile and CI.
PROFILES: dict[str, list[list[str]]] = {
    "smoke": [["-m", "smoke", "-n", "auto"]],
    "fast": [["-m", f"{E2E} and not serial and not visual and not quarantined", "-n", "auto"],
             ["-m", "serial and not quarantined"]],
    "full": [["-m", "not serial and not visual and not quarantined"], ["-m", "serial and not quarantined"]],
    "quarantined": [["-m", "quarantined"]],
    **{layer: [["-m", f"{layer} and not quarantined"]]
       for layer in ("unit", "ui", "api", "db", "security", "a11y", "property")},
}
NO_TESTS_COLLECTED = 5

Runner = Callable[[Sequence[str]], int]


def _subprocess_runner(cmd: Sequence[str]) -> int:
    return subprocess.run(list(cmd), check=False).returncode


def pytest_commands(profile: str, extra: list[str], junit_dir: Path | None,
                    changed: Callable[[], list[str]] | None = None) -> list[list[str]]:
    if profile == "impacted":
        expr = impact.marker_expression(impact.select(changed() if changed else []))
        if expr == "none":
            return []
        steps = PROFILES["fast"] if expr == impact.ALL else [["-m", f"({expr}) and not quarantined and not serial"]]
    else:
        steps = PROFILES[profile]
    commands = []
    for i, step in enumerate(steps):
        cmd = [sys.executable, "-m", "pytest", *step, *extra]
        if junit_dir is not None:
            cmd.append(f"--junitxml={junit_dir / f'{profile}-{i + 1}.xml'}")
        commands.append(cmd)
    return commands


def cmd_run(args: argparse.Namespace, runner: Runner | None = None) -> int:
    runner = runner or _subprocess_runner
    junit_dir = Path(args.junit_dir) if (args.record or args.junit_dir) else None
    commands = pytest_commands(args.profile, args.pytest_args, junit_dir,
                               changed=lambda: impact.changed_files(args.base))
    if not commands:
        print("Nothing to run: the changes only touch documentation.")
        return 0
    worst = 0
    for cmd in commands:
        print("$ " + " ".join(cmd), flush=True)
        code = runner(cmd)
        if code != NO_TESTS_COLLECTED:
            worst = max(worst, code)
    if args.record and junit_dir is not None:
        files = sorted(junit_dir.glob(f"{args.profile}-*.xml"))
        add_run(files, args.history, args.label, history.DEFAULT_KEEP)
    return worst


def add_run(files: list[Path], store: Path, label: str, keep: int) -> dict:
    results = [r for f in files if f.is_file() for r in parse(f)]
    run = history.make_run(results, label)
    history.save(store, history.load(store) + [run], keep)
    return run


def cmd_history_add(args: argparse.Namespace) -> int:
    files = [Path(p) for p in args.junit]
    if not any(f.is_file() for f in files):
        print("No JUnit XML found; nothing recorded.")
        return 0
    run = add_run(files, args.history, args.label, args.keep)
    print(f"Recorded {len(run['results'])} results as {run['label']!r} in {args.history} "
          f"({len(history.load(args.history))} runs).")
    return 0


def _quarantined_ids(path: Path) -> set[str]:
    return {e.test_id for e in quarantine.load(path)}


def cmd_flaky(args: argparse.Namespace) -> int:
    runs = history.load(args.history)
    text, open_items = history.flaky_report(runs, _quarantined_ids(args.quarantine_file), args.min_runs,
                                            args.threshold)
    sys.stdout.write(text)
    return 1 if args.strict and open_items else 0


def cmd_quarantine_check(args: argparse.Namespace) -> int:
    try:
        entries = quarantine.load(args.file)
    except quarantine.QuarantineError as exc:
        print(f"✗ {exc}")
        return 1
    today = date.fromisoformat(args.today) if args.today else date.today()
    found = quarantine.problems(entries, today, root=Path(args.root))
    for problem in found:
        print(f"✗ {problem}")
    if not found:
        print(f"✓ {args.file}: {len(entries)} quarantined test(s), all valid")
    return 1 if found else 0


def cmd_impact(args: argparse.Namespace) -> int:
    paths = args.paths or impact.changed_files(args.base)
    layers = impact.select(paths)
    if args.verbose:
        for path in paths:
            print(f"  {path}: {', '.join(sorted(impact.layers_for(path))) or '-'}", file=sys.stderr)
    print(impact.marker_expression(layers))
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    runs = history.load(args.history)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dashboard.render(runs, _quarantined_ids(args.quarantine_file), title=args.title))
    print(f"Wrote {args.out} ({len(runs)} runs)")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from qualitylens import doctor
    from qualitylens.config import settings

    checks = doctor.run_all(settings, offline=args.offline)
    print(doctor.render(checks))
    ok = doctor.healthy(checks)
    print("\nReady to run the suite." if ok else "\nFix the ✗ items above, then run: qualitylens doctor")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qualitylens", description="QualityLens test suite and reports")
    parser.add_argument("--version", action="version", version=f"qualitylens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check that this machine can run the suite")
    p.add_argument("--offline", action="store_true", help="skip the checks that need Gitea and PostgreSQL")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("run", help="run a test profile")
    p.add_argument("profile", choices=[*PROFILES, "impacted"])
    p.add_argument("pytest_args", nargs="*", help="extra pytest arguments, after --")
    p.add_argument("--base", default="origin/main", help="impacted: compare with this git ref")
    p.add_argument("--junit-dir", default=None, help="write JUnit XML here (default results/ with --record)")
    p.add_argument("--record", action="store_true", help="append the results to the test history")
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--label", default="local")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("impact", help="pytest marker expression for the layers a change can affect")
    p.add_argument("paths", nargs="*", help="changed files (default: git diff against --base)")
    p.add_argument("--base", default="origin/main")
    p.add_argument("-v", "--verbose", action="store_true", help="show the layers of each file on stderr")
    p.set_defaults(func=cmd_impact)

    hist = sub.add_parser("history", help="test-result history").add_subparsers(dest="action", required=True)
    p = hist.add_parser("add", help="append a run (one or more JUnit XML files) to the history")
    p.add_argument("junit", nargs="+")
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--label", default="local", help="name of the run, e.g. the commit SHA")
    p.add_argument("--keep", type=int, default=history.DEFAULT_KEEP)
    p.set_defaults(func=cmd_history_add)

    p = sub.add_parser("flaky", help="flaky tests in the history")
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--quarantine-file", type=Path, default=quarantine.DEFAULT_PATH)
    p.add_argument("--min-runs", type=int, default=history.DEFAULT_MIN_RUNS)
    p.add_argument("--threshold", type=float, default=history.DEFAULT_THRESHOLD, help="flip rate, 0 to 1")
    p.add_argument("--strict", action="store_true", help="exit 1 when a flaky test is not quarantined")
    p.set_defaults(func=cmd_flaky)

    quar = sub.add_parser("quarantine", help="flaky-test quarantine").add_subparsers(dest="action", required=True)
    p = quar.add_parser("check", help="validate quarantine.toml")
    p.add_argument("--file", type=Path, default=quarantine.DEFAULT_PATH)
    p.add_argument("--root", default=".", help="repository root, to check that each test exists")
    p.add_argument("--today", default=None, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_quarantine_check)

    p = sub.add_parser("dashboard", help="write the HTML trends dashboard")
    p.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    p.add_argument("--quarantine-file", type=Path, default=quarantine.DEFAULT_PATH)
    p.add_argument("--out", type=Path, default=Path("test-history/trends.html"))
    p.add_argument("--title", default="QualityLens test trends")
    p.set_defaults(func=cmd_dashboard)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra: list[str] = []
    if "--" in argv:  # everything after -- goes to pytest untouched
        cut = argv.index("--")
        argv, extra = argv[:cut], argv[cut + 1:]
    args = build_parser().parse_args(argv)
    if getattr(args, "command", None) == "run":
        args.pytest_args = [*args.pytest_args, *extra]
        if args.record and not args.junit_dir:
            args.junit_dir = "results"
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
