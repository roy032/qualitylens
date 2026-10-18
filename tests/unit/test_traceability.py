"""Every manual test case that claims automation must point at a test that really exists."""
import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
pytestmark = pytest.mark.unit


def referenced_tests():
    with (ROOT / "test-cases" / "manual_test_cases.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            for ref in re.findall(r"(tests/\S+?\.py)::(\w+)", row["Automated Test"]):
                yield row["ID"], *ref


@pytest.mark.parametrize("case_id, path, func", list(referenced_tests()))
def test_reference_exists(case_id, path, func):
    source = (ROOT / path).read_text()
    assert re.search(rf"^def {func}\(", source, re.M), f"{case_id} points at missing test {path}::{func}"


def test_every_manual_case_is_traced():
    with (ROOT / "test-cases" / "manual_test_cases.csv").open(newline="") as f:
        untraced = [r["ID"] for r in csv.DictReader(f) if not r["Automated Test"].strip()]
    assert untraced == []
