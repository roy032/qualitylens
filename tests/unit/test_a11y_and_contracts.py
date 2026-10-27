"""Offline checks of the accessibility baseline logic and the JSON-schema contract helper."""
import pytest

from qualitylens import a11y
from suite import schemas

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


# Added after mutation testing (make mutation): these details of the report were not pinned down.
def test_parse_details():
    raw = {"violations": [{"id": "region", "help": "Landmarks", "helpUrl": "https://x/region",
                           "nodes": [{"target": ["iframe", "#inner"]}]}]}
    assert a11y.parse(raw) == [a11y.Violation("region", "unknown", "Landmarks", "https://x/region", ("iframe #inner",))]
    assert a11y.parse({}) == []


@pytest.mark.parametrize("count, expected", [
    (3, "#t0, #t1, #t2"), (4, "#t0, #t1, #t2 ..."),
])
def test_describe_lists_at_most_three_targets(count, expected):
    v = a11y.Violation("label", "critical", "Labels", "https://x", tuple(f"#t{i}" for i in range(count)))
    assert v.describe() == f"[critical] label: Labels ({count} element(s): {expected}) https://x"


def test_contract_errors_name_the_nested_path():
    schema = {"type": "object", "properties": {"owner": {"type": "object", "properties": {
        "tags": schemas.list_of({"type": "string"})}}}}
    assert schemas.contract_errors({"owner": {"tags": ["a", 7]}}, schema) == ["owner/tags/1: 7 is not of type 'string'"]
    assert schemas.contract_errors({"owner": {"tags": "a"}}, schema) == ["owner/tags: 'a' is not of type 'array'"]
    assert schemas.contract_errors([], schema) == ["<root>: [] is not of type 'object'"]
