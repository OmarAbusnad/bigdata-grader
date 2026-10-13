# P01 — forensic grading review (15–20 band)

- Previously awarded provisional score: **17.486/25**, not official final academic mark.
- Frozen source: https://github.com/6980-rehab/midterm-data-pipeline-/tree/c43aae3d5e9c0d96731640206752f886f2618497
- Exact frozen SHA: `c43aae3d5e9c0d96731640206752f886f2618497`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38424927615

## Attribution and source inspection
/queries/orders_in_period was called without start/end, API returned 400; four other named queries returned 200. Same-SHA verified successes retained. Issue #37.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
