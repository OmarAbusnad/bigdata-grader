# Confirmed grader issues / consolidate fixes later

- [#37](https://github.com/omrbosnd/bigdata-grader/issues/37) Malformed named-query parameters: P01 P21 P28 P43 P54 P59. The invalid HTTP call is not student FAIL.
- [#38](https://github.com/omrbosnd/bigdata-grader/issues/38) Required `name` omitted from P59 /refresh-mv => 422.
- [#39](https://github.com/omrbosnd/bigdata-grader/issues/39) Isolated Maven Spark connector prerequisites missing: P04 P05 P14 P15 P26.
- [#34](https://github.com/omrbosnd/bigdata-grader/issues/34) Universal env-example requirement, rubric must be checked: P15 P18 P20 P24 P56.
- [#35](https://github.com/omrbosnd/bigdata-grader/issues/35), [#36](https://github.com/omrbosnd/bigdata-grader/issues/36): Schema Validator/Audit Trail evidence.
- [#30](https://github.com/omrbosnd/bigdata-grader/issues/30): Midterm rubric remains DRAFT_DISABLED.
- **Not grader bugs**: P05 import `aggregations`, P07 hard-coded Windows Java, P40 ignores CLI file argument; see ROOT_CAUSE.md in each project's folder.

No new grading jobs and no grade updates in current audit phase. Consolidate and regression-test these fixes only after all bands are reviewed.
