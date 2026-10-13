# P35 — forensic grading review (15–20 band)

- Previously awarded provisional score: **17.811/25**, not official final academic mark.
- Frozen source: https://github.com/mawdhq8q8112244-web/Bigdata-project/tree/084745c3c2
- Exact frozen SHA: `084745c3c2`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Source includes src/api.py, but results show 19750 validated/250 quarantined where oracle expected 17000/3000; unique index not evidenced. These are observed discrepancies needing business rule reconciliation.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
