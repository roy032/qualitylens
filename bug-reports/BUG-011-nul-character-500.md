# BUG-011: A NUL character in text input crashes six endpoints with a 500 and leaks the database error

| Field | Value |
|---|---|
| Severity | Major (unhandled server error on ordinary write and search endpoints; internal error text returned to the client) |
| Priority | P2 |
| Component | REST API: issues, comments, milestones, labels, repository search; web: `/explore/repos` |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Also reproduces on 28.2.0. |
| Found by | Property-based testing (Hypothesis): `test_issue_title_stored_as_trimmed_input` shrank a failing title to one containing `\x00` |

## Steps to reproduce
1. `POST /api/v1/repos/qa_admin/<repo>/issues` with body `{"title": "before\u0000after"}`.
2. Repeat with the character in an issue body, a comment, a milestone title, a label name.
3. `GET /api/v1/repos/search?q=before%00after`, or open `/explore/repos?q=a%00b` in a browser.

## Expected result
`422 Unprocessable Entity` (or `400`) with a validation message, the same as for any other invalid input.
Nothing is stored.

## Actual result
Every request returns `500 Internal Server Error` with the PostgreSQL driver's message in the body:

```
{"message":"newIssue: pq: invalid byte sequence for encoding \"UTF8\": 0x00", ...}
{"ok":false,"error":"Count: pq: invalid byte sequence for encoding \"UTF8\": 0x00"}
```

PostgreSQL `text` columns cannot hold U+0000, and Gitea passes the value through without checking it.
Other control characters (U+0001 to U+001F) are accepted and stored, which shows the gap is NUL specifically.
The issue search endpoint (`/repos/issues/search`) is the exception: it answers `200` with no results.

## Evidence
- [evidence/BUG-011.txt](evidence/BUG-011.txt) (1.22.6), [evidence/gitea-28.2.0/BUG-011.txt](evidence/gitea-28.2.0/BUG-011.txt)

## Impact
- Any client that forwards user text unfiltered (an importer, a bot, a CI integration) gets a server error
  instead of a validation error it could show to the user.
- The response discloses the database driver (`pq`) and the internal function name (`newIssue`), which
  helps an attacker fingerprint the stack. Error responses should be generic, with details only in the log.
- Each request writes an error-level log entry, so it is a cheap way to flood the server log.
- On MySQL or SQLite the same input is probably stored, so behaviour depends on the database: worth
  checking before an upstream report.

## Regression test
`tests/api/test_properties.py::test_nul_character_rejected_cleanly` (one case per endpoint)
