# P52 frozen archive source proof

Frozen student repo SHA: `32d0fde28c7214c8cd7a2738c5d4c9bf36b5101d`
Frozen artifact: `frozen-P52-37390623044` (GitHub Actions). The artifact contains `P52.repo.tar.gz` which contains `repo/saad hassan.zip`.

Inner ZIP size: 69,393,147 bytes. SHA-256: `6475cba85f070ec7c1e87a820e5025046d4a3fadb3cc85c4ba290759a9ed84d7`.

All relevant extracted source names: `src/main.py`, `src/batch_loader.py`, `src/elt_pipeline.py`, `src/file_router.py`, `src/schema_validation.py`, `src/mongo_setup.py`, `src/spark_loader.py`, `src/quality_rules.py`, `tests/test_classification.py`, `tests/test_cleaning_rules.py`, `tests/test_schema_only.py`, `README.md`, `requirements.txt`.

Frozen `requirements.txt` content: `pymongo`, `pyspark`, `pytest`, `python-dotenv`.

A search of the full original archive's source for FastAPI imports or route declarations did not find a FastAPI app or final API endpoints. This directly attributes absent final API to the frozen student submission, not the grader. The **initial failure to open this nested ZIP** is a separate confirmed grader discovery problem tracked in issue #29. Later successful same-SHA midterm tests preserve 29 PASS.

No tests rerun and no student files changed during inspection.
