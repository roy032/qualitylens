"""Test impact selection: which layers of the suite a change can affect.

    qualitylens impact --base origin/main      # -> pytest marker expression, or "all" / "none"

An e2e suite needs the app running and takes minutes; a change to one Page Object cannot break the
database checks. Each changed path is matched against the project's rules (qualitylens.toml
`[[impact.rule]]`, first match wins), then the convention that tests/<layer>/ belongs to the marker
<layer>. Anything not covered, and anything shared by every layer (fixtures, the API client,
dependencies, CI), selects everything, so the selection can only be too wide, never too narrow. CI
still runs the whole suite on every push; this is for fast feedback while working.
"""
from __future__ import annotations

import subprocess
from collections.abc import Iterable
from fnmatch import fnmatch

ALL = "all"
Rules = Iterable[tuple[str, tuple[str, ...]]]


def layers_for(path: str, rules: Rules, layers: Iterable[str] = ()) -> set[str]:
    for pattern, selected in rules:
        if fnmatch(path, pattern):
            return set(selected)
    parts = path.split("/")
    if len(parts) > 2 and parts[0] == "tests" and parts[1] in set(layers):
        return {parts[1]}
    return {ALL}


def select(paths: list[str], rules: Rules, layers: Iterable[str] = ()) -> set[str]:
    rules, layers = tuple(rules), tuple(layers)
    chosen: set[str] = set()
    for path in paths:
        chosen |= layers_for(path.strip(), rules, layers)
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
