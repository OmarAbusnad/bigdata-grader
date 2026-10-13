# P32 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.911/25**, not official final academic mark.
- Frozen source: https://github.com/malakmarzook03-star/-malash_pipline-main--1/tree/537106090a
- Exact frozen SHA: `537106090a`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Frozen API present. Batch counts 18500 valid vs expected 17000, quarantines 1500 instead of 3000; Spark produced zero valid/100000 quarantined. Needs source- and fixture-level reconciliation; no grader bug proved.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
