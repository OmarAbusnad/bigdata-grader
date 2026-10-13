# P39 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.861/25**, not official final academic mark.
- Frozen source: https://github.com/mushtaqalfaqih/BigData-Midterm-Pipeline/tree/ec844f735a
- Exact frozen SHA: `ec844f735a`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Upsert and incremental counts appeared negative in grading ledger (-16875, -917), which may reflect delta arithmetic rather than a negative MongoDB collection size. Must inspect grader calculation and student write path, not assume student error.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
