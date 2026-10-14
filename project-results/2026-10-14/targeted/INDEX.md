# Targeted, frozen-SHA grading repairs — 14 Oct 2026

**Scope:** only previously failed/blocked assertions; preserve every historical same-SHA PASS. No academic grade sheet updated. [Draft PR #42](https://github.com/omrbosnd/bigdata-grader/pull/42).

| Project | Focus | Outcome | Evidence |
|---|---|---|---|
| **P05** | Originally failing Spark test02 | **PASS** (real Spark ran and persisted raw data) | [Run 38608767447](https://github.com/omrbosnd/bigdata-grader/actions/runs/38608767447) · [report](P05_SPARK_RECOVERY.md) |
| **P50** | Fifth named query `high_value_orders` only | **PASS** (HTTP 200, 7 of 7 expected) | [Run 38609876440](https://github.com/omrbosnd/bigdata-grader/actions/runs/38609876440) · [report](P50_HIGH_VALUE_QUERY_RECOVERY.md) |
| **P54** | Two incorrectly failed Batch engine verdicts from saved evidence | **PASS / PASS** via immutable MongoDB engine markers, no student rerun | [machine overlay](P54_ENGINE_SAVED_EVIDENCE_OVERLAY.json) · [Issue #40](https://github.com/omrbosnd/bigdata-grader/issues/40) |
| **P04** | Spark candidate | **Guard stopped before student execution**; source requires Spark4 with Connector10.4 incompatible | [Run 38607973641](https://github.com/omrbosnd/bigdata-grader/actions/runs/38607973641) · [source proof](P04_SPARK_ATTRIBUTION.md) |
| **P26** | Later Spark `spark_pipeline.command` | **Historical PASS preserved** from correct later-SHA report, guard prevented retest | [Run 38625479332](https://github.com/omrbosnd/bigdata-grader/actions/runs/38625479332) · [saved verdict](../../../../project-results/P26/forensics/LATER_SHA_SPARK_PASS_PRESERVED_20261014.json) |
| **P39** | Upsert/Incremental with documented `--no-reset` | Original grader invocation fixed; **counts still mismatch** (19,544/17,600, 20,106/18,100); rerun counts stable, duplicates zero | [Run 38613275326](https://github.com/omrbosnd/bigdata-grader/actions/runs/38613275326) · [detailed result](P39_MUTATION_SAME_SHA_EVIDENCE.json) |
| **P21** | `quarantined_by_reason` with required `reason` | **PASS**; HTTP 200, positive/negative quarantine filters checked | [Run 38614189504](https://github.com/omrbosnd/bigdata-grader/actions/runs/38614189504) · [evidence](P21_QUARANTINE_QUERY_RECOVERY.json) |
| **P54** | `sales_by_period` with required `start/end` | **PASS**; typed date-range filter checked | [Run 38614629459](https://github.com/omrbosnd/bigdata-grader/actions/runs/38614629459) · [evidence](P54_SALES_BY_PERIOD_RECOVERY.json) |
| **P28** | Five formerly malformed named queries | **5 × PASS**, HTTP 200 with matching filtered records | [Run 38615059156](https://github.com/omrbosnd/bigdata-grader/actions/runs/38615059156) · [evidence](P28_FIVE_NAMED_QUERIES_RECOVERY.json) |

| **P59** | `final.mv.refresh` and `final.mv.incremental` | **PASS / PASS**, no previously PASS endpoint rerun | [Run 38607512434](https://github.com/omrbosnd/bigdata-grader/actions/runs/38607512434) · [report](P59_MV_RECOVERY.md) |
| **P43** | Five formerly invalid named queries | **5 × PASS** with correctly supplied city/status/customer/date/amount parameters | [Run 38615809081](https://github.com/omrbosnd/bigdata-grader/actions/runs/38615809081) · [evidence](P43_FIVE_NAMED_QUERIES_RECOVERY.json) |
| **P01** | Latest `orders_in_period` query needs source-verification first | **NOT RERUN**: older frozen SHA differs from later graded SHA | [snapshot guard](P01_LATER_SHA_GUARD.md) |
| **P59** | Missing `order_id` in fifth named query | **PASS**, HTTP 200 and matched exact seeded order; prior four queries untouched | [Run 38616724766](https://github.com/omrbosnd/bigdata-grader/actions/runs/38616724766) · [evidence](P59_ORDER_ID_QUERY_RECOVERY.json) |

### Permanent evidence register
[Machine-readable evidence register](EVIDENCE_REGISTER.json) retains frozen source SHA, original run IDs, focused run IDs, artifact IDs and verdicts. GitHub Actions ZIP archives have finite retention, so this committed summary remains in repository history.



## Later-source commit resolution (not a student retest)

- **P01** exact assessed commit [c43aae3d](https://github.com/6980-rehab/midterm-data-pipeline-/commit/c43aae3d5e9c0d96731640206752f886f2618497) is reachable; its frozen `src/api.py` declares `start/end` for `/queries/{name}`. [Source evidence](P01_EXACT_SOURCE_VERIFICATION.md). **No query PASS claimed**.
- **P26** exact assessed commit [fc4f5d99](https://github.com/engmwaly/Project-BigData-Data-Pipeline/commit/fc4f5d9924fe9a59f09e4167d323eaf4672ccca2) is reachable, and follows the older `51605d72...` as a parent; source requires version-specific Spark check. [Source evidence](P26_EXACT_SOURCE_VERIFICATION.md). **Original later-SHA Spark command PASS explicitly preserved; NO new functional retest**.
- An exact-source archive workflow was added with a guard against mismatched assessment reports. Its result is a *provenance check*, not a functional retest. See [workflow](../../../../.github/workflows/guarded-late-source-snapshots-20261014.yml).

## Known separate student errors not silently forgiven

- P05 final API module import failure is **independent** of recovered Spark.
- P04's incompatible Spark+connector versions remain a source-level problem, while the previous network failure also occurred.
- P14 and P15 require separate source compatibility adjudication before recovery; do not copy P05's success to them.
- P26 exact latest source is now archived and the later original `spark_pipeline.command` is already PASS, so that test is never retested; see saved per-project guard evidence.

## Remaining steps

1. Under [Issue #37](https://github.com/omrbosnd/bigdata-grader/issues/37), finish still-unproved project-specific named query contracts (P01 later source revision); preserve all earlier successful queries.
2. Under [Issue #41](https://github.com/omrbosnd/bigdata-grader/issues/41), review P39's corrected-count evidence: no-reset works and same-file count is stable, but validated counts still diverge from instructor Oracle.
3. Complete evidence determination for Schema Validator and Audit Trail ([#35](https://github.com/omrbosnd/bigdata-grader/issues/35), [#36](https://github.com/omrbosnd/bigdata-grader/issues/36)).
4. Human review and merge of PR #42, then fold verified overlays into scoring under ACTIVE rubric, preserving original artifacts and manual discussion marks.

**No original reports deleted. No student source updated. No academic grades changed.**

## Latest verified adjudication checkpoints — 2026-10-14

- **P01 later SHA `c43aae3d5e9c0d96731640206752f886f2618497`:** exact-source archive [38624013769](https://github.com/omrbosnd/bigdata-grader/actions/runs/38624013769); previously unproven period query [38625479332](https://github.com/omrbosnd/bigdata-grader/actions/runs/38625479332) remains **INCONCLUSIVE because API was not ready**. Independent import-only [38626460727](https://github.com/omrbosnd/bigdata-grader/actions/runs/38626460727) proves **STUDENT_DEPENDENCY_FAILURE** (undeclared `psutil` prevents API import); see [P01 source-specific traceback](../../../../project-results/P01/forensics/LATER_SHA_API_IMPORT_DIAGNOSIS_20261014.json). Query logic itself is *not separately judged*; four other historical successful queries were not re-run. No score changed.
- **P26 later SHA `fc4f5d9924fe9a59f09e4167d323eaf4672ccca2`:** later original `spark_pipeline.command` already **PASS**; duplicate test was blocked at guard in [38625479332](https://github.com/omrbosnd/bigdata-grader/actions/runs/38625479332) before student execution. See [saved P26 same-SHA PASS proof](../../../../project-results/P26/forensics/LATER_SHA_SPARK_PASS_PRESERVED_20261014.json). No score changed.
- **Schema Validator/Audit Trail:** six projects' same-SHA frozen source checked [38624458712](https://github.com/omrbosnd/bigdata-grader/actions/runs/38624458712), corrected exclusion of P41 vendored virtualenv plus nested P52 ZIP [38625135356](https://github.com/omrbosnd/bigdata-grader/actions/runs/38625135356). [#35](https://github.com/omrbosnd/bigdata-grader/issues/35) / [#36](https://github.com/omrbosnd/bigdata-grader/issues/36) still **OPEN** for behavioral validator and original individual audit-row sample verification. No static string can substitute for runtime PASS.
- **Read-only grade reconciliation:** [run 38627569441](https://github.com/omrbosnd/bigdata-grader/actions/runs/38627569441) **SUCCESS**. [JSON evidence/readiness](../reconciliation/RECONCILIATION_READINESS.json) · [all-project review queue](../reconciliation/PENDING_GRADES_REVIEW.csv). Baseline **68** old-master-ledger projects with **2,678 historical PASS preserved**; **70** listed submissions, old P01/P26 SHA isolated from newly accepted SHA. Candidate-only corrections: P54's two structured engine assertions; none were applied to official points. Other scoped named-query PASS cannot automatically replace coarse aggregate rubric verdict; human discussion and full rubric mapping remain pending.
- No student repository was altered, **0 official grade changes**, PR remains a draft pending review.
