# Examples

`sample-app/` is a tiny static site used by `scripts/toolkit_selftest.sh` (CI job "Toolkit self-test"):
QualityLens scaffolds a fresh suite for it with `qualitylens init`, the suite must pass on the healthy
site, and must fail on exactly the defects seeded into it (a broken link, a JavaScript error and an
image without alt text).
