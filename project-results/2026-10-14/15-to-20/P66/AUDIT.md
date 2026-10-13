# P66 — forensic grading review (15–20 band)

- Previously awarded provisional score: **15.136/25**, not official final academic mark.
- Frozen source: https://github.com/nwr456023-code/BigData_Phase2/tree/eab8fa34c8
- Exact frozen SHA: `eab8fa34c8`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen project tree has src/engine/main.py, but no discoverable FastAPI app source and requirements do not declare fastapi/uvicorn. The final API coverage gap is student submission-side; additional midterm output mismatch 19250 valid/750 quarantine. Human discussion not autograded.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
