# BUG-002: Issue titles over 255 characters are silently truncated

| Field | Value |
|---|---|
| Severity | Major (silent data loss) |
| Priority | P2 |
| Component | REST API, `POST /api/v1/repos/{owner}/{repo}/issues` |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Boundary value analysis on the 255-character limit (TC-ISSUE-05) |

## Preconditions
A repository exists; caller is authenticated.

## Steps to reproduce
1. `POST` an issue whose title is 256 characters (`"x" * 256`).
2. `GET` the created issue and measure the title.

## Expected result
`422` with a message that the title is too long. The web form already enforces `maxlength=255`,
and the database column is `varchar(255)`.

## Actual result
`201 Created`. The stored title is 253 characters: the first 252 characters plus `…`.
The client is never told that its data was changed.

## Evidence
[evidence/BUG-002.txt](evidence/BUG-002.txt)

## Impact
Integrations that sync titles from other systems (Jira, e-mail) lose text without any signal, and a later
sync compares unequal titles and may loop.

## Suggested fix
Validate length in the API (`binding:"MaxSize(255)"`) and return 422 instead of truncating.

## Regression test
`tests/api/test_issues_api.py::test_title_over_255_rejected`
