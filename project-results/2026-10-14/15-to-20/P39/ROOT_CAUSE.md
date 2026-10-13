# P39 — verified source-side destructive resets on every ingestion

Frozen student SHA: `ec844f735a04f351b8e9785d209ddfce74a0c829`.

Original grader run state: `upsert_baseline` left 18,750 validated records; next `upsert_first` left 1,875; `incremental_first` left 958. These are *real MongoDB collection snapshot counts*, not physical negative numbers. A provisional grading ledger recorded negative **deltas** because later collections were smaller than the earlier baseline.

**Why source-side:** [src/main.py](https://github.com/mushtaqalfaqih/BigData-Midterm-Pipeline/blob/ec844f735a04f351b8e9785d209ddfce74a0c829/src/main.py#L12-L44) accepts `--no-reset`, but its default calls `run_elt_pipeline(..., reset=not args.no_reset)` with reset=True. [src/mongo_setup.py](https://github.com/mushtaqalfaqih/BigData-Midterm-Pipeline/blob/ec844f735a04f351b8e9785d209ddfce74a0c829/src/mongo_setup.py#L12-L60) drops `orders_raw`, `orders_validated`, and `orders_quarantine` on reset. The grading command `python src/main.py --file-path {file}` did not pass `--no-reset`.

**Conclusion:** submission's default CLI contract destructively resets persistence; unsuitable for upsert/incremental replay. There is an alternative flag to disable reset, but the student README/contract should be checked whether grader was expected to invoke it. This is **not** evidence the grader fabricated negative record counts. Do not change PASS history or grades without rubric review.

Original actions: https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827 .