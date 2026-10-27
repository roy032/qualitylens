#!/usr/bin/env bash
# End-to-end check of QualityLens as a toolkit: scaffold a suite for a sample app with `qualitylens init`,
# run it against the healthy app (must pass), against a copy with seeded defects (each must be caught),
# and against a stopped app (must stop at once with the start hint). Needs qualitylens[ui] and Chromium.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
PORT=${PORT:-8765}
trap 'kill "${SERVER:-}" 2>/dev/null || true; rm -rf "$WORK"' EXIT

cp -r "$ROOT/examples/sample-app" "$WORK/app"
python -m http.server "$PORT" --bind 127.0.0.1 --directory "$WORK/app" >/dev/null 2>&1 &
SERVER=$!
for _ in $(seq 50); do curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 0.1; done

qualitylens init "$WORK/shop-qa" --url "http://127.0.0.1:$PORT" --health /health --name "Sample shop"
cd "$WORK/shop-qa"

echo "== doctor"
qualitylens doctor

echo "== healthy app: everything passes"
qualitylens run smoke --junit-dir results -- -q
qualitylens run full --record --label healthy -- -q
qualitylens flaky
qualitylens dashboard
test -s test-history/trends.html

echo "== seeded defects: each one is caught"
sed -i 's|<!-- DEFECTS -->|<a href="/gone.html">Old page</a><img src="/logo.png"><script>throw new Error("seeded")</script>|' \
  "$WORK/app/index.html"
set +e
qualitylens run full --junit-dir defects -- -q > defects.log 2>&1
status=$?
set -e
cat defects.log
[ "$status" -eq 1 ] || { echo "expected failures (exit 1), got exit $status"; exit 1; }
for test in test_home_page_has_no_console_errors test_no_broken_links_on_home_page \
            test_home_page_has_no_critical_accessibility_violations; do
  grep -q "FAILED tests/ui/test_pages.py::$test" defects.log || { echo "defect not caught by $test"; exit 1; }
done
grep -q "3 failed, 4 passed" defects.log || { echo "expected exactly 3 failures"; exit 1; }

echo "== app down: the run stops at once with the start hint"
kill "$SERVER"; wait "$SERVER" 2>/dev/null || true
set +e
qualitylens run smoke -- -q > down.log 2>&1
status=$?
set -e
cat down.log
[ "$status" -eq 3 ] && grep -q "Sample shop is not reachable" down.log || { echo "expected exit 3, got $status"; exit 1; }

echo "Toolkit self-test passed."
