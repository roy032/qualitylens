"""JSON Schemas for the Gitea API responses the suite depends on.

These are contracts, not copies of the swagger file: they list the fields our tests
and a typical client rely on, with their types. A schema failure means the API shape
changed (renamed field, null where a value is promised), which breaks clients even
when the status code is still 200.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

# Patterns instead of `format`, because jsonschema only checks formats when optional extra packages are installed.
TIMESTAMP = {"type": "string", "pattern": r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(Z|[+-]\d\d:\d\d)$"}
NULLABLE_TIMESTAMP = {"anyOf": [{"type": "null"}, TIMESTAMP]}
URL = {"type": "string", "pattern": "^https?://"}

USER = {
    "type": "object",
    "required": ["id", "login", "email", "avatar_url", "html_url", "is_admin", "active", "created", "visibility"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "login": {"type": "string", "minLength": 1},
        "email": {"type": "string"},
        "avatar_url": URL,
        "html_url": URL,
        "is_admin": {"type": "boolean"},
        "active": {"type": "boolean"},
        "created": TIMESTAMP,
        "visibility": {"enum": ["public", "limited", "private"]},
    },
}

REPOSITORY = {
    "type": "object",
    "required": ["id", "name", "full_name", "owner", "private", "empty", "default_branch",
                 "html_url", "clone_url", "open_issues_count", "created_at", "updated_at", "permissions"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "name": {"type": "string", "minLength": 1},
        "full_name": {"type": "string", "pattern": "^[^/]+/[^/]+$"},
        "owner": USER,
        "private": {"type": "boolean"},
        "empty": {"type": "boolean"},
        "default_branch": {"type": "string"},
        "html_url": URL,
        "clone_url": URL,
        "open_issues_count": {"type": "integer", "minimum": 0},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "permissions": {
            "type": "object",
            "required": ["admin", "push", "pull"],
            "properties": {k: {"type": "boolean"} for k in ("admin", "push", "pull")},
        },
    },
}

LABEL = {
    "type": "object",
    "required": ["id", "name", "color", "description", "url"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "name": {"type": "string", "minLength": 1},
        "color": {"type": "string", "pattern": "^[0-9a-f]{6}$"},  # stored without the leading '#'
        "description": {"type": "string"},
        "url": URL,
    },
}

MILESTONE = {
    "type": "object",
    "required": ["id", "title", "state", "open_issues", "closed_issues", "due_on"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "title": {"type": "string"},
        "state": {"enum": ["open", "closed"]},
        "open_issues": {"type": "integer", "minimum": 0},
        "closed_issues": {"type": "integer", "minimum": 0},
        "due_on": NULLABLE_TIMESTAMP,
    },
}

ISSUE = {
    "type": "object",
    "required": ["id", "number", "title", "body", "state", "user", "labels", "milestone",
                 "comments", "created_at", "updated_at", "closed_at", "html_url", "repository"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "number": {"type": "integer", "minimum": 1},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "state": {"enum": ["open", "closed"]},
        "user": USER,
        "labels": {"type": "array", "items": LABEL},
        "milestone": {"oneOf": [{"type": "null"}, MILESTONE]},
        "comments": {"type": "integer", "minimum": 0},
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "closed_at": NULLABLE_TIMESTAMP,
        "html_url": URL,
        "repository": {
            "type": "object",
            "required": ["id", "name", "owner", "full_name"],
        },
    },
}

COMMENT = {
    "type": "object",
    "required": ["id", "body", "user", "html_url", "issue_url", "created_at", "updated_at"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "body": {"type": "string"},
        "user": USER,
        "html_url": URL,
        "issue_url": URL,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    },
}

ERROR = {
    "type": "object",
    "required": ["message", "url"],
    "properties": {"message": {"type": "string", "minLength": 1}, "url": URL},
}


def list_of(schema: dict) -> dict:
    return {"type": "array", "items": schema}


def contract_errors(instance, schema: dict) -> list[str]:
    """Every way `instance` breaks `schema`, as readable 'path: problem' lines (empty list = valid)."""
    validator = Draft202012Validator(schema)
    return sorted(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
                  for e in validator.iter_errors(instance))
