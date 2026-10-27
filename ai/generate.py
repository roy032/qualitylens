"""Turn a user story or API spec into structured test cases with Claude.

Usage:
    export ANTHROPIC_API_KEY=...
    python -m ai.generate ai/stories/create_issue.md            # -> ai/output/create_issue.ai.json
    python -m ai.generate path/to/openapi-excerpt.yaml --model claude-sonnet-5-5

The output is JSON that matches ai/schema.py, so it can be diffed, reviewed and
scored by ai/evaluate.py against the hand-written suite.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import anthropic

from ai.schema import TEST_CASE_SCHEMA

DEFAULT_MODEL = "claude-opus-5-5"
OUTPUT_DIR = Path(__file__).parent / "output"

SYSTEM_PROMPT = """You are a senior QA engineer writing manual test cases.
Design techniques to apply: equivalence partitioning, boundary value analysis (test at, just below and
just above every limit), negative testing of every validation rule, and basic security checks
(authentication, authorisation, injection, XSS).
Rules:
- One behaviour per test case. Do not repeat a case with trivially different data; combine data variants
  into the test_data field instead.
- Steps are short imperative actions a tester can follow. Expected results are observable and specific
  (status code, message text, state), never "works correctly".
- Only test what the input describes. Do not invent features.
- Link each case to the acceptance criterion number it verifies."""


def build_request(source_text: str, model: str) -> dict:
    return {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": f"Write a complete, non-redundant set of test cases for this input:\n\n{source_text}",
        }],
        "output_config": {"format": {"type": "json_schema", "schema": TEST_CASE_SCHEMA}},
    }


def generate(source: Path, model: str) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    request = build_request(source.read_text(), model)
    # Server-side fallback: if the model declines, the API retries on a suitable model in the same call.
    response = client.beta.messages.create(
        **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if response.stop_reason == "refusal":
        sys.exit("The model declined this request; try rewording the input.")
    if response.stop_reason == "max_tokens":
        sys.exit("Output was cut off at max_tokens; split the input into smaller stories.")
    text = next(block.text for block in response.content if block.type == "text")
    cases = json.loads(text)["test_cases"]
    return {
        "source": str(source),
        "model": response.model,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "test_cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="user story (.md) or API spec excerpt")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, help="output JSON path")
    args = parser.parse_args(argv)

    result = generate(args.source, args.model)
    out = args.out or OUTPUT_DIR / f"{args.source.stem}.ai.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(result['test_cases'])} test cases to {out}")


if __name__ == "__main__":
    main()
