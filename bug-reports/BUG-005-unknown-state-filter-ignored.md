# BUG-005: Unknown `state` filter is silently ignored

| Field | Value |
|---|---|
| Severity | Minor |
| Priority | P3 |
| Component | REST API, `GET /api/v1/repos/{owner}/{repo}/issues` |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Negative testing of query parameters (TC-ISSUE-16) |

## Steps to reproduce
1. `GET /api/v1/repos/qa_admin/<repo>/issues?state=bogus`

## Expected result
`422` listing the allowed values (`open`, `closed`, `all`).

## Actual result
`200` with the open issues, as if `state` had not been sent. The same value on
`PATCH .../issues/{n}` is rejected (`412 unknown state: bogus`), so the API is inconsistent with itself.

## Evidence
[evidence/BUG-005.txt](evidence/BUG-005.txt)

## Impact
A typo such as `state=close` returns open issues; a report or script built on it shows wrong numbers
with no error.

## Regression test
`tests/api/test_issues_api.py::test_list_rejects_unknown_state`
