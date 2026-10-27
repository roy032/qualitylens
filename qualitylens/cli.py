"""The `qualitylens` command: one entry point for running a suite and for the reports around it.

    qualitylens init [DIR] --url URL        # a ready-to-run suite for your app (see docs/toolkit.md)
    qualitylens doctor                      # can this machine run the suite? what is missing?
    qualitylens run <profile|layer|impacted> [-- extra pytest args] [--record]
    qualitylens impact --base origin/main   # which layers a change can affect
    qualitylens history add results/*.xml   # append a run to the test history
    qualitylens flaky [--strict]            # flaky tests from the history, quarantined or not
    qualitylens quarantine check            # validate quarantine.toml (expiry, owner, test exists)
    qualitylens dashboard                   # HTML trends: failures, time, flaky, failing, slow tests
    qualitylens summary results/*.xml       # Markdown run summary (also: --runs for repeated runs)
    qualitylens load-trend | compat | mutation-score ...   # load, upgrade and mutation reports

Settings come from the nearest qualitylens.toml (or --config); see qualitylens/project.py.
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
from qualitylens import project as project_config
from qualitylens.junit import parse

NO_TESTS_COLLECTED = 5
# Report tools with their own arguments: `qualitylens summary ...` is `python -m qualitylens.summary ...`.
PASSTHROUGH = {
    "summary": ("qualitylens.summary", "Markdown summary of JUnit XML; --runs compares repeated runs"),
    "load-trend": ("qualitylens.load_trend", "Locust results vs the median of recent runs"),
    "compat": ("qualitylens.compat", "the same suite on several app versions: what an upgrade changes"),
    "mutation-score": ("qualitylens.mutation", "mutmut stats -> score and gate"),
}

Runner = Callable[[Sequence[str]], int]


def _subprocess_runner(cmd: Sequence[str]) -> int:
    return subprocess.run(list(cmd), check=False).returncode


def steps_for(project: project_config.Project, profile: str) -> list[list[str]]:
    """The pytest calls of a profile; a layer without a profile runs as `-m "<layer> and not quarantined"`."""
    if profile in project.profiles:
        return project.profiles[profile]
    if profile in project.layers:
        return [["-m", f"{profile} and not {project_config.QUARANTINED}"]]
    known = sorted({*project.profiles, *project.layers, "impacted"})
    raise SystemExit(f"unknown profile {profile!r}; choose from: {', '.join(known)}")


def pytest_commands(project: project_config.Project, profile: str, extra: list[str], junit_dir: Path | None,
                    changed: Callable[[], list[str]] | None = None) -> list[list[str]]:
    if profile == "impacted":
        expr = impact.marker_expression(impact.select(changed() if changed else [], project.impact_rules,
                                                      project.layers))
        if expr == "none":
            return []
        steps = steps_for(project, project.impact_fallback) if expr == impact.ALL else \
            [["-m", f"({expr}) and not {project_config.QUARANTINED} and not serial"]]
    else:
        steps = steps_for(project, profile)
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
    project = args.project
    commands = pytest_commands(project, args.profile, args.pytest_args, junit_dir,
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
        add_run(files, args.history or project.history_path, args.label, project.history_keep)
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
    store = args.history or args.project.history_path
    run = add_run(files, store, args.label, args.keep or args.project.history_keep)
    print(f"Recorded {len(run['results'])} results as {run['label']!r} in {store} "
          f"({len(history.load(store))} runs).")
    return 0


def _quarantined_ids(path: Path) -> set[str]:
    return {e.test_id for e in quarantine.load(path)}


def cmd_flaky(args: argparse.Namespace) -> int:
    project = args.project
    runs = history.load(args.history or project.history_path)
    text, open_items = history.flaky_report(runs, _quarantined_ids(args.quarantine_file or project.quarantine_path),
                                            args.min_runs or project.flaky_min_runs,
                                            project.flaky_threshold if args.threshold is None else args.threshold)
    sys.stdout.write(text)
    return 1 if args.strict and open_items else 0


def cmd_quarantine_check(args: argparse.Namespace) -> int:
    try:
        entries = quarantine.load(args.file or args.project.quarantine_path)
    except quarantine.QuarantineError as exc:
        print(f"✗ {exc}")
        return 1
    today = date.fromisoformat(args.today) if args.today else date.today()
    found = quarantine.problems(entries, today, root=Path(args.root) if args.root else args.project.root)
    for problem in found:
        print(f"✗ {problem}")
    if not found:
        print(f"✓ {args.file or args.project.quarantine_path}: {len(entries)} quarantined test(s), all valid")
    return 1 if found else 0


def cmd_impact(args: argparse.Namespace) -> int:
    project = args.project
    paths = args.paths or impact.changed_files(args.base)
    layers = impact.select(paths, project.impact_rules, project.layers)
    if args.verbose:
        for path in paths:
            found = impact.layers_for(path, project.impact_rules, project.layers)
            print(f"  {path}: {', '.join(sorted(found)) or '-'}", file=sys.stderr)
    print(impact.marker_expression(layers))
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    project = args.project
    store = args.history or project.history_path
    out = args.out or store.parent / "trends.html"
    runs = history.load(store)
    out.parent.mkdir(parents=True, exist_ok=True)
    quarantined = _quarantined_ids(args.quarantine_file or project.quarantine_path)
    out.write_text(dashboard.render(runs, quarantined, title=args.title or f"{project.name} test trends",
                                    min_runs=project.flaky_min_runs, threshold=project.flaky_threshold))
    print(f"Wrote {out} ({len(runs)} runs)")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from qualitylens import doctor

    checks = doctor.run_all(args.project, offline=args.offline)
    print(doctor.render(checks))
    ok = doctor.healthy(checks)
    print("\nReady to run the suite." if ok else "\nFix the ✗ items above, then run: qualitylens doctor")
    return 0 if ok else 1


def cmd_init(args: argparse.Namespace) -> int:
    from qualitylens import scaffold

    target = Path(args.directory)
    written, skipped = scaffold.write(target, scaffold.Options(
        name=args.name or target.resolve().name, base_url=args.url, health_path=args.health,
        api_prefix=args.api_prefix), force=args.force)
    for path in written:
        print(f"  created {path}")
    for path in skipped:
        print(f"  kept    {path} (exists; --force overwrites)")
    print(f"\nNext: cd {target} && qualitylens doctor && qualitylens run smoke   (guide: QUALITYLENS.md)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qualitylens", description="QualityLens: run, track and report on a test suite")
    parser.add_argument("--version", action="version", version=f"qualitylens {__version__}")
    parser.add_argument("--config", type=Path, default=None, help="qualitylens.toml (default: nearest one upwards)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a ready-to-run suite for a web app or API")
    p.add_argument("directory", nargs="?", default=".")
    p.add_argument("--url", required=True, help="base URL of the app, e.g. http://localhost:8000")
    p.add_argument("--name", default=None, help="project name (default: the directory name)")
    p.add_argument("--health", default="/", help="path that answers 2xx when the app is up (default: /)")
    p.add_argument("--api-prefix", default="", help="prefix of the API paths, e.g. /api/v1")
    p.add_argument("--force", action="store_true", help="overwrite files that already exist")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", help="check that this machine can run the suite")
    p.add_argument("--offline", action="store_true", help="skip the checks that need the app and its database")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("run", help="run a test profile")
    p.add_argument("profile", help="a profile from qualitylens.toml (smoke, full, ...), a layer, or impacted")
    p.add_argument("pytest_args", nargs="*", help="extra pytest arguments, after --")
    p.add_argument("--base", default="origin/main", help="impacted: compare with this git ref")
    p.add_argument("--junit-dir", default=None, help="write JUnit XML here (default results/ with --record)")
    p.add_argument("--record", action="store_true", help="append the results to the test history")
    p.add_argument("--history", type=Path, default=None)
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
    p.add_argument("--history", type=Path, default=None)
    p.add_argument("--label", default="local", help="name of the run, e.g. the commit SHA")
    p.add_argument("--keep", type=int, default=None)
    p.set_defaults(func=cmd_history_add)

    p = sub.add_parser("flaky", help="flaky tests in the history")
    p.add_argument("--history", type=Path, default=None)
    p.add_argument("--quarantine-file", type=Path, default=None)
    p.add_argument("--min-runs", type=int, default=None)
    p.add_argument("--threshold", type=float, default=None, help="flip rate, 0 to 1")
    p.add_argument("--strict", action="store_true", help="exit 1 when a flaky test is not quarantined")
    p.set_defaults(func=cmd_flaky)

    quar = sub.add_parser("quarantine", help="flaky-test quarantine").add_subparsers(dest="action", required=True)
    p = quar.add_parser("check", help="validate quarantine.toml")
    p.add_argument("--file", type=Path, default=None)
    p.add_argument("--root", default=None, help="project root, to check that each test exists")
    p.add_argument("--today", default=None, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_quarantine_check)

    p = sub.add_parser("dashboard", help="write the HTML trends dashboard")
    p.add_argument("--history", type=Path, default=None)
    p.add_argument("--quarantine-file", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None, help="default: trends.html next to the history")
    p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_dashboard)

    for name, (_, text) in PASSTHROUGH.items():
        sub.add_parser(name, help=text, add_help=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in PASSTHROUGH:
        import importlib

        return int(importlib.import_module(PASSTHROUGH[argv[0]][0]).main(argv[1:]))
    extra: list[str] = []
    if "--" in argv:  # everything after -- goes to pytest untouched
        cut = argv.index("--")
        argv, extra = argv[:cut], argv[cut + 1:]
    args = build_parser().parse_args(argv)
    try:
        args.project = project_config.load(args.config)
    except project_config.ConfigError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if getattr(args, "command", None) == "run":
        args.pytest_args = [*args.pytest_args, *extra]
        if args.record and not args.junit_dir:
            args.junit_dir = "results"
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
