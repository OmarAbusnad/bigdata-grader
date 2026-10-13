# P39 — confirmed grader invocation failure, not proven student Upsert failure

**Corrected conclusion after reading the frozen student's README.** The previous source-only analysis overlooked the documented `--no-reset` stage contract.

Frozen SHA: `ec844f735a04f351b8e9785d209ddfce74a0c829`

Student [README lines 688–701](https://github.com/mushtaqalfaqih/BigData-Midterm-Pipeline/blob/ec844f735a04f351b8e9785d209ddfce74a0c829/README.md#L688-L701) explicitly specifies **`python src/main.py --file-path ... --no-reset`** for idempotency/upsert reruns. Student `src/main.py` exposes flag `--no-reset` and passes `reset=not args.no_reset`. `src/mongo_setup.py` drops collections on default reset=True.

Grader did **not** append documented `--no-reset` for upsert and incremental stages. Saved MongoDB snapshots:
- Baseline: validated 18,750
- Upsert-first: validated 1,875 after unwanted reset
- Incremental-first: validated 958 after next unwanted reset.

Negative deltas in evidence ledger are a consequence of comparing successive **reset** snapshots. This is a confirmed **GRADER_INVOCATION_FAILURE**, [Issue #41](https://github.com/omrbosnd/bigdata-grader/issues/41), not proof student's business Upsert implementation fails. Preserve any already verified PASS and do not automatically grant new PASS without valid evidence. **No rerun or grade change performed.**