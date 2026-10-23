# Contributing

## Set up

Needs Docker and Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
make install-dev      # dependencies, the qualitylens command, Chromium, lint tools, pre-commit hooks
make up               # Gitea + PostgreSQL in Docker, admin user created
qualitylens doctor    # every line should be ✓
```

No Python at all? `make docker` builds the suite image; `docker run --rm --network host qualitylens doctor`.

## The loop

```bash
qualitylens run impacted          # only the layers your branch can affect (vs origin/main)
qualitylens run unit -- -x        # anything after -- goes to pytest
make lint                         # ruff, mypy, quarantine check (pre-commit runs these on commit)
```

`qualitylens impact -v` shows why each changed file selected the layers it did. Shared code (fixtures,
the API client, dependencies, CI) selects everything; CI always runs the whole suite regardless.

## Adding a test

1. Write the manual case in `test-cases/manual_test_cases.csv` and name the automated test that covers
   it in the `Automated Test` column. `tests/unit/test_traceability.py` fails if that test is missing.
2. Put selectors in a Page Object under `pages/`, not in the test.
3. Create data through the API fixtures (`repo`, `issue`, `temp_user`) so the test is independent and
   cleans up after itself.
4. Assert exact status codes and messages.
5. Mark the layer (`ui`, `api`, `db`, ...). A test that scans the whole database also gets `serial`.

## Found a Gitea bug?

Write a report in `bug-reports/` (copy an existing one), add its reproduction to
`scripts/capture_evidence.py`, and pin it with a test marked `known_bug` and
`xfail(strict=True, reason="BUG-0NN: ...")`. The build stays green while the bug exists and fails the
day Gitea fixes it, which is the signal to turn it into a normal regression test.

## Flaky tests

A flaky test fails the build at random, so people learn to re-run until green and stop trusting red.
QualityLens never retries. Instead:

1. **Detect.** Every e2e run in CI is added to the test history. `qualitylens flaky` (in the job summary)
   lists tests whose outcome flips in at least 10 % of consecutive runs over at least 10 runs. The weekly
   `flake-hunt.yml` repeats the suite on one commit to catch flakiness faster.
2. **Quarantine.** Open a "Flaky test" issue and add the test to `quarantine.toml` with the issue link,
   an owner and an expiry at most 30 days ahead. Quarantined tests still run in CI, in a step that cannot
   fail the build, so their history keeps being recorded.
3. **Fix.** Find the race (usually a missing wait, shared data or ordering between parallel workers), fix
   it, and remove the entry. `qualitylens quarantine check` fails CI once an entry expires, so a quarantine
   is never permanent by accident.

## Quality gates

| Gate | Where | Fails when |
|---|---|---|
| Ruff | lint job, pre-commit | lint or import-order error |
| Mypy | lint job, pre-commit | type error in `qualitylens/`, `scripts/`, `ai/` |
| pip-audit | lint job | a pinned dependency has a known vulnerability |
| Quarantine check | lint job, pre-commit | expired, ownerless or dangling quarantine entry |
| Package build | lint job | the wheel does not build or its CLI does not start |
| Coverage | unit job | framework branch coverage under 90 % |
| Mutation | mutation job | mutation score under 90 % |
| E2E | e2e, cross-browser, visual jobs | unexpected failure, or a known bug starts passing |
| Load | load job | errors over 1 %, p95 over the SLO, or 50 % slower than recent runs |

## Pull requests

Keep them small and focused, fill in the template, and update `CHANGELOG.md` for anything a user of the
suite would notice. Dependabot opens weekly update PRs; they go through the same gates.

## Releases

Bump `__version__` in `qualitylens/__init__.py`, move the `CHANGELOG.md` section from "unreleased" to
the date, merge, then run **Actions > Release > Run workflow** with the version (for example `v1.1.0`).
The workflow runs the unit suite, builds the package and an SBOM, creates the tag and publishes the
GitHub release with the changelog section as notes.
