# P50 — Immutable GitHub Actions log excerpt

Source: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827/job/113638779828

This is a **verbatim selected subset** of the GitHub Actions console log (timestamps included); it is not a new test. The original full log and structured assertions remain authoritative.

```text
2026-10-09T05:18:43.4656883Z [GRADER] P50: preparing student-visible hidden inputs
2026-10-09T05:18:43.4961457Z [GRADER] P50: sandbox ready | database=grader_p50 | threshold=20.0MB
2026-10-09T05:18:43.4963523Z [GRADER] P50: stage 1/5 — Batch + ELT
2026-10-09T05:18:43.9833809Z [GRADER] P50: RUN batch_pipeline | file=test_01_small_batch_pipeline.csv | size=8.53MB | expected_engine=python_batch | threshold=20.0MB
2026-10-09T05:22:38.8446317Z [GRADER] P50: DONE batch_pipeline | rc=0 | elapsed=234.83s | raw=20000 validated=0 quarantine=19751
2026-10-09T05:22:39.3858201Z [GRADER] P50: stage 2/5 — Spark path
2026-10-09T05:22:39.7382941Z [GRADER] P50: RUN spark_pipeline | file=test_02_large_spark.csv | size=43.61MB | expected_engine=pyspark | threshold=20.0MB
2026-10-09T05:42:40.2347480Z [GRADER] P50: DONE spark_pipeline | rc=124 | elapsed=1200.26s | raw=100000 validated=0 quarantine=43345
2026-10-09T05:42:40.2398933Z [GRADER] P50: stage 3/5 — establish Upsert baseline
2026-10-09T05:42:40.8927067Z [GRADER] P50: RUN upsert_baseline | file=test_01_small_batch_pipeline.csv | size=8.53MB | expected_engine=python_batch | threshold=20.0MB
2026-10-09T05:57:32.3275140Z [GRADER] P50: DONE upsert_baseline | rc=0 | elapsed=891.33s | raw=20000 validated=0 quarantine=39719
2026-10-09T05:57:33.8944077Z [GRADER] P50: stage 4/5 — Upsert insert/update/unchanged
2026-10-09T05:57:33.9685936Z [GRADER] P50: RUN upsert_first | file=test_03_upsert_idempotency.csv | size=0.85MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:57:44.5302432Z [GRADER] P50: DONE upsert_first | rc=0 | elapsed=10.47s | raw=22000 validated=0 quarantine=41845
2026-10-09T05:57:44.5772384Z [GRADER] P50: stage 5/5 — Idempotency rerun
2026-10-09T05:57:44.6597859Z [GRADER] P50: RUN upsert_rerun | file=test_03_upsert_idempotency.csv | size=0.85MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:57:55.7315950Z [GRADER] P50: DONE upsert_rerun | rc=0 | elapsed=10.97s | raw=24000 validated=0 quarantine=43956
2026-10-09T05:57:55.8378377Z [GRADER] P50: RUN incremental_first | file=test_04_incremental_plan_b.csv | size=0.43MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:57:59.9432369Z [GRADER] P50: DONE incremental_first | rc=0 | elapsed=4.02s | raw=25000 validated=0 quarantine=45009
2026-10-09T05:58:00.0589647Z [GRADER] P50: RUN incremental_rerun | file=test_04_incremental_plan_b.csv | size=0.43MB | expected_engine=n/a | threshold=20.0MB
2026-10-09T05:58:04.1390872Z [GRADER] P50: DONE incremental_rerun | rc=0 | elapsed=3.97s | raw=26000 validated=0 quarantine=46062
2026-10-09T05:58:04.1466278Z [GRADER] P50: runtime complete | PASS=17 FAIL=16 INCONCLUSIVE=2 ERROR=0
2026-10-09T06:11:50.8176757Z   "midterm_status": "COMPLETED_WITH_FAILURES",
2026-10-09T06:11:50.8177372Z   "final_status": "COMPLETED_WITH_FAILURES",
```
