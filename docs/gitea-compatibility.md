# Gitea compatibility: 1.22.6 (pinned) vs 28.2.0

What would happen to this suite, and to users, if the project upgraded Gitea. Produced on 21 Oct 2026 by
running the whole suite (186 UI, API, DB, security and accessibility tests) against clean installs of both
versions and comparing the JUnit results with `scripts/compat_report.py`. The weekly
`gitea-compat.yml` workflow repeats this in CI and writes the same report to its run summary.

## Verdict

**Not ready to upgrade without work.** None of the ten known bugs is fixed in 28.2.0, one API call now
fails with a server error, and six screens gain accessibility violations. The other 16 differences are
the suite's own maintenance: Gitea changed its HTML, status codes and CSRF handling.

| Cause | Tests | What it means | Action |
|---|---:|---|---|
| Server error | 1 | `POST /user/repos` with name `..` returns **500** (1.22.6: 422 "name is reserved") | Report upstream; blocks the upgrade |
| New accessibility violations | 6 | `aria-prohibited-attr` on the new repository switcher and the dashboard heatmap; `link-in-text-block` on the new-repository form | Triage; add to the 28.x a11y baseline or report upstream |
| API status codes changed | 3 | Duplicate username/email now **409 Conflict**, reserved username **400** (all 422 before) | Arguably better; update the expected codes per version |
| CSRF moved out of the cookie | 3 | The `_csrf` cookie no longer exists, so tests that read the token from it fail | Rewrite to read the token from the page, then re-check that CSRF still blocks forged requests |
| UI markup drift | 10 | Error banners are now matched twice, repository header and issue list use new classes, logout keeps a `redirect_to` parameter, invalid repo names are rejected in the browser before submit | Update page objects (selectors live only in `pages/`) |

| Gitea | Tests | Passed | Failed | Known bug |
|---|---:|---:|---:|---:|
| 1.22.6 | 186 | 173 | 0 | 13 |
| 28.2.0 | 186 | 150 | 23 | 13 |

## Known bugs

All ten still reproduce on 28.2.0 (their strict xfail held on both versions).

| Bug | 1.22.6 | 28.2.0 |
|---|---|---|
| BUG-001 | reproduces | reproduces |
| BUG-002 | reproduces | reproduces |
| BUG-003 | reproduces | reproduces |
| BUG-004 | reproduces | reproduces |
| BUG-005 | reproduces | reproduces |
| BUG-006 | reproduces | reproduces |
| BUG-007 | reproduces | reproduces |
| BUG-008 | reproduces | reproduces |
| BUG-009 | reproduces | reproduces |
| BUG-010 | reproduces | reproduces |

## All 23 tests that behave differently

| Test | 1.22.6 | 28.2.0 |
|---|---|---|
| `tests/a11y/test_accessibility.py::test_signed_in_page_has_no_new_violations[chromium-dashboard]` | passed | failed |
| `tests/a11y/test_accessibility.py::test_signed_in_page_has_no_new_violations[chromium-issue-list]` | passed | failed |
| `tests/a11y/test_accessibility.py::test_signed_in_page_has_no_new_violations[chromium-issue]` | passed | failed |
| `tests/a11y/test_accessibility.py::test_signed_in_page_has_no_new_violations[chromium-new-issue]` | passed | failed |
| `tests/a11y/test_accessibility.py::test_signed_in_page_has_no_new_violations[chromium-new-repository]` | passed | failed |
| `tests/a11y/test_accessibility.py::test_signed_in_page_has_no_new_violations[chromium-repository-home]` | passed | failed |
| `tests/api/test_repos_api.py::test_invalid_repo_names[..-name is reserved [name: ..]]` | passed | failed |
| `tests/api/test_users_api.py::test_duplicate_email_is_case_insensitive` | passed | failed |
| `tests/api/test_users_api.py::test_duplicate_username_rejected` | passed | failed |
| `tests/api/test_users_api.py::test_username_validation[reserved]` | passed | failed |
| `tests/security/test_web_security.py::test_login_error_does_not_reveal_accounts` | passed | failed |
| `tests/security/test_web_security.py::test_session_cookies_are_httponly_and_samesite` | passed | failed |
| `tests/security/test_web_security.py::test_state_change_without_csrf_token_rejected` | passed | failed |
| `tests/ui/test_issues.py::test_issue_listed[chromium]` | passed | failed |
| `tests/ui/test_login.py::test_login_rejects_invalid_credentials[chromium-trailing-space-wrong-password]` | passed | failed |
| `tests/ui/test_login.py::test_login_rejects_invalid_credentials[chromium-unknown-user]` | passed | failed |
| `tests/ui/test_login.py::test_login_rejects_invalid_credentials[chromium-wrong-password]` | passed | failed |
| `tests/ui/test_login.py::test_logout[chromium]` | passed | failed |
| `tests/ui/test_repository.py::test_create_public_repo[chromium]` | passed | failed |
| `tests/ui/test_repository.py::test_duplicate_repo_name[chromium]` | passed | failed |
| `tests/ui/test_repository.py::test_invalid_repo_name[chromium-ends.git]` | passed | failed |
| `tests/ui/test_repository.py::test_invalid_repo_name[chromium-has space]` | passed | failed |
| `tests/ui/test_repository.py::test_invalid_repo_name[chromium-semi;colon]` | passed | failed |
