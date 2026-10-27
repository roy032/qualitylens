# BUG-012: Editing an issue title skips the rules applied on create

| Field | Value |
|---|---|
| Severity | Minor |
| Priority | P3 |
| Component | REST API, `PATCH /api/v1/repos/{owner}/{repo}/issues/{index}` |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Also reproduces on 28.2.0. |
| Found by | Model-based testing: `test_issue_lifecycle_matches_model` (Hypothesis state machine) found that an edited title no longer matched the model |

## Steps to reproduce
1. `POST .../issues` with `{"title": "  padded  "}`: stored as `padded`.
2. `PATCH .../issues/<n>` with `{"title": "  padded  "}`.
3. `PATCH .../issues/<n>` with `{"title": "   "}`.

## Expected result
Edit applies the same rules as create: the title is trimmed (step 2 stores `padded`), and a blank title is
rejected with `422` (step 3), as `POST` rejects an empty title.

## Actual result
Step 2 stores `"  padded  "` with the spaces, and step 3 is accepted: the issue's title becomes three spaces,
which shows as a blank row in the issue list (the same symptom as BUG-001, reached by a different route).
An empty string `""` is silently ignored (title unchanged, still `201`). A title over 255 bytes is cut to
252 bytes plus `…`, which is a different truncation from the one on create (BUG-002).

## Evidence
- [evidence/BUG-012.txt](evidence/BUG-012.txt) (1.22.6), [evidence/gitea-28.2.0/BUG-012.txt](evidence/gitea-28.2.0/BUG-012.txt)

## Impact
Validation that only runs on create can be bypassed by creating a valid issue and editing it. Leading and
trailing spaces also make issues harder to find by exact title and sort them inconsistently.

## Regression test
`tests/api/test_properties.py::test_edit_title_follows_create_rules`
