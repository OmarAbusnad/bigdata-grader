# P24 — forensic grading review (15–20 band)

- Previously awarded provisional score: **18.329/25**, not official final academic mark.
- Frozen source: https://github.com/mohsenalfahed2026-sketch/Sagralbrsh/tree/2ea070985b82edf2cd560d188b1b2a4d410f9df2
- Exact frozen SHA: `2ea070985b82edf2cd560d188b1b2a4d410f9df2`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38317234359

## Attribution and source inspection
Use late-submitted frozen repo, not earlier cdvgf82-sys entry. Frozen API returns 500 for /ingest and both manual job runs; these are observed student runtime responses. Grader env-example is a separate policy issue.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
