# P64 — forensic grading review (15–20 band)

- Previously awarded provisional score: **18.861/25**, not official final academic mark.
- Frozen source: https://github.com/mod33tr/data-pipeline_by_pyspark_and_python_batch/tree/12f24f2fcf
- Exact frozen SHA: `12f24f2fcf`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Student FastAPI source contains jobs endpoint, but both manual-run calls returned HTTP 500; an observed runtime failure, not evidence of missing grader name parsing. MV/index explain has valid static evidence. Needs exception traceback.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
