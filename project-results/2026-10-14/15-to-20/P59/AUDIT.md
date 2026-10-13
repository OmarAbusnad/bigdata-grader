# P59 — forensic grading review (15–20 band)

- Previously awarded provisional score: **18.686/25**, not official final academic mark.
- Frozen source: https://github.com/abeeraun/midterm-data-pipeline/tree/33cb41e1fe
- Exact frozen SHA: `33cb41e1fe`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Grader sent only limit to order_id query, returned HTTP 400 missing order_id (#37), and omitted required name:Query(...) on /refresh-mv, returned HTTP 422 (#38). Other four query requests succeeded; jobs returned genuine HTTP 500 due ObjectId serialization, separate.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
