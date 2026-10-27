"""Read pytest JUnit XML into one Result per test: the common input of every report and history tool."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

OUTCOMES = ("passed", "failed", "known bug", "skipped")


@dataclass(frozen=True)
class Result:
    test_id: str
    layer: str
    outcome: str
    seconds: float
    message: str = ""


def parse(path: Path) -> list[Result]:
    results = []
    for case in ET.parse(path).getroot().iter("testcase"):
        classname = case.get("classname", "")
        parts = classname.split(".")
        layer = parts[1] if len(parts) > 2 and parts[0] == "tests" else "other"
        outcome, message = "passed", ""
        for child in case:
            if child.tag in ("failure", "error"):
                outcome, message = "failed", child.get("message", "")
            elif child.tag == "skipped":
                is_xfail = child.get("type") == "pytest.xfail"
                outcome, message = ("known bug" if is_xfail else "skipped"), child.get("message", "")
        test_id = f"{classname.replace('.', '/')}.py::{case.get('name')}"
        results.append(Result(test_id, layer, outcome, float(case.get("time") or 0), message))
    return results
