# P05 — successful targeted Spark recovery (14 Oct 2026)

- **Frozen student SHA:** `a4544a31f94b1924bfad9c34494e77879976fded`
- **Repo:** [HashemHobireh/hybrid-elt-data-pipeline](https://github.com/HashemHobireh/hybrid-elt-data-pipeline/tree/a4544a31f94b1924bfad9c34494e77879976fded)
- **Original evidence run:** [37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)
- **Targeted run:** [38608767447](https://github.com/omrbosnd/bigdata-grader/actions/runs/38608767447)
- **Raw artifact:** `p05-spark-only-proven-guarded-38608767447` (artifact ID `11916808130`)
- **Grader code at targeted run:** `1df283ee96c95df827b5a5c387189daefa9ae363`

## Exact observed verdict

```json
{"project_id": "P05", "verdict": "PASS", "reason": "original Spark stage ran successfully and persisted raw records", "error": null}
```

This targeted runner verified matching SHA between the original graded report and freeze metadata, then reran **only the originally failed Spark Test02** with a sandbox that prefetches compatible MongoDB Spark connector `org.mongodb.spark:mongo-spark-connector_2.12:10.3.0` for student-pinned `pyspark==3.5.1`.

**Scope of this PASS:** `spark_pipeline.command` proved that Spark ran and persisted raw data. This does not by itself certify all Spark data-cleaning counts or any final API tests. In particular the P05 import `aggregations` failure in the final API is a distinct student-source defect.

**Safeguards:** No previously PASS student phase rerun; no source modification; no change to grade sheet. Preserve original and focused records; use historical-PASS union only on identical frozen SHA.

Refer to the scoped Spark diagnostic [Issue #39](https://github.com/omrbosnd/bigdata-grader/issues/39).
