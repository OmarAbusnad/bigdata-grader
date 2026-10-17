# P26 — immutable later-source commit verification (read-only)

- Exact accepted grading SHA: `fc4f5d9924fe9a59f09e4167d323eaf4672ccca2`, [later grading run 38317234359](https://github.com/omrbosnd/bigdata-grader/actions/runs/38317234359), artifact `late-grading-P26-38317234359` (ID `11776873139`, not expired at inspection).
- Source [at exact commit](https://github.com/engmwaly/Project-BigData-Data-Pipeline/commit/fc4f5d9924fe9a59f09e4167d323eaf4672ccca2) exists. GitHub confirms old `51605d72971468f5d96fb995833f378a87d2216f` is its parent, **not the same commit**.
- [README at exact SHA](https://github.com/engmwaly/Project-BigData-Data-Pipeline/blob/fc4f5d9924fe9a59f09e4167d323eaf4672ccca2/README.md) documents MongoDB connector `mongo-spark-connector_2.12:10.3.0` downloaded manually in `jars/`, with Java and PySpark dependencies; does not itself establish executed Spark success.
- Guarded later snapshot checks artifact report SHA and emits manifest with source SHA-256; [workflow](https://github.com/omrbosnd/bigdata-grader/blob/fix/consolidated-fair-grading-20261014/.github/workflows/guarded-late-source-snapshots-20261014.yml).

**Decision:** `PRECONDITION_NOT_SATISFIED` for retesting old frozen archive against this later grading. Spark verdict remains unverified for later SHA pending exact pinned dependency/runtime-only check; do not use old P26 full-phase workflow, and do not change grades.
