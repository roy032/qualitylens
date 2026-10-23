"""`qualitylens doctor`: check that this machine can run the suite, and say how to fix what is missing.

Most "the tests are broken" reports on a new machine are a stopped container, a missing browser or the
wrong Python. Each check returns a one-line fix instead of a stack trace.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass

from qualitylens.config import Settings

MIN_PYTHON = (3, 12)
PACKAGES = ("pytest", "playwright", "requests", "psycopg", "jsonschema", "hypothesis", "allure_commons", "locust")


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


def check_packages(find: Callable[[str], object] = importlib.util.find_spec) -> Check:
    missing = [p for p in PACKAGES if find(p) is None]
    return Check("Python packages", not missing,
                 "all installed" if not missing else f"missing {', '.join(missing)}: pip install -r requirements.txt")


def check_docker(which: Callable[[str], str | None] = shutil.which) -> Check:
    path = which("docker")
    return Check("Docker", path is not None, path or "not found: install Docker to start Gitea (make up)",
                 required=False)


def check_browser(executable: Callable[[], str]) -> Check:
    try:
        path = executable()
    except Exception as exc:  # playwright raises its own error types, all mean "not usable"
        return Check("Chromium (Playwright)", False, f"{exc.__class__.__name__}: python -m playwright install chromium")
    ok = bool(path) and os.path.exists(path)
    return Check("Chromium (Playwright)", ok, path if ok else "not installed: python -m playwright install chromium")


def check_app(settings: Settings, get: Callable[..., object]) -> Check:
    try:
        response = get(f"{settings.api_url}/version", timeout=5)
        response.raise_for_status()  # type: ignore[attr-defined]
        version = response.json().get("version", "?")  # type: ignore[attr-defined]
    except Exception as exc:
        return Check("Gitea", False, f"not reachable at {settings.base_url} ({exc.__class__.__name__}): make up")
    return Check("Gitea", True, f"{version} at {settings.base_url}")


def check_login(settings: Settings, get: Callable[..., object]) -> Check:
    try:
        response = get(f"{settings.api_url}/user", auth=(settings.admin_user, settings.admin_password), timeout=5)
        status = response.status_code  # type: ignore[attr-defined]
    except Exception as exc:
        return Check("Admin login", False, f"{exc.__class__.__name__}: is Gitea running?")
    if status == 200:
        return Check("Admin login", True, settings.admin_user)
    return Check("Admin login", False, f"HTTP {status} for {settings.admin_user}: run make up to create the admin")


def check_db(settings: Settings, connect: Callable[..., object]) -> Check:
    try:
        connect(settings.db_dsn, connect_timeout=5).close()  # type: ignore[attr-defined]
    except Exception as exc:
        return Check("PostgreSQL", False, f"{exc.__class__.__name__}: is the db container up? (make up)",
                     required=False)
    return Check("PostgreSQL", True, settings.db_dsn.rsplit("@", 1)[-1], required=False)


def run_all(settings: Settings, offline: bool = False) -> list[Check]:
    checks = [check_python(), check_packages(), check_docker()]
    try:
        from playwright.sync_api import sync_playwright

        def chromium_path() -> str:
            with sync_playwright() as p:
                return p.chromium.executable_path
        checks.append(check_browser(chromium_path))
    except ImportError:
        checks.append(Check("Chromium (Playwright)", False, "playwright is not installed"))
    if not offline:
        import psycopg
        import requests

        checks += [check_app(settings, requests.get), check_login(settings, requests.get),
                   check_db(settings, psycopg.connect)]
    return checks


def render(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        mark = "✓" if c.ok else ("✗" if c.required else "!")
        lines.append(f" {mark} {c.name:<22} {c.detail}")
    return "\n".join(lines)


def healthy(checks: list[Check]) -> bool:
    return all(c.ok for c in checks if c.required)
