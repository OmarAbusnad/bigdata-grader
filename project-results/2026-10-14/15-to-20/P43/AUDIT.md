# P43 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.928/25**, not official final academic mark.
- Frozen source: https://github.com/shehabalawdy-png/Shehab_BigData_Pipeline/tree/cbbc33924c
- Exact frozen SHA: `cbbc33924c`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Grader invoked all 5 named queries with {} parameters, and each returned HTTP 400 Missing required parameter; endpoints exist in frozen src/phase2/api.py and need city/status/customer/date/min_total. Confirmed grader probe bug, issue #37.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
