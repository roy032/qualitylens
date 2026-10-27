"""`qualitylens doctor`: check that this machine can run the project's suite, and say how to fix what is missing.

Most "the tests are broken" reports on a new machine are a stopped app, a missing browser or the wrong
Python. Each check returns a one-line fix instead of a stack trace. What is checked comes from
qualitylens.toml: the packages the suite needs, whether it drives a browser, the app's health URL,
the login and the database, when they are configured.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass

from qualitylens.project import Project

MIN_PYTHON = (3, 12)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def check_python(version: tuple[int, ...] = tuple(sys.version_info[:2])) -> Check:
    found = ".".join(map(str, version))
    need = ".".join(map(str, MIN_PYTHON))
    return Check("Python", version >= MIN_PYTHON, found if version >= MIN_PYTHON else f"{found}, needs {need}+")


def check_packages(packages: tuple[str, ...], find: Callable[[str], object] = importlib.util.find_spec) -> Check:
    missing = [p for p in packages if find(p) is None]
    return Check("Python packages", not missing,
                 "all installed" if not missing else f"missing {', '.join(missing)}: pip install -r requirements.txt")


def check_docker(which: Callable[[str], str | None] = shutil.which) -> Check:
    path = which("docker")
    return Check("Docker", path is not None, path or "not found (only needed if the app runs in Docker)",
                 required=False)


def check_browser(executable: Callable[[], str]) -> Check:
    try:
        path = executable()
    except Exception as exc:  # playwright raises its own error types, all mean "not usable"
        return Check("Chromium (Playwright)", False, f"{exc.__class__.__name__}: python -m playwright install chromium")
    ok = bool(path) and os.path.exists(path)
    return Check("Chromium (Playwright)", ok, path if ok else "not installed: python -m playwright install chromium")


def check_app(project: Project, get: Callable[..., object]) -> Check:
    name = f"{project.name} (app)"
    try:
        response = get(project.health_url, timeout=5)
        response.raise_for_status()  # type: ignore[attr-defined]
    except Exception as exc:
        return Check(name, False, f"not reachable at {project.health_url} ({exc.__class__.__name__}): "
                                  f"{project.start_hint}")
    return Check(name, True, f"{project.health_url} answers {response.status_code}")  # type: ignore[attr-defined]


def check_login(project: Project, get: Callable[..., object]) -> Check:
    login = project.login
    assert login is not None
    if not login.user:
        return Check("Login", False, "no user configured: set the env variable named in [target.login] user_env")
    try:
        response = get(f"{project.base_url}{login.path}", auth=(login.user, login.password), timeout=5)
        status = response.status_code  # type: ignore[attr-defined]
    except Exception as exc:
        return Check("Login", False, f"{exc.__class__.__name__}: is the app running?")
    if 200 <= status < 300:
        return Check("Login", True, login.user)
    return Check("Login", False, f"HTTP {status} for {login.user}: wrong credentials, or the user does not exist")


def check_db(project: Project, connect: Callable[..., object]) -> Check:
    try:
        connect(project.database_dsn, connect_timeout=5).close()  # type: ignore[attr-defined]
    except Exception as exc:
        return Check("Database", False, f"{exc.__class__.__name__}: is the database up?", required=False)
    return Check("Database", True, project.database_dsn.rsplit("@", 1)[-1], required=False)


def run_all(project: Project, offline: bool = False) -> list[Check]:
    checks = [check_python(), check_packages(project.packages), check_docker()]
    if project.browser:
        try:
            from playwright.sync_api import sync_playwright

            def chromium_path() -> str:
                with sync_playwright() as p:
                    return p.chromium.executable_path
            checks.append(check_browser(chromium_path))
        except ImportError:
            checks.append(Check("Chromium (Playwright)", False, "playwright is not installed"))
    if offline:
        return checks
    import requests

    if project.health_path:
        checks.append(check_app(project, requests.get))
    if project.login:
        checks.append(check_login(project, requests.get))
    if project.database_dsn:
        try:
            import psycopg
        except ImportError:
            checks.append(Check("Database", False, "psycopg is not installed", required=False))
        else:
            checks.append(check_db(project, psycopg.connect))
    return checks


def render(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        mark = "✓" if c.ok else ("✗" if c.required else "!")
        lines.append(f" {mark} {c.name:<22} {c.detail}")
    return "\n".join(lines)


def healthy(checks: list[Check]) -> bool:
    return all(c.ok for c in checks if c.required)
