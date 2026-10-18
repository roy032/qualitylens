# Bug reports

Seven defects found in Gitea 1.22.6 while building this suite. Every one is reproducible from a clean
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

**Severity** is the impact on the user or data (Critical, Major, Minor, Trivial).
**Priority** is how soon it should be fixed (P1 now ... P4 when convenient).

Status of all seven: confirmed locally on 1.22.6. Before filing upstream, search the
[Gitea issue tracker](https://github.com/go-gitea/gitea/issues) for duplicates and retest on the latest release.
