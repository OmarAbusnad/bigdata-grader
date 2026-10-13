# P41 — adjudication ledger

**Evidence only; student code frozen, no new tests or grade changes.**

- Student frozen requirements omit fastapi, uvicorn, and schedule used in api.py and src/scheduler_jobs.py. Final API server cannot start; its 20 dependent cases are BLOCKED due student configuration rather than separate functional failures.
- Frozen src/mongo_setup.py and src/elt_pipeline.py create incompatible order_id index configurations.
- Midterm output differences: batch.validated_count=18750; batch.quarantine_count=1250; upsert.final_validated=794; incremental.final_validated=562; batch.unique_index_runtime failed.
- spark_pipeline.engine observed python_batch where PySpark expected.
- batch.schema_validator_runtime lacks linked runtime proof; issue #35.
- batch.audit_trail=9/18 partial; issue #36 for diagnostic detail.
- code_tests_docs not assessed; issue #33. Discussion manual.

## Traceability
- [Original grader run](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)
- [Same-SHA targeted reruns](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812)
- Raw result artifact named `unified-P41-37874152827` contains `reports/P41/result.json` and `reports_final/P41/result.json`.
- All existing PASS are retained. An inconclusive assertion must not be described as a proven student FAIL; root cause belongs either to missing student source/dependency, observed output discrepancy, grader probe defect, grader evidence gap, or human discussion.
