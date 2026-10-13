# P07 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.783/25**, not official final academic mark.
- Frozen source: https://github.com/Mo-Alwosabi/BigData-Hybrid-Pipeline/tree/a7beeeaa76
- Exact frozen SHA: `a7beeeaa76`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen API exists. Spark/upsert command exits 1, downstream verified row counts differ. Need exact stderr and matching student requirements for causal attribution; never penalize for exit code without root cause.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
