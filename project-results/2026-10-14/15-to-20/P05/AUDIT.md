# P05 — forensic grading review (15–20 band)

- Previously awarded provisional score: **17.486/25**, not official final academic mark.
- Frozen source: https://github.com/HashemHobireh/hybrid-elt-data-pipeline/tree/a4544a31f9
- Exact frozen SHA: `a4544a31f9`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen src/api.py implements FastAPI; archived final startup result was blocked. Need exact original missing import or startup traceback before attributing the final startup to student or grader; preserve same-SHA PASS.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
