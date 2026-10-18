"""Offline tests for the AI evaluator: the scoring rules must behave as documented."""
import pytest

from ai.evaluate import Case, evaluate, tokens

pytestmark = pytest.mark.unit


def case(id, title, type="Positive", detail=""):
    return Case(id, title, type, detail)


def test_synonyms_are_normalised():
    assert tokens("user not logged in") == tokens("anonymous user")
    assert tokens("repository does not exist")["missing"] == 1


def test_negation_words_are_kept():
    assert "empty" in tokens("Reject empty title")


def test_matching_is_one_to_one():
    manual = [case("M1", "Close an issue")]
    ai = [case("A1", "Close an open issue"), case("A2", "Close issue from list")]
    result = evaluate(ai, manual)
    assert len(result["valid"]) == 1
    assert result["missed"] == []


def test_duplicate_detected_and_not_counted_as_valid():
    ai = [case("A1", "Reject empty comment", "Negative"), case("A2", "Reject empty comment", "Negative")]
    result = evaluate(ai, [case("M1", "Empty comment is rejected", "Negative")])
    assert [d[0].id for d in result["duplicates"]] == ["A2"]
    assert result["metrics"]["valid"] == 1


def test_positive_vs_negative_is_penalised():
    """'Create issue with title' must not match 'Create issue with empty title'."""
    manual = [case("M1", "Create issue with empty title", "Negative")]
    ai = [case("A1", "Create issue with title", "Positive")]
    assert evaluate(ai, manual)["valid"] == []


def test_missed_and_new_reported():
    manual = [case("M1", "Pagination of issue list", "Boundary")]
    ai = [case("A1", "Markdown renders safely")]
    result = evaluate(ai, manual)
    assert [m.id for m in result["missed"]] == ["M1"]
    assert [a.id for a in result["new"]] == ["A1"]
    assert result["metrics"]["coverage_of_manual"] == 0
