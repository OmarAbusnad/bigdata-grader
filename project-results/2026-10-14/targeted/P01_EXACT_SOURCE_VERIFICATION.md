# P01 — immutable later-source commit verification (read-only)

- Exact latest assessed SHA: `c43aae3d5e9c0d96731640206752f886f2618497` from [original diagnostic run 38424927615](https://github.com/omrbosnd/bigdata-grader/actions/runs/38424927615), artifact `diagnostic-undeclared-deps-P01-38424927615` (artifact ID `11827434516`, not expired at inspection).
- Student repository: [6980-rehab/midterm-data-pipeline- at exact commit](https://github.com/6980-rehab/midterm-data-pipeline-/commit/c43aae3d5e9c0d96731640206752f886f2618497), commit exists and GitHub reports message `Add files via upload`.
- Direct read at exact SHA: [src/api.py](https://github.com/6980-rehab/midterm-data-pipeline-/blob/c43aae3d5e9c0d96731640206752f886f2618497/src/api.py) defines GET `/queries/{name}` accepting `start: str | None`, `end: str | None`. Old grader request with only `limit` cannot test a date-scoped query.
- Older initial frozen SHA `f1a440a4a07b8b8bd8c9bf9818de59e5046eeab3` differs: its snapshot must not be reused.
- New guarded artifact snapshot workflow is [here](https://github.com/omrbosnd/bigdata-grader/blob/fix/consolidated-fair-grading-20261014/.github/workflows/guarded-late-source-snapshots-20261014.yml). It must cross-check a report JSON matching this SHA before snapshotting.

**Decision:** `GRADER_PROBE_FAILURE` previously for malformed `orders_in_period` request, but **P01 functional verdict remains unverified** until exact-SHA guarded query runtime. Do not rerun four historical same-SHA query PASS or change any grade.
