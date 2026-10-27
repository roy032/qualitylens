# Changelog

All notable changes to QualityLens. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/). A release is cut with the
[Release workflow](.github/workflows/release.yml), which uses the section below as its notes.

## [2.0.0] - unreleased

### Added
- Reusable engine: `qualitylens.toml` describes the app under test (URL, health check, login, database,
  layers, profiles, impact rules, history and flaky settings), so the engine runs any pytest suite.
- `qualitylens init`: scaffolds a ready-to-run suite for any web app or HTTP API (API and browser
  baselines, accessibility, CI workflow with history and flaky tracking). Guide: `docs/toolkit.md`.
- `qualitylens.http.ApiClient` and the plugin fixtures `api` and `ql_project`; the plugin stops a run
  with the start hint when the app is down, for any project.
- `qualitylens summary | load-trend | compat | mutation-score` (were `scripts/*.py`).
- CI job "toolkit": the scaffolded suite must pass on a sample app, catch seeded defects and stop when
  the app is down.
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
- **Breaking:** Gitea-specific modules moved from `qualitylens` to `suite` (`config`, `api_client`, `data`,
  `db`, `oracles`, `schemas`); `qualitylens.api_client.GiteaApi` is now `suite.api_client.GiteaApi`.
- The package installs only `pytest` and `requests`; browser, visual and database support are the extras
  `ui`, `visual` and `db` (`all` for everything).
- `doctor` checks what `qualitylens.toml` configures instead of a fixed Gitea list.
- CI jobs run with read-only repository permissions by default.
- `pytest -m unit` (and `make unit`) now works without a running Gitea.

### Fixed
- The feature table in the README had two rows merged into it by mistake.

## [1.0.0] - 2026-10-22

First complete version: 86 traced manual cases; UI, API, database, security, accessibility and visual
automation against Gitea 1.22.6; ten confirmed Gitea bugs pinned with strict xfail; coverage and
mutation gates; parallel CI with Allure history; load test with SLO thresholds; AI test-case generator
measured against the manual suite; Gitea 28.x compatibility report.
