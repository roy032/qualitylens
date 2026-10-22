"""Offline tests for the AI evaluator: the scoring rules must behave as documented."""
import json
import math
from collections import Counter

import pytest

from ai import evaluate as ev
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


# Added after mutation testing (make mutation) showed these rules were not pinned down:
# an AI case could be matched twice, and the best-score-first order and the thresholds could change unnoticed.
def test_an_ai_case_matches_at_most_one_manual_case():
    manual = [case("M1", "Close an issue"), case("M2", "Close an issue from the list")]
    result = evaluate([case("A1", "Close an issue")], manual)
    assert [(a.id, m.id) for a, m, _ in result["valid"]] == [("A1", "M1")]
    assert [m.id for m in result["missed"]] == ["M2"]


def test_best_scoring_pair_is_matched_first():
    manual = [case("M1", "Add label to issue"), case("M2", "Remove label from issue")]
    ai = [case("A1", "Label added to issue"), case("A2", "Remove a label from an issue")]
    pairs = [(a.id, m.id) for a, m, _ in evaluate(ai, manual)["valid"]]
    assert sorted(pairs) == [("A1", "M1"), ("A2", "M2")]
    # Each pair is listed with its score, highest first.
    scores = [s for *_, s in evaluate(ai, manual)["valid"]]
    assert scores == sorted(scores, reverse=True)


def test_thresholds_are_inclusive():
    a, m = case("A1", "Lock the conversation"), case("M1", "Lock conversation now")
    score = ev.similarity(a, m, {c.id: ev.vector(c) for c in (a, m)})
    assert 0 < score < 1
    assert len(evaluate([a], [m], match_at=score)["valid"]) == 1
    assert len(evaluate([a], [m], match_at=score + 1e-9)["valid"]) == 0
    twin = case("A2", m.title)
    assert len(evaluate([a, twin], [], duplicate_at=score)["duplicates"]) == 1
    assert len(evaluate([a, twin], [], duplicate_at=score + 1e-9)["duplicates"]) == 0


def test_duplicate_points_at_the_closest_kept_case():
    ai = [case("A1", "Pin issue"), case("A2", "Lock conversation"), case("A3", "Lock the conversation now")]
    (dup, twin, score), = evaluate(ai, [])["duplicates"]
    assert (dup.id, twin.id) == ("A3", "A2")
    assert score == pytest.approx(ev.similarity(ai[2], ai[1], {c.id: ev.vector(c) for c in ai}))


def test_metrics_are_exact():
    ai = [case("A1", "Close an issue"), case("A2", "Close an issue"), case("A3", "Markdown renders safely")]
    manual = [case("M1", "Close an issue"), case("M2", "Pagination", "Boundary"), case("M3", "Reopen", "Positive")]
    assert evaluate(ai, manual)["metrics"] == {
        "ai_cases": 3, "manual_cases": 3, "valid": 1, "new": 1, "duplicate": 1, "missed": 2,
        "coverage_of_manual": 0.33, "duplicate_rate": 0.33}
    assert evaluate([], [])["metrics"] == {
        "ai_cases": 0, "manual_cases": 0, "valid": 0, "new": 0, "duplicate": 0, "missed": 0,
        "coverage_of_manual": 0, "duplicate_rate": 0}


def test_plural_s_is_stripped_only_from_longer_words():
    assert tokens("LABELS bus") == Counter({"label": 1, "bus": 1})
    assert tokens("pins") == Counter({"pin": 1})


def test_title_words_weigh_three_times():
    assert ev.vector(case("1", "label", detail="label milestone")) == Counter({"label": 4, "milestone": 1})


def test_cosine():
    assert ev.cosine(Counter(a=1, b=1), Counter(a=1)) == pytest.approx(1 / math.sqrt(2))
    assert ev.cosine(Counter(a=1), Counter(b=1)) == 0
    assert ev.cosine(Counter(), Counter(a=1)) == 0.0


def test_loaders(tmp_path):
    csv_path = tmp_path / "manual.csv"
    csv_path.write_text("ID,Feature,Title,Type,Test Data,Expected Result\n"
                        "M1,Issues,Close issue,Positive,#1,Closed\nM2,Login,Sign in,Positive,,Dashboard\n")
    assert ev.load_manual("Issues", csv_path) == [Case("M1", "Close issue", "Positive", "#1 Closed")]
    ai_path = tmp_path / "x.ai.json"
    ai_path.write_text(json.dumps({"test_cases": [
        {"id": "AI-1", "title": "T", "type": "Negative", "test_data": "d", "expected_result": "e"}]}))
    assert ev.load_ai(ai_path) == [Case("AI-1", "T", "Negative", "d e")]
    assert len(ev.load_manual("Issues")) > 10   # the real CSV


def test_main_writes_a_markdown_report(tmp_path, capsys):
    ai_path = tmp_path / "demo.ai.json"
    ai_path.write_text(json.dumps({"test_cases": [
        {"id": "AI-1", "title": "Create issue with title and body", "type": "Positive",
         "test_data": "title", "expected_result": "issue created"},
        {"id": "AI-2", "title": "Create issue with title and body", "type": "Positive",
         "test_data": "title", "expected_result": "issue created"},
        {"id": "AI-3", "title": "Teleport issue to the moon", "type": "Positive",
         "test_data": "", "expected_result": ""}]}))
    with pytest.raises(SystemExit):
        ev.main([str(ai_path)])                     # --feature is required
    capsys.readouterr()
    ev.main([str(ai_path), "--feature", "Issues", "--match-at", "0.99", "--duplicate-at", "0.2"])
    assert "| Valid (matched a manual case) | 0 |" in (tmp_path / "demo.report.md").read_text()
    capsys.readouterr()
    ev.main([str(ai_path), "--feature", "Issues"])   # default thresholds 0.40 / 0.75
    report = (tmp_path / "demo.report.md").read_text()
    assert report.startswith("# AI vs manual test cases: Issues\n\nAI output: `demo.ai.json`.")
    assert "| AI cases | 3 |" in report and "| Duplicate | 1 |" in report and "| New (no manual match, review) | 1 |" in report
    assert "| Valid (matched a manual case) | 1 |" in report
    assert "| AI-3 | Positive | Teleport issue to the moon |" in report
    assert "| AI-2 | AI-1 | 1.00 | Create issue with title and body |" in report
    assert "| Coverage of manual suite | " in report and "## Missed: manual cases the AI did not produce" in report
    out = capsys.readouterr().out
    assert out.startswith('{\n  "ai_cases": 3,\n  "manual_cases": ')
    assert out.rstrip().endswith("demo.report.md")


def test_markdown_report_is_exact(tmp_path):
    ai = [case("A1", "Close an issue"), case("A2", "Close an issue"), case("A3", "Markdown renders safely")]
    manual = [case("M1", "Close an issue"), case("M2", "Pagination", "Boundary")]
    assert ev.to_markdown(evaluate(ai, manual), tmp_path / "demo.ai.json", "Issues") == "\n".join([
        "# AI vs manual test cases: Issues", "",
        "AI output: `demo.ai.json`. Manual suite: `test-cases/manual_test_cases.csv` (feature = Issues).", "",
        "| Metric | Value |", "|---|---|",
        "| AI cases | 3 |", "| Manual cases | 2 |", "| Valid (matched a manual case) | 1 |",
        "| New (no manual match, review) | 1 |", "| Duplicate | 1 |", "| Missed (manual case not generated) | 1 |",
        "| Coverage of manual suite | 50% |", "",
        "## Valid: AI case matched to manual case", "",
        "| AI | Manual | Score | AI title | Manual title |", "|---|---|---|---|---|",
        "| A1 | M1 | 1.00 | Close an issue | Close an issue |", "",
        "## New: no manual equivalent (review: real gap or noise?)", "",
        "| AI | Type | Title |", "|---|---|---|",
        "| A3 | Positive | Markdown renders safely |", "",
        "## Duplicate AI cases", "",
        "| AI | Duplicates | Score | Title |", "|---|---|---|---|",
        "| A2 | A1 | 1.00 | Close an issue |", "",
        "## Missed: manual cases the AI did not produce", "",
        "| Manual | Type | Title |", "|---|---|---|",
        "| M2 | Boundary | Pagination |", "",
    ])
