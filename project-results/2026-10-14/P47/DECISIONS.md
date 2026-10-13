# P47 — adjudication ledger

**Evidence only; student code frozen, no new tests or grade changes.**

- Student source date handling in src/quality_rules.py accepts only enumerated date formats; most tested records were quarantined rather than validated. Midterm FAIL includes batch.validated_count, batch.quarantine_count=20000, spark.raw_count, spark.validated_count, upsert.final_validated, incremental.final_validated and related zero-of-12 sample checks.
- Spark command failure is recorded, but do not separately blame grader without confirming environment prerequisites.
- batch.schema_validator_runtime has incomplete proof; issue #35.
- upsert.baseline_validated / idempotency.validated_stable / incremental.rerun_validated_stable are INCONCLUSIVE when upstream has zero valid rows. Not independent proof of downstream failure.
- final.indexes.explain and final.aggregations.runtime have partial evidence; their data depends on upstream population. final.mv.collections was FAIL in latest report.
- final.dependencies missing .env.example: rubric requirement unverified (issue #34), not proven student penalty.
- final.github_readme INCONCLUSIVE, inspect document criterion from official rubric. final.discussion manual.

## Traceability
- [Original grader run](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)
- [Same-SHA targeted reruns](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812)
- Raw result artifact named `unified-P47-37874152827` contains `reports/P47/result.json` and `reports_final/P47/result.json`.
- All existing PASS are retained. An inconclusive assertion must not be described as a proven student FAIL; root cause belongs either to missing student source/dependency, observed output discrepancy, grader probe defect, grader evidence gap, or human discussion.
