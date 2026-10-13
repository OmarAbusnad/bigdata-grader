# Confirmed grader issues / consolidate fixes later

- [#37](https://github.com/omrbosnd/bigdata-grader/issues/37) Malformed named-query parameters: P01 P21 P28 P43 P54 P59. Invalid HTTP query not student FAIL.
- [#38](https://github.com/omrbosnd/bigdata-grader/issues/38) P59 /refresh-mv omitted required name, got HTTP 422.
- [#39](https://github.com/omrbosnd/bigdata-grader/issues/39) Isolated Maven Spark connector prerequisite: P04 P05 P14 P15 P26.
- [#40](https://github.com/omrbosnd/bigdata-grader/issues/40) P54 false PySpark detected from Arabic explanation despite MongoDB engine=python_batch.
- [#34](https://github.com/omrbosnd/bigdata-grader/issues/34) Global env-example gate and official rubric.
- [#35](https://github.com/omrbosnd/bigdata-grader/issues/35), [#36](https://github.com/omrbosnd/bigdata-grader/issues/36): Schema/Audit trace evidence.
- [#30](https://github.com/omrbosnd/bigdata-grader/issues/30): Official midterm grading rubric still needs approval.

### Verified student-side causes
- P05 src/api.py imports aggregations from a nonresolving top-level location (ModuleNotFoundError).
- P07 hardcoded Windows Java executable path.
- P40 root main.py discards dataset CLI argument.
- P39 source defaults to reset=True and drops persisted collections between upsert/incremental runs.

Do not run new student tests or modify scores until the pooled grader repairs and academic rubric are approved.
