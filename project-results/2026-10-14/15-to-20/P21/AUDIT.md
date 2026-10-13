# P21 — forensic grading review (15–20 band)

- Previously awarded provisional score: **19.811/25**, not official final academic mark.
- Frozen source: https://github.com/alimohnasseriy-bot/Auto-Routing-clean-order-pipeline/tree/30abeb6575d41c4f173af0bfcf9517f43f120156
- Exact frozen SHA: `30abeb6575d41c4f173af0bfcf9517f43f120156`
- Original evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
- Latest summary evidence run: https://github.com/omrbosnd/bigdata-grader/actions/runs/38196458648

## Attribution and source inspection
Student API conditionally requires reason for quarantined_by_reason; grader sent only limit -> 400. Other 4 query calls returned 200. Proven malformed grader probe, issue #37. Other data-count differences separate.

## Fairness controls
- Keep every established PASS from previous evaluations of the identical frozen SHA.
- HTTP failure following a malformed grader request is a grader-side probe failure, not student code failure; does not automatically award PASS.
- Inconclusive, blocked, and untested criteria must not be described as proven student failure. Manual discussion needs academic review.
- Full original `result.json` and assertion-level evidence are in the GitHub Actions artifacts for the linked run. This file is an index of source attribution, not replacement for machine report.
- No rerun, no score change and no student repository changes performed.
