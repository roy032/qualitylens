"""Offline checks of the accessibility baseline logic and the JSON-schema contract helper."""
import pytest

from qualitylens import a11y, schemas

pytestmark = pytest.mark.unit

AXE_OUTPUT = {"violations": [
    {"id": "label", "impact": "critical", "help": "Form elements must have labels", "helpUrl": "https://x/label",
     "nodes": [{"target": ["#a"]}, {"target": ["#b"]}]},
    {"id": "color-contrast", "impact": "serious", "help": "Contrast", "helpUrl": "https://x/cc",
     "nodes": [{"target": [".primary"]}]},
]}


def test_parse_axe_output():
    found = a11y.parse(AXE_OUTPUT)
    assert [(v.rule, v.impact, v.targets) for v in found] == [
        ("color-contrast", "serious", (".primary",)), ("label", "critical", ("#a", "#b"))]
    assert found[1].describe().startswith("[critical] label: Form elements must have labels (2 element(s): #a, #b)")


def test_only_rules_outside_the_baseline_are_regressions():
    found = a11y.parse(AXE_OUTPUT)
    assert [v.rule for v in a11y.new_violations(found, ["color-contrast"])] == ["label"]
    assert a11y.new_violations(found, ["color-contrast", "label"]) == []


def test_fixed_rules_are_reported():
    assert a11y.fixed_rules(a11y.parse(AXE_OUTPUT), ["label", "button-name"]) == ["button-name"]


def test_baseline_file_is_well_formed():
    baseline = a11y.load_baseline()
    assert baseline, "baseline has no pages"
    for page, rules in baseline.items():
        assert rules == sorted(set(rules)), f"{page}: keep rules sorted and unique"


GOOD_LABEL = {"id": 1, "name": "bug", "color": "ee0701", "description": "", "url": "http://localhost:3000/x"}


def test_contract_accepts_valid_payload():
    assert schemas.contract_errors(GOOD_LABEL, schemas.LABEL) == []


def test_contract_lists_every_problem():
    broken = {**GOOD_LABEL, "color": "#EE0701", "url": "not-a-url"}
    del broken["name"]
    errors = schemas.contract_errors(broken, schemas.LABEL)
    assert len(errors) == 3
    assert any(e.startswith("<root>: 'name' is a required property") for e in errors)
    assert any(e.startswith("color:") for e in errors)


def test_contract_checks_timestamps():
    milestone = {"id": 1, "title": "m", "state": "open", "open_issues": 0, "closed_issues": 0, "due_on": "tomorrow"}
    assert [e.split(":")[0] for e in schemas.contract_errors(milestone, schemas.MILESTONE)] == ["due_on"]
    assert schemas.contract_errors({**milestone, "due_on": None}, schemas.MILESTONE) == []
