# P04 — forensic grading review (15–20 band)

- Previously awarded provisional score: **17.611/25**, not official final academic mark.
- Frozen source: https://github.com/Hafsa-Alazazi/Data_pipeline/tree/f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda
- Exact frozen SHA: `f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Spark console evidence explicitly shows missing Maven repositories and unresolved MongoDB Spark connector in isolated grader environment; grader infrastructure blocker, not student FAIL. Separate cleaning results disagree with reference (17706 validated; 2294 quarantine).

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
