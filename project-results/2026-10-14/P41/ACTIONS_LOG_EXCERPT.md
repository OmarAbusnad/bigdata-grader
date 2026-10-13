# P41 — Immutable GitHub Actions log excerpt

Source: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827/job/113638778649

This is a **verbatim selected subset** of the GitHub Actions console log (timestamps included); it is not a new test. The original full log and structured assertions remain authoritative.

```text
2026-10-09T05:01:06.8824623Z [GRADER] P41: preparing student-visible hidden inputs
2026-10-09T05:01:06.9110715Z [GRADER] P41: sandbox ready | database=grader_p41 | threshold=20.0MB
2026-10-09T05:01:06.9118091Z [GRADER] P41: stage 1/5 — Batch + ELT
2026-10-09T05:01:07.9046294Z [GRADER] P41: RUN batch_pipeline | file=test_01_small_batch_pipeline.csv | size=8.53MB | expected_engine=python_batch | threshold=20.0MB
2026-10-09T05:01:09.3911004Z [GRADER] P41: DONE batch_pipeline | rc=1 | elapsed=1.49s | raw=0 validated=0 quarantine=0
2026-10-09T05:01:46.9478372Z   "midterm_status": "STARTUP_BLOCKED",
2026-10-09T05:01:46.9478815Z   "final_status": "STARTUP_BLOCKED",
```
