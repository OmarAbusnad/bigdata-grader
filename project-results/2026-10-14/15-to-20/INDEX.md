# Forensic review — 15 ≤ provisional grade < 20 (14 Oct 2026)

**Status: Evidence-only, not final grading.** 32 frozen projects, 35 students, 1,952 total assertions in locally generated forensic ledger: 1,561 historical PASS retained, 203 FAIL, 141 INCONCLUSIVE, 47 NO_EVIDENCE.

Project-level report: `project-results/2026-10-14/15-to-20/<Pxx>/AUDIT.md`, linked to the actual frozen student SHA and original GitHub Actions evidence. Full assertion-level exports for each project were generated locally; the GitHub folder currently contains the per-project source-attribution reports, **not yet a verbatim upload of all assertion CSVs**.

## Confirmed grader issues
- [#37](https://github.com/omrbosnd/bigdata-grader/issues/37): malformed named-query probes in **P01, P21, P28, P43, P54, P59** (missing conditionally required query parameters).
- [#38](https://github.com/omrbosnd/bigdata-grader/issues/38): P59 `POST /refresh-mv` did not send required `name`; resulting 422 is a grader probe failure.
- [#34](https://github.com/omrbosnd/bigdata-grader/issues/34): overly strict global `.env.example` criterion affects P15, P18, P20, P24, P56; also audit README accuracy separately.
- [#35](https://github.com/omrbosnd/bigdata-grader/issues/35) / [#36](https://github.com/omrbosnd/bigdata-grader/issues/36): source-linked schema-validator and audit-sample diagnostic gaps.
- [#30](https://github.com/omrbosnd/bigdata-grader/issues/30): midterm point distribution `DRAFT_DISABLED` until official rubric is confirmed.

## Important specific proof
- P04 saved Spark output explicitly shows Maven network dependency failures under isolated sandbox; do not count blocked Spark pipeline as student FAIL without further evidence.
- P08 final API is nested under `final_extension/`, not missing.
- P40 final API worked; earlier midterm blocked needs its original traceback, not automatic forfeiture.
- P66 lacks source implementation / declared dependencies for required FastAPI final.
- P59 two job manual runs returned HTTP 500 due ObjectId serialization, **separate student runtime behavior**, not related to grader missing `name` on MV.

## Rules
1. Do **not** run any new tests or change provisional scores.
2. Preserve every same-SHA historical PASS.
3. A malformed grader request = `GRADER_PROBE_FAILURE`, not student FAIL and not automatic PASS.
4. Actual data mismatches against the teacher oracle must include sample-level evidence and frozen source proof before final responsibility is assigned.
5. Undetermined criteria must have explicit owner/cause; manual discussion remains teacher-assessed.
6. Do not treat these evidence-only provisional /25 weights as final official grades until the rubric is approved.
