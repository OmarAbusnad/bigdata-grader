# P16 — adjudication ledger

**Evidence only; student code frozen, no new tests or grade changes.**

- Student output mismatch: batch.validated_count=15530; batch.quarantine_count=4470; upsert.final_validated=666. Runtime results differ from test oracle.
- Grader evidence gap: batch.schema_validator_runtime; source contains src/schema_validation.py but runtime activation is not evidenced. Issue #35.
- Partial audit: batch.audit_trail=9/18; require sample diagnostics. Issue #36.
- Incremental output: incremental.final_validated=483 vs test expectation 500.
- Final: final.api.discovered failed; no FastAPI source in frozen project. Other final cases NO_EVIDENCE due absent entrypoint, not independently failed.
- code_tests_docs NO_EVIDENCE: grader did not test weighted criterion; issue #33.
- final.discussion HUMAN_DECISION_REQUIRED. Other historic PASS retained.

## Traceability
- [Original grader run](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)
- [Same-SHA targeted reruns](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812)
- Raw result artifact named `unified-P16-37874152827` contains `reports/P16/result.json` and `reports_final/P16/result.json`.
- All existing PASS are retained. An inconclusive assertion must not be described as a proven student FAIL; root cause belongs either to missing student source/dependency, observed output discrepancy, grader probe defect, grader evidence gap, or human discussion.
