# P68 and P69 — omitted stage due to submission classification, not observed failure

## Source of omission

The original grader roster `submission_groups.csv` and `late_submissions_20261013.csv` registered **P68 as midterm** and **P69 as final**. The last-chance workflow 38632370130 followed these registration modes, so its artifacts omitted P68 final and P69 midterm.

## Code review at the deadline-accepted SHAs

- **P68**, `Bilal-AlShami/bigdata-hybrid-pipeline@1c0b2b4652e51c33209f6a89e7a580100276f591`: `src/api.py` defines a FastAPI app, standard final endpoints including /health, /ingest, /indexes, queries, aggregations, /refresh-mv and jobs; `run_api.bat` documents `uvicorn src.api:app`. A missing final assessment is therefore a grader/scheduling omission, **not a student failure**.
- **P69**, `newump2017-coder/Final-project-bigdata@cfce6b1d0b0b8fcae26a6b6f2e805c10479539cf`: `README.md` documents `python -m src.ingestion.pipeline --file data/sample.csv` as midterm; `src/ingestion/pipeline.py` contains an unfinished bridge `run_pipeline` returning a stub, not the actual pipeline. This is source evidence requiring actual isolated midterm probing before any academic attribution.

## Safety and status

The targeted two-project workflow validates original same-SHA snapshot and absence of old assessment for requested phase, freezes only exact deadline-accepted SHAs, runs **only P68 final and P69 midterm**, uploads independent evidence, and never edits student code or grades. Existing P68 midterm PASS and P69 final PASS stay untouched. P69 source functionality is not inferred successful from README.
