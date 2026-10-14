# Targeted, frozen-SHA grading repairs — 14 Oct 2026

**Scope:** only previously failed/blocked assertions; preserve every historical same-SHA PASS. No academic grade sheet updated. [Draft PR #42](https://github.com/omrbosnd/bigdata-grader/pull/42).

| Project | Focus | Outcome | Evidence |
|---|---|---|---|
| **P59** | `final.mv.refresh` and `final.mv.incremental` | **PASS / PASS**, no previously PASS endpoint rerun | [Run 38607512434](https://github.com/omrbosnd/bigdata-grader/actions/runs/38607512434) · [report](P59_MV_RECOVERY.md) |
| **P05** | Originally failing Spark test02 | **PASS** (real Spark ran and persisted raw data) | [Run 38608767447](https://github.com/omrbosnd/bigdata-grader/actions/runs/38608767447) · [report](P05_SPARK_RECOVERY.md) |
| **P50** | Fifth named query `high_value_orders` only | **PASS** (HTTP 200, 7 of 7 expected) | [Run 38609876440](https://github.com/omrbosnd/bigdata-grader/actions/runs/38609876440) · [report](P50_HIGH_VALUE_QUERY_RECOVERY.md) |
| **P54** | Two incorrectly failed Batch engine verdicts from saved evidence | **PASS / PASS** via immutable MongoDB engine markers, no student rerun | [machine overlay](P54_ENGINE_SAVED_EVIDENCE_OVERLAY.json) · [Issue #40](https://github.com/omrbosnd/bigdata-grader/issues/40) |
| **P04** | Spark candidate | **Guard stopped before student execution**; source requires Spark4 with Connector10.4 incompatible | [Run 38607973641](https://github.com/omrbosnd/bigdata-grader/actions/runs/38607973641) · [source proof](P04_SPARK_ATTRIBUTION.md) |
| **P26** | Spark candidate | **Not rerun**; later assessed SHA differs from older frozen source | [source comparison](P26_SNAPSHOT_BLOCKER.md) |

## Known separate student errors not silently forgiven

- P05 final API module import failure is **independent** of recovered Spark.
- P04's incompatible Spark+connector versions remain a source-level problem, while the previous network failure also occurred.
- P14 and P15 require separate source compatibility adjudication before recovery; do not copy P05's success to them.
- P26 requires exact latest source snapshot, not the old 37390623044 freeze.

## Remaining steps

1. Under [Issue #37](https://github.com/omrbosnd/bigdata-grader/issues/37), verify the malformed query responses for other affected frozen projects with scoped tests only; do not re-run their prior successful queries.
2. Under [Issue #41](https://github.com/omrbosnd/bigdata-grader/issues/41), test P39 Upsert/Incremental using documented `--no-reset` flag without changing a previous PASS.
3. Complete evidence determination for Schema Validator and Audit Trail ([#35](https://github.com/omrbosnd/bigdata-grader/issues/35), [#36](https://github.com/omrbosnd/bigdata-grader/issues/36)).
4. Human review and merge of PR #42, then fold verified overlays into scoring under ACTIVE rubric, preserving original artifacts and manual discussion marks.

**No original reports deleted. No student source updated. No academic grades changed.**
