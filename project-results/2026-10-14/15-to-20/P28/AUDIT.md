# P28 — forensic grading review (15–20 band)

- Previously awarded provisional score: **17.567/25**, not official final academic mark.
- Frozen source: https://github.com/jalalengneer1-jalal/BigData_Hybrid_Pipeline/tree/20f40dafa7d78f3cecf428d24345ccc05a
- Exact frozen SHA: `20f40dafa7d78f3cecf428d24345ccc05a`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen FastAPI query route requires value for customer/city/status/quality, start/end for date; grader omitted all and got five HTTP 422. Confirmed invalid grader requests: issue #37.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
