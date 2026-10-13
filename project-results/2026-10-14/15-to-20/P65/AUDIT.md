# P65 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.061/25**, not official final academic mark.
- Frozen source: https://github.com/mm7090mm7090-glitch/midterm-data-pipeline/tree/d2b3075c5
- Exact frozen SHA: `d2b3075c5`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen final API is api/main.py. Midterm Spark path returned exit 1, while batch validated=16706 and quarantined=3294. Source/oracle trace required before claiming grader defect or student error.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
