# BUG-010: Search treats `%` and `_` as SQL wildcards

| Field | Value |
|---|---|
| Severity | Minor |
| Priority | P3 |
| Component | Search: `GET /api/v1/repos/search`, `GET /api/v1/users/search` (and the explore pages that use them) |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Security testing: SQL metacharacter probes (TC-SEC-WEB-05) |

## Steps to reproduce
1. Create repositories `wild-<x>`, `wild-<y>` and `plain-<z>`.
2. `GET /api/v1/repos/search?q=w_ld`
3. `GET /api/v1/repos/search?q=%`

## Expected result
The keyword is matched literally: no repository name contains `w_ld` or `%`, so both return no results.

## Actual result
`w_ld` returns both `wild-` repositories and `%` returns every repository: the keyword is pasted into a
SQL `LIKE` pattern without escaping `%` and `_`. User search behaves the same way.

This is **not** SQL injection: quotes, `UNION` and comment sequences are handled safely
(`tests/security/test_web_security.py::test_search_handles_sql_metacharacters`), and private
repositories never appear for users without access, even with wildcards
(`tests/security/test_authorization.py::test_private_repo_not_in_search_results`).

## Evidence
- [evidence/BUG-010.txt](evidence/BUG-010.txt)

## Impact
Wrong search results for names containing `_`, a common character in repository and user names
(`my_project` also matches `myXproject`). A leading `%` forces a full table scan, so one cheap
request can make search slow on a large instance.

## Regression test
`tests/api/test_repos_api.py::test_search_treats_wildcards_literally`
