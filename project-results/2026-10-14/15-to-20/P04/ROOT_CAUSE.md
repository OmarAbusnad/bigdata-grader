# P04 — verified Spark Maven access blocked in grader isolated sandbox

- Frozen SHA: `f2c2ffd8901d83ed9363f33fd1b49ba5360a9eda`
- Grader selected PySpark correctly but could not resolve `org.mongodb.spark`:
```
unresolved dependencies
module not found: org.mongodb.spark
host repo1.maven.org not found
host repos.spark-packages.org not found
PySparkRuntimeError: [JAVA_GATEWAY_EXITED]
```
- Student batch path did run and produced **17,706 validated** and **2,294 quarantined** records, versus the reference 17,000/3,000; this mismatch is **separate**, not an effect of the Maven block.
- This class of isolated Maven failures is tracked in [Issue #39](https://github.com/omrbosnd/bigdata-grader/issues/39) with P05/P14/P15/P26; treat blocked Spark checks as grader-environment blocked, not student FAIL, pending compatibility proof.
- No rerun or grade change.