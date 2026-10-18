# BUG-004: Short password reported as "PasswordIsRequired"

| Field | Value |
|---|---|
| Severity | Minor (misleading error) |
| Priority | P3 |
| Component | REST API, `POST /api/v1/admin/users` |
| Environment | Gitea 1.22.6 (Docker image `gitea/gitea:1.22.6`) + PostgreSQL 16, see `docker-compose.yml`. Chromium 141 via Playwright 1.56 for UI steps. |
| Found by | Negative testing of the password rule (compare TC-REG-02 in the UI) |

## Steps to reproduce
1. As an admin, `POST /api/v1/admin/users` with a valid username and email and `"password": "Ab1!"`.

## Expected result
`422` (or 400) with a message that names the rule, as the sign-up page does:
"Password length cannot be less than 8 characters."

## Actual result
`400` with `{"message": "PasswordIsRequired"}`, the same response as when no password is sent at all.

## Evidence
[evidence/BUG-004.txt](evidence/BUG-004.txt)

## Impact
Admins and provisioning scripts are told the password is missing when it is present, and spend time
debugging the wrong thing. It is also a raw translation key, not a human-readable message.

## Regression test
`tests/api/test_users_api.py::test_short_password_error_message_is_accurate`
