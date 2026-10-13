# P50 — adjudication ledger

**Evidence only; student code frozen, no new tests or grade changes.**

- Confirmed grader issue #31: final.queries.runtime sent unadvertised start_date and end_date to high_value_orders; the HTTP 500 from this invalid request is not evidence of a failing student query. Four other query calls succeeded.
- Confirmed historical grader issue #32: earlier jobs parser ignored scheduler_status.jobs; same-SHA rerun showed two jobs and manual triggers PASS.
- Same-SHA history: keep earlier successful final.mv.collections, final.indexes.explain, final.aggregations.runtime even when a later probe failed or became inconclusive.
- Midterm student outputs: batch.quarantine_count=19751, spark.quarantine_count=43146, sample checks 0/18 for audit/cleaning, upsert sample checks 0/12. These need data-quality source attribution; no presumption that a late FAIL overrides earlier PASS.
- spark_pipeline.engine and batch.schema_validator_runtime lack runtime evidence (issue #35), and zero-row upsert stability checks are INCONCLUSIVE rather than proof of implementation success or failure.
- code_tests_docs missing grader coverage (issue #33). Discussion manual.

## Traceability
- [Original grader run](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)
- [Same-SHA targeted reruns](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812)
- Raw result artifact named `unified-P50-37874152827` contains `reports/P50/result.json` and `reports_final/P50/result.json`.
- All existing PASS are retained. An inconclusive assertion must not be described as a proven student FAIL; root cause belongs either to missing student source/dependency, observed output discrepancy, grader probe defect, grader evidence gap, or human discussion.
