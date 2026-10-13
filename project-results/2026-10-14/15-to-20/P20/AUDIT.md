# P20 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.783/25**, not official final academic mark.
- Frozen source: https://github.com/alfqyhalmtsm051-coder/Scalable_Orders_Data_Pipeline/tree/61537545b8
- Exact frozen SHA: `61537545b8`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
API exists at src/phase2/api.py. Grader universal env-example requirement affects final.dependencies though declared API deps exist. Other Spark/upsert failures require source-level causality, not assumption.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
