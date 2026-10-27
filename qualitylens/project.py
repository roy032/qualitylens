"""Project configuration: qualitylens.toml describes the app under test and how its suite is run.

QualityLens is an engine; a project (the Gitea suite in this repository, or a suite made with
`qualitylens init` for your own app) says what it points at:

    [project]
    name = "My shop"
    layers = ["smoke", "api", "ui"]          # pytest markers; tests/<layer>/ maps to its marker

    [target]
    base_url = "http://localhost:8000"      # QL_BASE_URL overrides it
    health_path = "/health"                 # must answer 2xx before tests that need the app run
    requires_app = ["api", "ui"]            # markers of tests that need the app running
    start_hint = "docker compose up -d"     # printed when the app is not reachable
    api_prefix = "/api"                     # the `api` fixture's paths are relative to this

    [target.login]                          # optional: credentials for fixtures and `doctor`
    path = "/api/me"
    user_env = "QL_USER"
    password_env = "QL_PASSWORD"

    [target.database]                       # optional: `doctor` checks it is reachable
    dsn_env = "QL_DB_DSN"

    [profiles]                              # `qualitylens run <name>`: one pytest call per list
    smoke = [["-m", "smoke"]]

    [impact]
    fallback_profile = "full"               # `run impacted` when a change can affect everything

    [[impact.rule]]                         # `qualitylens impact`: first match wins
    glob = "src/payments/*"
    layers = ["api"]

Every section is optional. Missing values fall back to DEFAULTS below, so an empty file (or none at
all) still gives a working runner for a plain pytest suite.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FILENAME = "qualitylens.toml"
QUARANTINED = "quarantined"

DEFAULT_PROFILES: dict[str, list[list[str]]] = {
    "smoke": [["-m", f"smoke and not {QUARANTINED}"]],
    "full": [["-m", f"not {QUARANTINED}"]],
    QUARANTINED: [["-m", QUARANTINED]],
}
# Paths that never change test behaviour. Anything not matched by a rule or the tests/<layer>/ convention
# selects every layer, so a selection can be too wide but never too narrow.
DEFAULT_IMPACT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("*.md", ()),
    ("docs/*", ()),
    ("LICENSE", ()),
    (".github/ISSUE_TEMPLATE/*", ()),
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Login:
    path: str
    user: str
    password: str


@dataclass(frozen=True)
class Project:
    root: Path = Path(".")
    name: str = "project"
    layers: tuple[str, ...] = ()
    base_url: str = "http://localhost:8000"
    health_path: str = ""
    requires_app: tuple[str, ...] = ()
    start_hint: str = "start the app under test"
    api_prefix: str = ""
    login: Login | None = None
    database_dsn: str = ""
    packages: tuple[str, ...] = ("pytest", "requests")
    browser: bool = False
    profiles: dict[str, list[list[str]]] = field(default_factory=lambda: dict(DEFAULT_PROFILES))
    impact_rules: tuple[tuple[str, tuple[str, ...]], ...] = DEFAULT_IMPACT_RULES
    impact_fallback: str = "full"
    history_path: Path = Path("test-history/history.json")
    history_keep: int = 50
    flaky_min_runs: int = 10
    flaky_threshold: float = 0.1
    quarantine_path: Path = Path("quarantine.toml")

    @property
    def health_url(self) -> str:
        return f"{self.base_url}{self.health_path}" if self.health_path else ""

    @property
    def api_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}"


def find(start: Path) -> Path | None:
    """qualitylens.toml in `start` or the nearest parent directory, like git and pyproject tools do."""
    for folder in (start, *start.parents):
        candidate = folder / FILENAME
        if candidate.is_file():
            return candidate
    return None


def _table(data: dict, key: str, where: str) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{where}{key} must be a table")
    return value


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where} must be a list of strings")
    return tuple(value)


def _profiles(raw: dict) -> dict[str, list[list[str]]]:
    profiles = dict(DEFAULT_PROFILES)
    for name, steps in raw.items():
        if not isinstance(steps, list) or not steps or not all(isinstance(s, list) for s in steps):
            raise ConfigError(f"profiles.{name} must be a list of pytest argument lists, e.g. [[\"-m\", \"smoke\"]]")
        profiles[name] = [list(_strings(step, f"profiles.{name}")) for step in steps]
    return profiles


def _rules(raw: list) -> tuple[tuple[str, tuple[str, ...]], ...]:
    rules = []
    for i, rule in enumerate(raw, start=1):
        if not isinstance(rule, dict) or not isinstance(rule.get("glob"), str):
            raise ConfigError(f"impact.rule {i} needs a glob")
        rules.append((rule["glob"], _strings(rule.get("layers", []), f"impact.rule {i} layers")))
    return tuple(rules)


def parse(data: dict, root: Path, env: dict[str, str] | None = None) -> Project:
    env = dict(os.environ) if env is None else env
    project = _table(data, "project", "")
    target = _table(data, "target", "")
    login = _table(target, "login", "target.")
    database = _table(target, "database", "target.")
    doctor = _table(data, "doctor", "")
    history = _table(data, "history", "")
    flaky = _table(data, "flaky", "")
    impact = _table(data, "impact", "")
    defaults = Project()
    rules = _rules(impact.get("rule", []))
    return Project(
        root=root,
        name=str(project.get("name", root.resolve().name)),
        layers=_strings(project.get("layers", []), "project.layers"),
        base_url=env.get("QL_BASE_URL") or str(target.get("base_url", defaults.base_url)).rstrip("/"),
        health_path=str(target.get("health_path", "")),
        requires_app=_strings(target.get("requires_app", []), "target.requires_app"),
        start_hint=str(target.get("start_hint", defaults.start_hint)),
        api_prefix=str(target.get("api_prefix", "")).rstrip("/"),
        login=Login(str(login["path"]),
                    env.get(str(login.get("user_env", "QL_USER")), str(login.get("default_user", ""))),
                    env.get(str(login.get("password_env", "QL_PASSWORD")), str(login.get("default_password", ""))))
        if "path" in login else None,
        database_dsn=env.get(str(database.get("dsn_env", "QL_DB_DSN")), str(database.get("default_dsn", "")))
        if database else "",
        packages=_strings(doctor.get("packages", list(defaults.packages)), "doctor.packages"),
        browser=bool(doctor.get("browser", defaults.browser)),
        profiles=_profiles(_table(data, "profiles", "")),
        impact_rules=rules + DEFAULT_IMPACT_RULES if impact.get("keep_defaults", True) else rules,
        impact_fallback=str(impact.get("fallback_profile", defaults.impact_fallback)),
        history_path=root / str(history.get("path", defaults.history_path)),
        history_keep=int(history.get("keep", defaults.history_keep)),
        flaky_min_runs=int(flaky.get("min_runs", defaults.flaky_min_runs)),
        flaky_threshold=float(flaky.get("threshold", defaults.flaky_threshold)),
        quarantine_path=root / str(_table(data, "quarantine", "").get("path", defaults.quarantine_path)),
    )


def load(path: Path | None = None, start: Path | None = None, env: dict[str, str] | None = None) -> Project:
    """The project at `path`, or the nearest qualitylens.toml above `start` (default: the current directory).

    Without a config file the defaults apply, rooted at `start`.
    """
    start = start or Path.cwd()
    path = path or find(start)
    if path is None:
        return parse({}, start, env)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    try:
        return parse(data, path.parent, env)
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
