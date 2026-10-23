"""Quarantine for flaky tests: a reviewed list with an owner, a reason and an expiry date.

A flaky test that keeps failing the build teaches people to re-run until green, and deleting it loses
coverage. A quarantined test still runs in CI, in a separate non-blocking step, so its history keeps
being recorded, but it cannot fail the build. Every entry expires: `qualitylens quarantine check`
(run in the lint job) fails once the date has passed, so a quarantine cannot quietly become permanent.

quarantine.toml:

    [[test]]
    id = "tests/ui/test_login.py::test_logout"   # pytest node id; without [params] it covers all of them
    reason = "Logout redirect races the session cookie, about 1 run in 8"
    owner = "roy032"
    issue = "https://github.com/roy032/qualitylens/issues/12"
    expires = 2026-11-30
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path("quarantine.toml")
MAX_DAYS = 30
REQUIRED = ("id", "reason", "owner", "expires")


class QuarantineError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    test_id: str
    reason: str
    owner: str
    expires: date
    issue: str = ""


def load(path: Path = DEFAULT_PATH) -> list[Entry]:
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise QuarantineError(f"{path}: {exc}") from exc
    entries = []
    for i, raw in enumerate(data.get("test", []), start=1):
        missing = [k for k in REQUIRED if not str(raw.get(k, "")).strip()]
        if missing:
            raise QuarantineError(f"{path}: entry {i} is missing {', '.join(missing)}")
        if not isinstance(raw["expires"], date):
            raise QuarantineError(f"{path}: entry {i}: expires must be a date like 2026-11-30")
        entries.append(Entry(raw["id"].strip(), raw["reason"].strip(), raw["owner"].strip(),
                             raw["expires"], str(raw.get("issue", "")).strip()))
    return entries


def base_id(node_id: str) -> str:
    """tests/x.py::test_a[1-2] -> tests/x.py::test_a"""
    return node_id.split("[", 1)[0]


def is_quarantined(node_id: str, ids: set[str]) -> bool:
    return node_id in ids or base_id(node_id) in ids


def names_real_test(test_id: str, root: Path) -> bool:
    """tests/x.py::test_a[...] names a `def test_a(` in tests/x.py under root (no collection, no app needed)."""
    path, _, name = base_id(test_id).partition("::")
    source = root / path
    if not name or not source.is_file():
        return False
    return re.search(rf"^\s*(async\s+)?def {re.escape(name.split('::')[-1])}\(", source.read_text(), re.M) is not None


def problems(entries: list[Entry], today: date, root: Path | None = None) -> list[str]:
    """Everything that makes the quarantine list invalid; empty when it is fine."""
    found = []
    seen: set[str] = set()
    for e in entries:
        if e.test_id in seen:
            found.append(f"{e.test_id}: listed twice")
        seen.add(e.test_id)
        if e.expires < today:
            found.append(f"{e.test_id}: quarantine expired on {e.expires} (owner {e.owner}): fix the test or "
                         f"renew it with a new reason")
        elif (e.expires - today).days > MAX_DAYS:
            found.append(f"{e.test_id}: expires {e.expires}, more than {MAX_DAYS} days ahead")
        if root is not None and not names_real_test(e.test_id, root):
            found.append(f"{e.test_id}: no such test (renamed or deleted?)")
    return found
