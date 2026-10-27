"""`qualitylens doctor` checks and the HTML trends dashboard."""
import re

import pytest

from qualitylens import dashboard, doctor
from qualitylens.project import Login, Project

pytestmark = pytest.mark.unit
PROJECT = Project(name="Shop", base_url="http://app:3000", health_path="/health", start_hint="make up",
                  login=Login("/api/me", "qa", "pw"), database_dsn="postgresql://u:p@db:5432/shop",
                  packages=("pytest", "locust"), browser=True)
BARE = Project(name="Plain")


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._body


def boom(*args, **kwargs):
    raise ConnectionError("refused")


def test_python_version():
    assert doctor.check_python((3, 12)) == doctor.Check("Python", True, "3.12")
    assert doctor.check_python((3, 11)) == doctor.Check("Python", False, "3.11, needs 3.12+")


def test_packages():
    assert doctor.check_packages(("pytest",), lambda name: object()).ok
    check = doctor.check_packages(("pytest", "requests", "locust"),
                                  lambda name: None if name in ("locust", "pytest") else object())
    assert check == doctor.Check("Python packages", False,
                                 "missing pytest, locust: pip install -r requirements.txt")


def test_docker_is_optional():
    assert doctor.check_docker(lambda name: "/usr/bin/docker") == doctor.Check("Docker", True, "/usr/bin/docker", False)
    missing = doctor.check_docker(lambda name: None)
    assert not missing.ok and not missing.required


def test_browser(tmp_path):
    exe = tmp_path / "chrome"
    exe.write_text("")
    assert doctor.check_browser(lambda: str(exe)) == doctor.Check("Chromium (Playwright)", True, str(exe))
    assert doctor.check_browser(lambda: str(tmp_path / "gone")).detail == \
        "not installed: python -m playwright install chromium"
    assert doctor.check_browser(lambda: "").ok is False
    failed = doctor.check_browser(boom)
    assert failed == doctor.Check("Chromium (Playwright)", False,
                                  "ConnectionError: python -m playwright install chromium")


def test_app():
    calls = []

    def get(url, **kw):
        calls.append((url, kw))
        return FakeResponse(204)

    assert doctor.check_app(PROJECT, get) == doctor.Check("Shop (app)", True, "http://app:3000/health answers 204")
    assert calls == [("http://app:3000/health", {"timeout": 5})]
    down = doctor.check_app(PROJECT, boom)
    assert down == doctor.Check("Shop (app)", False,
                                "not reachable at http://app:3000/health (ConnectionError): make up")
    assert not doctor.check_app(PROJECT, lambda url, **kw: FakeResponse(500)).ok


def test_login():
    calls = []

    def get(url, **kw):
        calls.append((url, kw))
        return FakeResponse(200)

    assert doctor.check_login(PROJECT, get) == doctor.Check("Login", True, "qa")
    assert calls == [("http://app:3000/api/me", {"auth": ("qa", "pw"), "timeout": 5})]
    assert doctor.check_login(PROJECT, lambda url, **kw: FakeResponse(401)) == doctor.Check(
        "Login", False, "HTTP 401 for qa: wrong credentials, or the user does not exist")
    assert doctor.check_login(PROJECT, boom) == doctor.Check("Login", False, "ConnectionError: is the app running?")


def test_login_without_user():
    nobody = Project(login=Login("/api/me", "", ""))
    check = doctor.check_login(nobody, boom)
    assert not check.ok and "user_env" in check.detail


def test_db():
    closed = []

    class Conn:
        def close(self):
            closed.append(True)

    calls = []

    def connect(dsn, **kw):
        calls.append((dsn, kw))
        return Conn()

    assert doctor.check_db(PROJECT, connect) == doctor.Check("Database", True, "db:5432/shop", False)
    assert calls == [("postgresql://u:p@db:5432/shop", {"connect_timeout": 5})] and closed == [True]
    down = doctor.check_db(PROJECT, boom)
    assert down == doctor.Check("Database", False, "ConnectionError: is the database up?", False)


def test_render_and_health():
    checks = [doctor.Check("A", True, "fine"), doctor.Check("B", False, "broken"),
              doctor.Check("C", False, "optional", required=False)]
    assert doctor.render(checks) == (f" ✓ {'A':<22} fine\n ✗ {'B':<22} broken\n ! {'C':<22} optional")
    assert not doctor.healthy(checks)
    assert doctor.healthy(checks[::2])


def test_run_all_offline_skips_network_checks():
    names = [c.name for c in doctor.run_all(PROJECT, offline=True)]
    assert names == ["Python", "Python packages", "Docker", "Chromium (Playwright)"]


def test_run_all_checks_only_what_is_configured(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "get", boom)
    assert [c.name for c in doctor.run_all(BARE)] == ["Python", "Python packages", "Docker"]


def test_run_all_online_adds_app_checks(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "get", boom)
    names = [c.name for c in doctor.run_all(PROJECT)]
    assert names[-3:] == ["Shop (app)", "Login", "Database"]


# --- dashboard ------------------------------------------------------------
def run(label, **outcomes):
    return {"label": label, "time": "2026-10-22T10:00:00+00:00",
            "results": {f"tests/api/test_x.py::{k}": [v, 2.0] for k, v in outcomes.items()}}


def test_empty_dashboard():
    html = dashboard.render([], set())
    assert html.startswith("<!doctype html>") and "No runs recorded yet" in html


def test_dashboard_sections_and_numbers():
    runs = [run(f"r{i}", a="passed" if i % 2 else "failed", b="known bug", c="passed", d="skipped")
            for i in range(10)] + [run("<latest>", a="passed", b="known bug", c="failed")]
    html = dashboard.render(runs, {"tests/api/test_x.py::a"}, title="T & T")
    assert "<title>T &amp; T</title>" in html
    assert "<code>&lt;latest&gt;</code>" in html  # labels are escaped
    assert "<b>66.7%</b><span>as expected, latest run</span>" in html
    assert "<b>3</b><span>tests executed</span>" in html
    assert "<b>1</b><span>flaky tests</span>" in html
    assert "<b>1</b><span>failing now</span>" in html
    assert "<b>11</b><span>runs in history</span>" in html
    assert "Flaky tests (1)" in html and "<td>yes</td>" in html
    assert "Failing in the latest run (1)" in html
    assert html.count('class="hit"') == 11
    assert html.count("<circle") == 11
    assert 'aria-label="Unexpected failures per run"' in html


def test_failure_bars_count_failures_and_every_run_has_a_tooltip():
    svg = dashboard.failure_bars([run("r1", a="passed", b="failed", c="failed"), run("r2", a="passed")])
    assert "<title>r1 (2026-10-22T10:00:00+00:00): 2 failed, 33.3% as expected</title>" in svg
    assert "<title>r2 (2026-10-22T10:00:00+00:00): 0 failed, 100.0% as expected</title>" in svg
    plot = dashboard.H - dashboard.PAD_B - dashboard.PAD_T
    bars = re.findall(r'<rect x="[\d.]+" y="([\d.]+)" width="[\d.]+" height="([\d.]+)" rx="2"', svg)
    assert [(float(y), float(h)) for y, h in bars] == [(dashboard.PAD_T, plot)]
    assert svg.count('class="hit"') == 2
    assert [t for t in re.findall(r'text-anchor="end">(\d+)<', svg)] == ["0", "1", "2"]


def test_failure_axis_without_failures():
    svg = dashboard.failure_bars([run("r1", a="passed")])
    assert re.findall(r'text-anchor="end">(\d+)<', svg) == ["0", "1"]


def test_duration_line_scales_to_the_slowest_run():
    svg = dashboard.duration_line([run("r1", a="passed"), run("r2", a="passed", b="passed")])
    assert "<title>r1: 0.0 min</title>" in svg and "<title>r2: 0.1 min</title>" in svg
    ys = [float(y) for y in re.findall(r'cy="([\d.]+)"', svg)]
    plot = dashboard.H - dashboard.PAD_B - dashboard.PAD_T
    assert ys == [pytest.approx(dashboard.PAD_T + plot / 2, abs=0.1), pytest.approx(dashboard.PAD_T, abs=0.1)]
    assert "<path" in svg
    assert "<path" not in dashboard.duration_line([run("only", a="passed")])


def test_run_labels_are_thinned_out():
    def labels(n):
        return re.findall(r'text-anchor="(?:middle|end)">([^<]*)<', dashboard._run_labels([run(f"r{i:02}") for i in range(n)]))

    assert labels(40) == ["r00", "r05", "r10", "r15", "r20", "r25", "r30", "r39"]  # r35 would overlap r39
    assert labels(30) == ["r00", "r03", "r06", "r09", "r12", "r15", "r18", "r21", "r24", "r29"]
    assert labels(3) == ["r00", "r01", "r02"]
    assert labels(0) == []
    assert 'text-anchor="end">r02<' in dashboard._run_labels([run(f"r{i:02}") for i in range(3)])
    assert 'text-anchor="middle">r00<' in dashboard._run_labels([run("r00")])
