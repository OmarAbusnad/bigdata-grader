# P54 — confirmed grader-side false PySpark failure

Frozen SHA: `81d9b76c452f27c8941e6da34e00c20071993e49`.
- Grader marked `batch_pipeline.engine` and `upsert_baseline.engine` **FAIL**, actual `pyspark`, expected `python_batch`.
- The same stored assertion includes authoritative `mongodb:engine=python_batch`.
- Student [src/file_router.py](https://github.com/shughaq/data-pipeline-main-BIGDATA/blob/81d9b76c452f27c8941e6da34e00c20071993e49/src/file_router.py#L12-L37) computes engine `python_batch` for files under threshold, and the explanatory sentence says batch is faster than paying the cost of starting **Spark**.
- Grader free-text matcher interpreted the word Spark in this sentence as if Spark were selected. This is a **GRADER_PROBE_FAILURE**, not student engine selection error.

Fixed centrally in [Issue #40](https://github.com/omrbosnd/bigdata-grader/issues/40) later. **Do not modify source or rerun tests in this evidence audit.** Retain other same-SHA successes. Independent malformed `sales_by_period` query is documented under issue #37.
