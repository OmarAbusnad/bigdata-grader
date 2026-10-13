# P54 — forensic grading review (15–20 band)

- Previously awarded provisional score: **18.686/25**, not official final academic mark.
- Frozen source: https://github.com/shughaq/data-pipeline-main-BIGDATA/tree/81d9b76c45
- Exact frozen SHA: `81d9b76c45`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Student sales_by_period query needs start/end, grader sent only limit and got HTTP 400; other four query calls returned 200. Malformed grader request issue #37, not proof of failed student query. Separate batch engine selection differs.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
