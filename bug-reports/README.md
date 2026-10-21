# Bug reports

Ten defects found in Gitea 1.22.6 while building this suite. Every one is reproducible from a clean
install with `python scripts/capture_evidence.py`, which writes the HTTP logs and screenshots in
[`evidence/`](evidence/), and each is pinned by an automated test marked `known_bug` (strict `xfail`):
the build stays green while the bug exists and turns red the moment it is fixed, so the test can be
promoted to a normal regression test.

| ID | Title | Severity | Priority | Found by | Regression test |
|---|---|---|---|---|---|
| [BUG-001](BUG-001-whitespace-issue-title.md) | API accepts a whitespace-only issue title and stores an empty title | Major | P2 | Manual boundary analysis | `test_issues_api.py::test_whitespace_title_rejected` |
| [BUG-002](BUG-002-issue-title-silent-truncation.md) | Issue titles over 255 characters are silently truncated | Major | P2 | Boundary value analysis | `test_issues_api.py::test_title_over_255_rejected` |
| [BUG-003](BUG-003-duplicate-label-names.md) | Duplicate label names are allowed in one repository | Minor | P3 | Exploratory API testing | `test_labels_api.py::test_duplicate_label_name_rejected` |
| [BUG-004](BUG-004-misleading-password-error.md) | Short password reported as "PasswordIsRequired" | Minor | P3 | Negative API testing | `test_users_api.py::test_short_password_error_message_is_accurate` |
| [BUG-005](BUG-005-unknown-state-filter-ignored.md) | Unknown `state` filter is silently ignored | Minor | P3 | Negative API testing | `test_issues_api.py::test_list_rejects_unknown_state` |
| [BUG-006](BUG-006-malformed-json-error.md) | Malformed JSON returns 422 with a misleading parser message | Trivial | P4 | Negative API testing | `test_issues_api.py::test_malformed_json_returns_400` |
| [BUG-007](BUG-007-whitespace-comment.md) | Whitespace-only comment is accepted and shown as an empty comment | Minor | P3 | **AI-generated case AI-19** | `test_issues_api.py::test_whitespace_comment_rejected` |
| [BUG-008](BUG-008-blank-milestone-title.md) | Milestones can be created with an empty or whitespace-only title | Minor | P3 | Negative API testing | `test_milestones_api.py::test_milestone_title_required` |
| [BUG-009](BUG-009-unknown-ids-silently-dropped.md) | Unknown milestone or label IDs are silently dropped on issue create | Minor | P3 | Negative API testing | `test_milestones_api.py::test_issue_with_unknown_reference_rejected` |
| [BUG-010](BUG-010-search-like-wildcards.md) | Search treats `%` and `_` as SQL wildcards | Minor | P3 | Security testing (SQL metacharacters) | `test_repos_api.py::test_search_treats_wildcards_literally` |

**Severity** is the impact on the user or data (Critical, Major, Minor, Trivial).
**Priority** is how soon it should be fixed (P1 now ... P4 when convenient).

## Triage (20 Oct 2026)

All ten are defects in Gitea's server, not in QualityLens: each test asserts the documented or reasonable
behaviour and the server answers differently. Nothing in this repository can fix them, so they stay pinned as
strict `xfail`. To see whether they are still open upstream, the suite and `capture_evidence.py` were re-run on
a clean install of the latest Gitea release, **28.2.0**
([evidence](evidence/gitea-28.2.0/)):

| ID | 1.22.6 | 28.2.0 | Status |
|---|---|---|---|
| BUG-001 | reproduces | reproduces | Open upstream |
| BUG-002 | reproduces | reproduces | Open upstream |
| BUG-003 | reproduces | reproduces | Open upstream |
| BUG-004 | reproduces | reproduces | Open upstream |
| BUG-005 | reproduces | reproduces | Open upstream |
| BUG-006 | reproduces | partly fixed | Message is now accurate (`unexpected EOF within "/title"`); status is still 422, not 400 |
| BUG-007 | reproduces | reproduces | Open upstream |
| BUG-008 | reproduces | reproduces | Open upstream (found 21 Oct 2026) |
| BUG-009 | reproduces | reproduces | Open upstream (found 21 Oct 2026) |
| BUG-010 | reproduces | reproduces | Open upstream (found 21 Oct 2026) |

The suite stays pinned to 1.22.6. On 28.2.0, 14 other tests fail. Most are version drift to handle in a
later upgrade: changed login and repository UI markup (10 UI tests) and changed status codes for duplicate
users (409 instead of 422) and reserved usernames (400 instead of 422). One looks like a **new candidate bug**:
`POST /api/v1/user/repos` with the name `..` returns `500 Internal Server Error` with a validation message,
where 1.22.6 returned 422. It is not filed as BUG-008 yet because the suite does not target 28.x.
Before filing anything upstream, search the [Gitea issue tracker](https://github.com/go-gitea/gitea/issues)
for duplicates.

Retest on any version:

```bash
make down
GITEA_VERSION=28.2.0 make up
pytest -m known_bug -rA                                        # XFAIL = still broken, XPASS = fixed
python scripts/capture_evidence.py bug-reports/evidence/gitea-28.2.0
```
