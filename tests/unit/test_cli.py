"""The qualitylens command line: profiles, history, flaky report, quarantine check, impact and dashboard."""
import json
import sys
from pathlib import Path

import pytest

from qualitylens import cli, history

pytestmark = pytest.mark.unit

JUNIT = ('<?xml version="1.0"?><testsuites><testsuite name="pytest">'
         '<testcase classname="tests.api.test_x" name="test_ok" time="1.5"/>{extra}'
         '</testsuite></testsuites>')
FAIL = '<testcase classname="tests.api.test_x" name="test_flaky" time="2"><failure message="boom"/></testcase>'
PASS = '<testcase classname="tests.api.test_x" name="test_flaky" time="2"/>'


def junit(path: Path, extra: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(JUNIT.format(extra=extra))
    return path


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"qualitylens {cli.__version__}"


def test_a_command_is_required(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


@pytest.mark.parametrize("profile, expected", [
    ("smoke", [["-m", "smoke", "-n", "auto"]]),
    ("fast", [["-m", "(ui or api or db or security or a11y) and not serial and not visual and not quarantined",
               "-n", "auto"], ["-m", "serial and not quarantined"]]),
    ("full", [["-m", "not serial and not visual and not quarantined"], ["-m", "serial and not quarantined"]]),
    ("quarantined", [["-m", "quarantined"]]),
    ("ui", [["-m", "ui and not quarantined"]]),
    ("property", [["-m", "property and not quarantined"]]),
])
def test_profiles(profile, expected):
    commands = cli.pytest_commands(profile, ["-q"], None)
    assert commands == [[sys.executable, "-m", "pytest", *step, "-q"] for step in expected]


def test_profiles_write_one_junit_file_per_step(tmp_path):
    commands = cli.pytest_commands("fast", [], tmp_path)
    assert [c[-1] for c in commands] == [f"--junitxml={tmp_path / 'fast-1.xml'}", f"--junitxml={tmp_path / 'fast-2.xml'}"]


def test_impacted_profile_runs_only_the_affected_layers():
    commands = cli.pytest_commands("impacted", [], None, changed=lambda: ["pages/login_page.py", "tests/db/x.py"])
    assert commands == [[sys.executable, "-m", "pytest", "-m",
                         "(a11y or db or security or ui or visual) and not quarantined and not serial"]]


def test_impacted_profile_falls_back_to_fast_for_shared_code():
    assert cli.pytest_commands("impacted", [], None, changed=lambda: ["tests/conftest.py"]) == \
        cli.pytest_commands("fast", [], None)


def test_impacted_profile_with_docs_only_runs_nothing():
    assert cli.pytest_commands("impacted", [], None, changed=lambda: ["README.md"]) == []
    assert cli.pytest_commands("impacted", [], None) == []


def test_run_passes_extra_args_and_returns_the_worst_exit_code(capsys, monkeypatch):
    seen = []
    codes = iter([1, 0])
    monkeypatch.setattr(cli, "_subprocess_runner", lambda cmd: seen.append(cmd) or next(codes))
    args = cli.build_parser().parse_args(["run", "fast"])
    args.pytest_args = ["-x"]
    assert cli.cmd_run(args, runner=cli._subprocess_runner) == 1
    assert [c[-1] for c in seen] == ["-x", "-x"]
    assert capsys.readouterr().out.startswith("$ ")


def test_no_tests_collected_is_not_a_failure():
    args = cli.build_parser().parse_args(["run", "quarantined"])
    assert cli.cmd_run(args, runner=lambda cmd: cli.NO_TESTS_COLLECTED) == 0
    assert cli.NO_TESTS_COLLECTED == 5


def test_run_with_nothing_to_do(capsys, monkeypatch):
    monkeypatch.setattr(cli.impact, "changed_files", lambda base: ["docs/x.md"])
    assert cli.main(["run", "impacted"]) == 0
    assert "only touch documentation" in capsys.readouterr().out


def test_run_record_appends_to_history(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    def fake_pytest(cmd):
        junit(Path(cmd[-1].split("=", 1)[1]))
        return 0

    monkeypatch.setattr(cli, "_subprocess_runner", fake_pytest)
    assert cli.main(["run", "smoke", "--record", "--label", "abc", "--", "-q"]) == 0
    runs = history.load(tmp_path / "test-history/history.json")
    assert [r["label"] for r in runs] == ["abc"]
    assert runs[0]["results"] == {"tests/api/test_x.py::test_ok": ["passed", 1.5]}
    assert (tmp_path / "results/smoke-1.xml").is_file()


def test_main_uses_the_real_runner_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.subprocess, "run",
                        lambda cmd, check: calls.append(cmd) or cli.subprocess.CompletedProcess(cmd, 3))
    assert cli.main(["run", "unit", "--", "-q"]) == 3
    assert calls == [[sys.executable, "-m", "pytest", "-m", "unit and not quarantined", "-q"]]


def test_history_add(tmp_path, capsys):
    store = tmp_path / "h.json"
    files = [str(junit(tmp_path / "a.xml")), str(junit(tmp_path / "b.xml", FAIL)), str(tmp_path / "missing.xml")]
    assert cli.main(["history", "add", *files, "--history", str(store), "--label", "r1"]) == 0
    assert cli.main(["history", "add", files[0], "--history", str(store), "--label", "r2", "--keep", "1"]) == 0
    out = capsys.readouterr().out
    assert f"Recorded 2 results as 'r1' in {store} (1 runs)." in out
    assert f"Recorded 1 results as 'r2' in {store} (1 runs)." in out


def test_history_add_without_files(tmp_path, capsys):
    store = tmp_path / "h.json"
    assert cli.main(["history", "add", str(tmp_path / "none.xml"), "--history", str(store)]) == 0
    assert "nothing recorded" in capsys.readouterr().out
    assert not store.exists()


def flaky_store(tmp_path):
    store = tmp_path / "h.json"
    for i in range(10):
        f = junit(tmp_path / f"r{i}.xml", PASS if i % 2 else FAIL)
        cli.main(["history", "add", str(f), "--history", str(store), "--label", f"r{i}"])
    return store


def test_flaky_report_and_strict_gate(tmp_path, capsys):
    store = flaky_store(tmp_path)
    capsys.readouterr()
    none = tmp_path / "none.toml"
    assert cli.main(["flaky", "--history", str(store), "--quarantine-file", str(none)]) == 0
    assert "| `tests/api/test_x.py::test_flaky` | 100% | 5/10 |" in capsys.readouterr().out
    assert cli.main(["flaky", "--history", str(store), "--quarantine-file", str(none), "--strict"]) == 1
    assert cli.main(["flaky", "--history", str(store), "--quarantine-file", str(none), "--strict",
                     "--min-runs", "11"]) == 0
    assert cli.main(["flaky", "--history", str(store), "--quarantine-file", str(none), "--strict",
                     "--threshold", "1.01"]) == 0


def test_flaky_strict_passes_when_quarantined(tmp_path):
    store = flaky_store(tmp_path)
    q = tmp_path / "q.toml"
    q.write_text('[[test]]\nid = "tests/api/test_x.py::test_flaky"\nreason = "r"\nowner = "o"\nexpires = 2026-11-01\n')
    assert cli.main(["flaky", "--history", str(store), "--quarantine-file", str(q), "--strict"]) == 0


QUARANTINE = '[[test]]\nid = "tests/unit/test_cli.py::test_version"\nreason = "r"\nowner = "o"\nexpires = {d}\n'


def test_quarantine_check_ok(tmp_path, capsys):
    q = tmp_path / "q.toml"
    q.write_text(QUARANTINE.format(d="2026-11-01"))
    root = str(Path(__file__).parents[2])
    assert cli.main(["quarantine", "check", "--file", str(q), "--root", root, "--today", "2026-10-22"]) == 0
    assert capsys.readouterr().out == f"✓ {q}: 1 quarantined test(s), all valid\n"


def test_quarantine_check_expired(tmp_path, capsys):
    q = tmp_path / "q.toml"
    q.write_text(QUARANTINE.format(d="2026-10-01"))
    root = str(Path(__file__).parents[2])
    assert cli.main(["quarantine", "check", "--file", str(q), "--root", root, "--today", "2026-10-22"]) == 1
    assert capsys.readouterr().out.startswith("✗ tests/unit/test_cli.py::test_version: quarantine expired")


def test_quarantine_check_invalid_file(tmp_path, capsys):
    q = tmp_path / "q.toml"
    q.write_text("[[test]]\nid = 1\n")
    assert cli.main(["quarantine", "check", "--file", str(q)]) == 1
    assert "is missing reason, owner, expires" in capsys.readouterr().out


def test_quarantine_check_defaults_to_today(tmp_path, capsys):
    assert cli.main(["quarantine", "check", "--file", str(tmp_path / "none.toml")]) == 0


def test_impact_with_paths(capsys):
    assert cli.main(["impact", "-v", "pages/login_page.py", "README.md"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "a11y or security or ui or visual\n"
    assert "  README.md: -\n" in captured.err
    assert "  pages/login_page.py: a11y, security, ui, visual\n" in captured.err


def test_impact_from_git(monkeypatch, capsys):
    monkeypatch.setattr(cli.impact, "changed_files", lambda base: ["tests/db/x.py"] if base == "dev" else [])
    assert cli.main(["impact", "--base", "dev"]) == 0
    assert capsys.readouterr().out == "db\n"


def test_dashboard(tmp_path, capsys):
    store = flaky_store(tmp_path)
    out = tmp_path / "site" / "trends.html"
    assert cli.main(["dashboard", "--history", str(store), "--out", str(out), "--title", "My trends",
                     "--quarantine-file", str(tmp_path / "none.toml")]) == 0
    html = out.read_text()
    assert "<title>My trends</title>" in html and "Flaky tests (1)" in html
    assert f"Wrote {out} (10 runs)" in capsys.readouterr().out


def test_doctor(monkeypatch, capsys):
    from qualitylens import doctor

    monkeypatch.setattr(doctor, "run_all", lambda settings, offline: [doctor.Check("Python", offline, "x")])
    assert cli.main(["doctor", "--offline"]) == 0
    assert "Ready to run the suite." in capsys.readouterr().out
    assert cli.main(["doctor"]) == 1
    assert "Fix the ✗ items above" in capsys.readouterr().out


def test_module_entry_point():
    import subprocess

    out = subprocess.run([sys.executable, "-m", "qualitylens", "impact", "README.md"], capture_output=True,
                         text=True, cwd=Path(__file__).parents[2], check=True).stdout
    assert out == "none\n"


def test_default_history_path():
    assert Path("test-history/history.json") == cli.DEFAULT_HISTORY
    assert json.loads("[]") == []
