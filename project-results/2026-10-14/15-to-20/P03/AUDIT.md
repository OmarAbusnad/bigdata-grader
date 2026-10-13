# P03 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.811/25**, not official final academic mark.
- Frozen source: https://github.com/Alqudimi/HybridOrderFlow/tree/3da60482902f1d76a4ae800247e6a9a9db9e075c
- Exact frozen SHA: `3da60482902f1d76a4ae800247e6a9a9db9e075c`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Observed cleaning/quarantine count discrepancies, Spark exit 1 and later upsert/incremental mismatches. Student-code root cause versus Spark environment still requires stderr review; no grader defect proven.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
