"""Test impact selection: which layers of the suite a change can affect.

    qualitylens impact --base origin/main      # -> pytest marker expression, or "all" / "none"

The full e2e suite needs a running Gitea and takes minutes; a change to one Page Object cannot break
the database checks. Each changed path is matched against RULES (first match wins) and the layers of
all matches are combined. Anything not covered by a rule, and anything shared by every layer
(fixtures, the API client, dependencies, CI), selects everything, so the selection can only be too
wide, never too narrow. CI still runs the whole suite on every push; this is for fast local feedback.
"""
from __future__ import annotations

import subprocess
from fnmatch import fnmatch

ALL = "all"
LAYERS = ("unit", "ui", "api", "db", "security", "a11y", "visual", "property", "load")

# (glob, layers). First match wins, so specific paths come before their folders.
RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("*.md", ()),
    ("docs/*", ()),
    ("bug-reports/*", ()),
    ("LICENSE", ()),
    (".github/ISSUE_TEMPLATE/*", ()),
    ("test-cases/*", ("unit",)),
    ("tests/unit/*", ("unit",)),
    ("tests/ui/*", ("ui",)),
    ("tests/api/test_properties.py", ("property",)),
    ("tests/api/*", ("api",)),
    ("tests/db/*", ("db",)),
    ("tests/security/*", ("security",)),
    ("tests/a11y/*", ("a11y",)),
    ("tests/visual/*", ("visual",)),
    ("pages/*", ("ui", "a11y", "visual", "security")),
    ("qualitylens/schemas.py", ("unit", "api")),
    ("qualitylens/oracles.py", ("unit", "property")),
    ("qualitylens/a11y.py", ("unit", "a11y")),
    ("qualitylens/visual.py", ("unit", "visual")),
    ("qualitylens/db.py", ("db",)),
    ("sql/*", ("db",)),
    ("load/*", ("load",)),
    ("ai/*", ("unit",)),
    ("scripts/bootstrap.sh", (ALL,)),
    ("scripts/*", ("unit",)),
    ("quarantine.toml", ("unit",)),
    ("qualitylens/junit.py", ("unit",)),
    ("qualitylens/history.py", ("unit",)),
    ("qualitylens/quarantine.py", ("unit",)),
    ("qualitylens/impact.py", ("unit",)),
    ("qualitylens/dashboard.py", ("unit",)),
    ("qualitylens/doctor.py", ("unit",)),
    ("qualitylens/cli.py", ("unit",)),
)


def layers_for(path: str) -> set[str]:
    for pattern, layers in RULES:
        if fnmatch(path, pattern):
            return set(layers)
    return {ALL}


def select(paths: list[str]) -> set[str]:
    chosen: set[str] = set()
    for path in paths:
        chosen |= layers_for(path.strip())
    return {ALL} if ALL in chosen else chosen


def marker_expression(layers: set[str]) -> str:
    """pytest -m expression for the selected layers; load has no pytest marker (it is a Locust run)."""
    if ALL in layers:
        return ALL
    markers = sorted(layers - {"load"})
    return " or ".join(markers) if markers else "none"


def changed_files(base: str) -> list[str]:
    """Files changed on this branch since it left `base`, plus uncommitted changes."""
    committed = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                               capture_output=True, text=True, check=True).stdout
    local = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, check=True).stdout
    return sorted({line for line in (committed + local).splitlines() if line.strip()})
