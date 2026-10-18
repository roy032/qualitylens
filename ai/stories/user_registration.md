# User story: Register an account

As a visitor, I want to create an account with a username, email and password,
so that I can sign in and collaborate on repositories.

## Acceptance criteria
1. Registration form: username, email, password, confirm password.
2. Username: required, unique (case-insensitive), at most 40 characters, letters/digits/dash/underscore/dot only, not a reserved word (e.g. "api", "admin").
3. Email: required, valid format, unique (case-insensitive).
4. Password: at least 8 characters; password and confirmation must match.
5. On success the user is signed in, sees a confirmation message, and the password is stored hashed.
6. Error messages must say which field is wrong.

## Interfaces
- UI: /user/sign_up
- API (admin): POST /api/v1/admin/users  body: {"username", "email", "password", "must_change_password"}
