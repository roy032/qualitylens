"""Accessibility scanning with axe-core (the engine behind Lighthouse and the axe browser extension).

Scans are limited to WCAG 2.1 level A and AA rules, the level most accessibility laws refer to.
Gitea already has some violations, so tests compare against a recorded baseline: anything *new*
fails, known issues are reported but do not block, and the baseline shrinks as they get fixed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe

WCAG_AA = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]},
           "resultTypes": ["violations"]}
BASELINE_FILE = Path(__file__).resolve().parents[1] / "tests" / "a11y" / "baseline.json"

_axe = Axe()


@dataclass(frozen=True)
class Violation:
    rule: str
    impact: str
    help: str
    help_url: str
    targets: tuple[str, ...]

    def describe(self) -> str:
        where = ", ".join(self.targets[:3]) + (" ..." if len(self.targets) > 3 else "")
        return f"[{self.impact}] {self.rule}: {self.help} ({len(self.targets)} element(s): {where}) {self.help_url}"


def scan(page) -> list[Violation]:
    raw = _axe.run(page, options=WCAG_AA).response
    return parse(raw)


def parse(raw: dict) -> list[Violation]:
    return sorted(
        (Violation(v["id"], v.get("impact") or "unknown", v["help"], v["helpUrl"],
                   tuple(" ".join(map(str, n["target"])) for n in v["nodes"]))
         for v in raw.get("violations", [])),
        key=lambda v: v.rule)


def load_baseline(path: Path = BASELINE_FILE) -> dict[str, list[str]]:
    return json.loads(path.read_text())["pages"]


def new_violations(found: list[Violation], allowed_rules: list[str]) -> list[Violation]:
    """Violations whose rule is not in the page's baseline: these are regressions."""
    return [v for v in found if v.rule not in set(allowed_rules)]


def fixed_rules(found: list[Violation], allowed_rules: list[str]) -> list[str]:
    """Baseline rules that no longer fire: the baseline can be tightened."""
    return sorted(set(allowed_rules) - {v.rule for v in found})
