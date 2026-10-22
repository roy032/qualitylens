# BUG-009: Unknown milestone or label IDs are silently dropped when creating an issue

| Field | Value |
|---|---|
| Severity | Minor |
| Priority | P3 |
| Component | REST API, `POST /api/v1/repos/{owner}/{repo}/issues` (`milestone`, `labels` fields) |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Negative API testing of the new milestone suite (TC-API-MILESTONE-05) |

## Steps to reproduce
1. `POST /api/v1/repos/qa_admin/<repo>/issues` with `{"title": "x", "milestone": 999999}`
2. `POST /api/v1/repos/qa_admin/<repo>/issues` with `{"title": "x", "labels": [999999]}`

## Expected result
`404` or `422` naming the unknown milestone or label, and no issue created, the same way
`GET .../milestones/999999` answers 404.

## Actual result
`201 Created`. The issue is created with `"milestone": null` or `"labels": []`; the bad reference
is dropped without any warning.

## Evidence
- [evidence/BUG-009.txt](evidence/BUG-009.txt)

## Impact
Integrations (importers, bots, CI tools) that send a stale or mistyped ID believe the issue was filed
under the right milestone or label. The mistake surfaces later as issues missing from release
reports and label filters.

## Regression test
`tests/api/test_milestones_api.py::test_issue_with_unknown_reference_rejected`
