# BUG-001: API accepts a whitespace-only issue title and stores an empty title

| Field | Value |
|---|---|
| Severity | Major (data integrity: creates issues with no title that cannot be clicked in the list) |
| Priority | P2 |
| Component | REST API, `POST /api/v1/repos/{owner}/{repo}/issues` |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Manual case TC-ISSUE-03 (whitespace is a classic equivalence class for "required" fields) |

## Preconditions
A repository exists and the caller is authenticated (any user who may open issues).

## Steps to reproduce
1. `POST /api/v1/repos/qa_admin/<repo>/issues` with body `{"title": "   "}` (three spaces).
2. `GET` the issue that was created.
3. Open `/qa_admin/<repo>/issues` in the browser.

## Expected result
Request rejected with `422` and a validation message, exactly as the web UI does for the same input
("Title cannot be empty") and as the API does for `""`.

## Actual result
- `201 Created`. The title is trimmed **after** validation, so the stored title is `""`.
- The issue list shows a row with no title text, so there is nothing to click on to open it (see screenshot).

## Evidence
- [evidence/BUG-001.txt](evidence/BUG-001.txt): request/response log
- ![issue list with blank title](evidence/BUG-001.png)

## Impact
Any API client or integration (CI bots, importers) can create untitled issues. They clutter the tracker,
break search and notifications, and the UI and API disagree on the same rule.

## Suggested fix
Trim the title before the `Required` check in the API form binding, as the web handler already does.

## Regression test
`tests/api/test_issues_api.py::test_whitespace_title_rejected`
