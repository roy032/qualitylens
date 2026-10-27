# Load testing

`locustfile.py` simulates people using the issue tracker: mostly reading (issue list, repository,
search, the HTML issues page) and sometimes creating issues. Weights are 5:3:2:1:1.

The run **fails** (exit code 1, so CI goes red) when either service-level objective is broken:

| SLO | Default | Override |
|---|---|---|
| Error rate | at most 1 % | `QL_MAX_FAILURE_RATIO` |
| 95th percentile response time | at most 800 ms | `QL_MAX_P95_MS` |

## Baseline (13 Oct 2026)

60 s, 20 users, spawn rate 5/s, Gitea 1.22.6 + PostgreSQL 16 in Docker on a 4 vCPU / 16 GB Linux VM.

| Endpoint | Requests | Failures | Median | p95 |
|---|---|---|---|---|
| GET /issues (API, 20 per page) | 348 | 0 | 130 ms | 210 ms |
| GET /repo | 225 | 0 | 32 ms | 70 ms |
| GET /repos/search | 144 | 0 | 35 ms | 72 ms |
| GET issues page (HTML) | 78 | 0 | 48 ms | 140 ms |
| POST /issues | 60 | 0 | 85 ms | 180 ms |
| **All** | **855** | **0 %** | **69 ms** | **180 ms** |

Observation: the issue-list API is about 4x slower than reading a repository even with only a few dozen
issues. It is the endpoint to watch first if the data set grows; a follow-up run with 10,000 seeded issues
would show whether it scales with the number of issues.

## CI

GitHub's shared runners are slower and noisier than the baseline VM: on 21 Oct 2026 runs of the same
commit measured p95 between 720 and 860 ms, driven by `GET /issues` (p95 1.4 to 1.6 s, slowing as the
scenario keeps adding issues). The CI job therefore sets `QL_MAX_P95_MS=1200`, which still fails on a
~1.5x slowdown there; local runs keep 800 ms.

Results land in `load/results/` (CSV per endpoint and an HTML report); CI uploads them as an artifact.

## Trend

The fixed SLO only catches a large slowdown. After every CI run, `qualitylens load-trend` compares each
endpoint's p95 with the median of the previous runs (kept in the Actions cache, up to 30) and writes the
table and a sparkline of the overall p95 to the job summary. The job fails when the overall p95 is more
than 50 % above that median; with fewer than three earlier runs it only reports. `make load` does the same
locally with `load/history/history.json`.
