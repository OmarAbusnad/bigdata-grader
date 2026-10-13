# P55 — Immutable GitHub Actions log excerpt

Source: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827/job/113638780570

This is a **verbatim selected subset** of the GitHub Actions console log (timestamps included); it is not a new test. The original full log and structured assertions remain authoritative.

```text
2026-10-09T05:36:11.8896311Z [GRADER] P55: preparing student-visible hidden inputs
2026-10-09T05:36:11.9142305Z [GRADER] P55: sandbox ready | database=grader_p55 | threshold=20.0MB
2026-10-09T05:36:11.9143709Z [GRADER] P55: stage 1/5 — Batch + ELT
2026-10-09T05:36:13.5027875Z [GRADER] P55: RUN batch_pipeline | file=test_01_small_batch_pipeline.csv | size=8.53MB | expected_engine=python_batch | threshold=20.0MB
2026-10-09T05:36:17.6397706Z [GRADER] P55: DONE batch_pipeline | rc=0 | elapsed=4.09s | raw=20000 validated=17956 quarantine=2044
2026-10-09T05:36:18.1012332Z [GRADER] P55: stage 2/5 — Spark path
2026-10-09T05:36:18.3447665Z [GRADER] P55: RUN spark_pipeline | file=test_02_large_spark.csv | size=43.61MB | expected_engine=pyspark | threshold=20.0MB
2026-10-09T05:36:20.1116198Z [GRADER] P55: DONE spark_pipeline | rc=1 | elapsed=1.76s | raw=0 validated=0 quarantine=0
2026-10-09T05:36:20.1128665Z [GRADER] P55: stage 3/5 — establish Upsert baseline
2026-10-09T05:36:21.0243096Z [GRADER] P55: RUN upsert_baseline | file=test_01_small_batch_pipeline.csv | size=8.53MB | expected_engine=python_batch | threshold=20.0MB
2026-10-09T05:36:25.1802393Z [GRADER] P55: DONE upsert_baseline | rc=0 | elapsed=4.11s | raw=20000 validated=17956 quarantine=2044
2026-10-09T05:36:25.8103838Z [GRADER] P55: stage 4/5 — Upsert insert/update/unchanged
2026-10-09T05:36:25.8627783Z [GRADER] P55: RUN upsert_first | file=test_03_upsert_idempotency.csv | size=0.85MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:36:27.1825537Z [GRADER] P55: DONE upsert_first | rc=0 | elapsed=1.27s | raw=22000 validated=18716 quarantine=2231
2026-10-09T05:36:27.5643364Z [GRADER] P55: stage 5/5 — Idempotency rerun
2026-10-09T05:36:27.6113720Z [GRADER] P55: RUN upsert_rerun | file=test_03_upsert_idempotency.csv | size=0.85MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:36:28.8446861Z [GRADER] P55: DONE upsert_rerun | rc=0 | elapsed=1.18s | raw=24000 validated=18716 quarantine=2418
2026-10-09T05:36:28.8958922Z [GRADER] P55: RUN incremental_first | file=test_04_incremental_plan_b.csv | size=0.43MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:36:30.1203600Z [GRADER] P55: DONE incremental_first | rc=0 | elapsed=1.17s | raw=25000 validated=19259 quarantine=2485
2026-10-09T05:36:30.1805847Z [GRADER] P55: RUN incremental_rerun | file=test_04_incremental_plan_b.csv | size=0.43MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:36:31.3756030Z [GRADER] P55: DONE incremental_rerun | rc=0 | elapsed=1.14s | raw=26000 validated=19259 quarantine=2552
2026-10-09T05:36:31.3788070Z [GRADER] P55: runtime complete | PASS=17 FAIL=11 INCONCLUSIVE=7 ERROR=0
2026-10-09T05:37:08.4889654Z   "midterm_status": "COMPLETED_WITH_FAILURES",
2026-10-09T05:37:08.4889930Z   "final_status": "STARTUP_BLOCKED",
```
