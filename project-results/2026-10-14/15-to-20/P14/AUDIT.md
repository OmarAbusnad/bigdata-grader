# P14 — forensic grading review (15–20 band)

- Previously awarded provisional score: **18.561/25**, not official final academic mark.
- Frozen source: https://github.com/RyadAbdullahAlshwish/hybrid-elt-bigdata-pipeline/tree/5ace7400b9
- Exact frozen SHA: `5ace7400b9`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen API exists. Spark returned code 1 and batch quarantine differs from Oracle; Audit samples 9/18. Cause must be rooted in source vs isolated dependency errors.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
