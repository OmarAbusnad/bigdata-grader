# P08 — forensic grading review (15–20 band)

- Previously awarded provisional score: **16.467/25**, not official final academic mark.
- Frozen source: https://github.com/Nabelhossensalh/-data_pipeline-/tree/dff0bbf63e
- Exact frozen SHA: `dff0bbf63e`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen final API is under final_extension/src/final/api.py (not repository root). Midterm required manual review. Final indexes count=1, manual-job requests 0/2: determine failure from status/body, not merely count.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
