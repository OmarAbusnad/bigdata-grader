# P47 — evidence report

Frozen SHA: `16637583c1cb0937d10e8afa3f029dcc5a36bf62`

Student code src/quality_rules.py rejects date representations outside the parser's supported list, leaving too few validated records for downstream checks. Missing source data affects independent MV tests. A grader policy question about requiring .env.example is tracked in issue #34; do not classify missing file as a confirmed rubric violation until the assignment is checked.

Counts: 38 PASS, 14 FAIL, 8 INCONCLUSIVE, 1 NO_EVIDENCE. Provisional 13.250/25. Evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
