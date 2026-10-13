# P40 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.861/25**, not official final academic mark.
- Frozen source: https://github.com/qusaiqaria-cmyk/-midterm-data-pipeline/tree/ce51dee3dff5a4abd589d1c5dcab88dfaae4020b
- Exact frozen SHA: `ce51dee3dff5a4abd589d1c5dcab88dfaae4020b`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38317234359

## Attribution and source inspection
Frozen root main.py and src/main.py exist. Latest midterm startup blocked while final API succeeded. Require traceback and grader start-command source to attribute failure. Preserve prior same-SHA PASS; no immediate fail.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
