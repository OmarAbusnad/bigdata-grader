# P50 — evidence report

Frozen SHA: `e3c74fdd8e5a36e80ce1a8d0337733f0ca64add3`

Confirmed grader problems: an invalid high_value_orders query-parameter combination (issue #31), and prior job-list extraction ignoring scheduler_status.jobs (issue #32). Historical passes on the same commit must be kept; four queries worked correctly. Midterm cleaning/quarantine/upsert discrepancies remain in student output.

Counts: 41 PASS, 12 FAIL, 7 INCONCLUSIVE, 1 NO_EVIDENCE. Provisional score 14.370/25 pending formal rubric confirmation. Evidence: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827
