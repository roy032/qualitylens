"""Compare AI-generated test cases with the hand-written suite.

Usage:
    python -m ai.evaluate ai/output/create_issue.ai.json --feature Issues
    -> ai/output/create_issue.report.md

Each case is turned into a bag of words (title weighted x3, plus test data and expected
result) and compared with cosine similarity; success-path vs failure-path pairs are penalised. That is deliberately simple: every score is
explainable, and the report shows the matched pairs so a human makes the final call.

Categories in the report:
  valid      AI case that matches a hand-written case (confirmed useful)
  new        AI case with no hand-written match: a gap in the manual suite, or noise. Needs review.
  duplicate  AI case that repeats an earlier AI case
  missed     hand-written case the AI did not produce
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

MANUAL_CSV = Path(__file__).parents[1] / "test-cases" / "manual_test_cases.csv"
# Words that appear in almost every case and carry no meaning for matching. Words that flip meaning
# ("empty", "invalid", "not", "reject") are deliberately NOT stopwords.
STOPWORDS = set("""a an the and or of to in on for with is are be by as at it its this that from into
then when should must user page shown show displayed field value enter entered click create created
issue issues test case""".split())
# Phrases that mean the same thing in test cases, mapped to one canonical word before comparing.
SYNONYMS = [
    (r"not (signed|logged) in|without (being )?(signed|logged) in|without credentials|unauthenticated|anonymous",
     "anonymous"),
    (r"does not exist|doesn't exist|non-?existent|unknown|missing", "missing"),
    (r"(signed|logged) in", "authenticated"),
    (r"maximum|max\b", "max"),
    (r"minimum|min\b", "min"),
]
TITLE_WEIGHT = 3          # the title says what is tested; data/expected text only adds detail
POLARITY = {"Positive": "+", "Negative": "-", "Security": "-", "Boundary": "b"}


@dataclass
class Case:
    id: str
    title: str
    type: str
    detail: str  # test data + expected result


def tokens(text: str) -> Counter:
    text = text.lower()
    for pattern, canonical in SYNONYMS:
        text = re.sub(pattern, canonical, text)
    words = re.findall(r"[a-z0-9]+", text)
    stem = [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words]
    return Counter(w for w in stem if w not in STOPWORDS)


def vector(case: Case) -> Counter:
    vec = tokens(case.detail)
    for word, n in tokens(case.title).items():
        vec[word] += n * TITLE_WEIGHT
    return vec


def similarity(a: Case, b: Case, vec: dict) -> float:
    """Cosine similarity, halved when one case checks a success path and the other a failure path."""
    score = cosine(vec[a.id], vec[b.id])
    if {POLARITY.get(a.type), POLARITY.get(b.type)} == {"+", "-"}:
        score *= 0.5
    return score


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


def load_manual(feature: str, path: Path = MANUAL_CSV) -> list[Case]:
    with path.open(newline="") as f:
        return [Case(r["ID"], r["Title"], r["Type"], f"{r['Test Data']} {r['Expected Result']}")
                for r in csv.DictReader(f) if r["Feature"] == feature]


def load_ai(path: Path) -> list[Case]:
    data = json.loads(path.read_text())
    return [Case(c["id"], c["title"], c["type"], f"{c['test_data']} {c['expected_result']}")
            for c in data["test_cases"]]


def evaluate(ai: list[Case], manual: list[Case], match_at: float = 0.40, duplicate_at: float = 0.75) -> dict:
    vec = {c.id: vector(c) for c in ai + manual}

    # 1. Duplicates inside the AI output: a later case too similar to an earlier, kept case.
    kept, duplicates = [], []
    for case in ai:
        twin = max(((k, similarity(case, k, vec)) for k in kept), key=lambda p: p[1], default=None)
        if twin and twin[1] >= duplicate_at:
            duplicates.append((case, twin[0], twin[1]))
        else:
            kept.append(case)

    # 2. Greedy one-to-one matching of kept AI cases to manual cases, best scores first.
    pairs = sorted(((similarity(a, m, vec), a, m) for a in kept for m in manual), key=lambda p: -p[0])
    used_ai, used_manual, valid = set(), set(), []
    for score, a, m in pairs:
        if score < match_at:
            break
        if a.id not in used_ai and m.id not in used_manual:
            valid.append((a, m, score))
            used_ai.add(a.id)
            used_manual.add(m.id)

    new = [a for a in kept if a.id not in used_ai]
    missed = [m for m in manual if m.id not in used_manual]
    return {
        "valid": valid, "new": new, "duplicates": duplicates, "missed": missed,
        "metrics": {
            "ai_cases": len(ai),
            "manual_cases": len(manual),
            "valid": len(valid),
            "new": len(new),
            "duplicate": len(duplicates),
            "missed": len(missed),
            "coverage_of_manual": round(len(valid) / len(manual), 2) if manual else 0,
            "duplicate_rate": round(len(duplicates) / len(ai), 2) if ai else 0,
        },
    }


def to_markdown(result: dict, ai_path: Path, feature: str) -> str:
    m = result["metrics"]
    lines = [
        f"# AI vs manual test cases: {feature}",
        "",
        f"AI output: `{ai_path.name}`. Manual suite: `test-cases/manual_test_cases.csv` (feature = {feature}).",
        "",
        "| Metric | Value |", "|---|---|",
        f"| AI cases | {m['ai_cases']} |",
        f"| Manual cases | {m['manual_cases']} |",
        f"| Valid (matched a manual case) | {m['valid']} |",
        f"| New (no manual match, review) | {m['new']} |",
        f"| Duplicate | {m['duplicate']} |",
        f"| Missed (manual case not generated) | {m['missed']} |",
        f"| Coverage of manual suite | {m['coverage_of_manual']:.0%} |",
        "",
        "## Valid: AI case matched to manual case", "",
        "| AI | Manual | Score | AI title | Manual title |", "|---|---|---|---|---|",
        *[f"| {a.id} | {mm.id} | {s:.2f} | {a.title} | {mm.title} |" for a, mm, s in result["valid"]],
        "", "## New: no manual equivalent (review: real gap or noise?)", "",
        "| AI | Type | Title |", "|---|---|---|",
        *[f"| {a.id} | {a.type} | {a.title} |" for a in result["new"]],
        "", "## Duplicate AI cases", "",
        "| AI | Duplicates | Score | Title |", "|---|---|---|---|",
        *[f"| {a.id} | {k.id} | {s:.2f} | {a.title} |" for a, k, s in result["duplicates"]],
        "", "## Missed: manual cases the AI did not produce", "",
        "| Manual | Type | Title |", "|---|---|---|",
        *[f"| {mm.id} | {mm.type} | {mm.title} |" for mm in result["missed"]],
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ai_json", type=Path)
    parser.add_argument("--feature", required=True, help="Feature column value in the manual CSV")
    parser.add_argument("--match-at", type=float, default=0.40)
    parser.add_argument("--duplicate-at", type=float, default=0.75)
    args = parser.parse_args(argv)

    result = evaluate(load_ai(args.ai_json), load_manual(args.feature), args.match_at, args.duplicate_at)
    report = args.ai_json.with_name(args.ai_json.name.replace(".ai.json", ".report.md"))
    report.write_text(to_markdown(result, args.ai_json, args.feature))
    print(json.dumps(result["metrics"], indent=2))
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
