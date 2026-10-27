## What changes

<!-- One or two sentences: what and why. Link the issue or bug report. -->

## How it was tested

- [ ] `qualitylens run unit` (offline) passes
- [ ] `qualitylens run impacted` (or the affected layers) passes against a local Gitea
- [ ] `ruff check .` and `mypy` are clean (pre-commit runs both)

## Checklist

- [ ] New or changed manual cases are traced in `test-cases/manual_test_cases.csv`
- [ ] A new Gitea defect has a report in `bug-reports/` and a `known_bug` strict-xfail test
- [ ] A quarantined test has an owner, a reason and an expiry in `quarantine.toml`
- [ ] Visual baselines changed on purpose only (diff reviewed)
- [ ] `CHANGELOG.md` updated for user-visible changes
