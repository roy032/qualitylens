# Changelog

All notable changes to QualityLens. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/). A release is cut with the
[Release workflow](.github/workflows/release.yml), which uses the section below as its notes.

## [1.1.0] - unreleased

### Added
- `qualitylens` command (`pip install -e .`, or `python -m qualitylens`): `doctor`, `run <profile>`,
  `impact`, `history add`, `flaky`, `quarantine check`, `dashboard`.
- Test history across CI runs and flaky-test scoring by outcome flip rate; flaky tests are listed in the
  job summary on every e2e run.
- Flaky-test quarantine (`quarantine.toml`): listed tests run in a non-blocking step, every entry has an
  owner, a reason and an expiry of at most 30 days, enforced in CI.
- Trends dashboard (`trends.html`): failures per run, suite time, flaky, failing and slowest tests;
  uploaded as the `test-trends` artifact and published next to the Allure report.
- Test impact selection: `qualitylens impact` and `qualitylens run impacted` run only the layers a change
  can affect.
- Packaging (`pyproject.toml`), a suite container image (`Dockerfile`) and a CI job that builds and
  self-tests it.
- Lint job: ruff, mypy, pip-audit against known vulnerabilities, quarantine validity, package build.
- Release workflow: tag, GitHub release, wheel and CycloneDX SBOM from one button.
- Dependabot for pip, GitHub Actions and Docker; pre-commit hooks; contributing guide, security policy,
  issue and pull request templates, CODEOWNERS.
- Property-based and state-machine API tests (Hypothesis), BUG-011 and BUG-012, cross-browser UI runs
  (Firefox, WebKit), load trend tracking and the weekly deep-fuzz workflow (PR #4).

### Changed
- CI jobs run with read-only repository permissions by default.
- `pytest -m unit` (and `make unit`) now works without a running Gitea.

### Fixed
- The feature table in the README had two rows merged into it by mistake.

## [1.0.0] - 2026-10-22

First complete version: 86 traced manual cases; UI, API, database, security, accessibility and visual
automation against Gitea 1.22.6; ten confirmed Gitea bugs pinned with strict xfail; coverage and
mutation gates; parallel CI with Allure history; load test with SLO thresholds; AI test-case generator
measured against the manual suite; Gitea 28.x compatibility report.
