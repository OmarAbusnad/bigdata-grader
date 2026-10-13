# P11 — forensic grading review (15–20 band)

- Previously awarded provisional score: **18.385/25**, not official final academic mark.
- Frozen source: https://github.com/Osa2Sa3/hybrid-data-pipeline1/tree/e22f5a21d3
- Exact frozen SHA: `e22f5a21d3`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen API present. Ingest returned HTTP 500 and cleaning/upsert expected counts not met. Aggregation 5 HTTP 2xx but only 4 meaningful: partial evidence, do not claim complete fail.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
