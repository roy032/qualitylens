# Security policy

## Reporting a problem in QualityLens

Please do not open a public issue. Use GitHub's private vulnerability reporting
(**Security > Report a vulnerability**) on this repository, or contact the owner, @roy032, directly.
Expect an answer within a week.

## Reporting a problem in Gitea

QualityLens tests Gitea; it is not part of it. Security issues in Gitea go to the Gitea project
following [its policy](https://github.com/go-gitea/gitea/security/policy). The defects documented in
`bug-reports/` are functional bugs that were checked against that policy before being written up.

## What the repository does to stay safe

- Dependencies are pinned in `requirements.txt`, audited on every push with `pip-audit`, and updated
  weekly by Dependabot (Python packages, GitHub Actions, the Docker base image).
- Every release carries a CycloneDX SBOM of the pinned dependencies.
- GitHub Actions are pinned to commit SHAs, and workflows run with read-only repository permissions
  unless a job needs more (Pages publishing, releases).
- The suite image runs as an unprivileged user.
- The credentials in `.env.example` and `docker-compose.yml` are for a throwaway local Gitea only. Never
  point the suite at a real server with them: set `QL_ADMIN_USER`, `QL_ADMIN_PASSWORD` and `QL_DB_DSN`
  through environment variables or CI secrets instead.
- The suite creates and deletes repositories, users and issues. Run it only against a Gitea instance
  that exists for testing.
