# P04 Spark — no grade change; proven incompatible student dependencies

**Student frozen SHA:** `f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda`  
**Student repo:** [Hafsa-Alazazi/Data_pipeline](https://github.com/Hafsa-Alazazi/Data_pipeline/tree/f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda)  
**Original run:** [37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)  
**Guarded targeted attempt:** [38607973641](https://github.com/omrbosnd/bigdata-grader/actions/runs/38607973641)  
**Spark issue:** [#39](https://github.com/omrbosnd/bigdata-grader/issues/39)

## Frozen source-level proof

- [requirements.txt](https://github.com/Hafsa-Alazazi/Data_pipeline/blob/f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda/requirements.txt) explicitly requires `pyspark>=4.0.0`.
- [src/spark_loader.py](https://github.com/Hafsa-Alazazi/Data_pipeline/blob/f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda/src/spark_loader.py) configures `org.mongodb.spark:mongo-spark-connector_2.13:10.4.0`.
- [MongoDB v10 connector prerequisites](https://www.mongodb.com/docs/spark-connector/v10.x/getting-started/) target Spark 3.1–3.5; [MongoDB 11.0 release notes](https://www.mongodb.com/docs/spark-connector/current/release-notes/) state Spark 4.0 support begins with Connector 11.0.
- Therefore the submitted pair is independently incompatible even if Maven is online.

## Targeted attempt results

The frozen metadata/source comparison and the original test-status guard **passed**. The retry runner then refused execution before running the student's Spark command:

```text
ValueError: Retry denied: Maven dependency responsibility is not proven grader-side
```

**Attribution:** `STUDENT_VERSION_OR_FORMAT_MISMATCH` is supported by immutable source and official compatibility docs; the earlier sandbox Maven network failure is also real but is not the **sole** blocker here. No corrected Spark functional PASS was demonstrated.

**Integrity:** Zero new student Spark tests executed; none of P04's historical PASS are revoked, and no academic grade changed. This case must not be automatically grouped with grader-only Maven recovery. The earlier Issue #39 list has been corrected.
