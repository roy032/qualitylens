"""Shared shape of a test case, used by the generator (as the output schema) and the evaluator."""

CASE_TYPES = ["Positive", "Negative", "Boundary", "Security"]

TEST_CASE_SCHEMA = {
    "type": "object",
    "properties": {
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "AI-<n>"},
                    "title": {"type": "string"},
                    "type": {"type": "string", "enum": CASE_TYPES},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "preconditions": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "test_data": {"type": "string"},
                    "expected_result": {"type": "string"},
                    "acceptance_criterion": {"type": "integer",
                                             "description": "Number of the acceptance criterion this case verifies, 0 if none"},
                },
                "required": ["id", "title", "type", "priority", "preconditions", "steps",
                             "test_data", "expected_result", "acceptance_criterion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["test_cases"],
    "additionalProperties": False,
}
