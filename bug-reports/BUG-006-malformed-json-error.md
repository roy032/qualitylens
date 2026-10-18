# BUG-006: Malformed JSON returns 422 with a misleading parser message

| Field | Value |
|---|---|
| Severity | Trivial |
| Priority | P4 |
| Component | REST API request binding (seen on `POST .../issues`) |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Negative API testing (broken request bodies) |

## Steps to reproduce
1. `POST /api/v1/repos/qa_admin/<repo>/issues` with header `Content-Type: application/json` and the
   truncated body `{"title":`

## Expected result
`400 Bad Request` with a message such as "request body is not valid JSON".

## Actual result
`422` with `[]: invalid character '\u0000' looking for beginning of value`. The body contains no NUL
character, so the message points the developer at a problem that does not exist.

## Evidence
[evidence/BUG-006.txt](evidence/BUG-006.txt)

## Impact
Low: only affects developers of API clients, but slows down debugging.

## Regression test
`tests/api/test_issues_api.py::test_malformed_json_returns_400`
