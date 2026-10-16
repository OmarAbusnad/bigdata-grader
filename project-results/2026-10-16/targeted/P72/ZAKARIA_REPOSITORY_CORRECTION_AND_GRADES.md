# P72 — Zakaria Yahya Ali Qaria | Repository correction and machine-grade evidence

**Student:** زكريا يحيى علي قاريه  
**Student no.:** 30  
**Correct repository:** https://github.com/ZakariaQaria/big-data-project  
**Frozen evaluated commit:** `4f83f6f7a64db072f2d4d3ef6689e5ea52001c32`

The earlier cohort entry P45 incorrectly grouped Zakaria with Ziad's different repository `ziad0110/big-data-pipeline`. The cohort register was corrected to keep **P45 exclusively for Ziad** and create **P72 exclusively for Zakaria**, preserving all historical P45 evidence and grades.

## Latest isolated grader executions
- Full midterm + final baseline: https://github.com/omrbosnd/bigdata-grader/actions/runs/38952071362
- Focused midterm rerun after generic safe staging of the student-documented fixed CSV input: https://github.com/omrbosnd/bigdata-grader/actions/runs/38953069354

## Grade by the teacher's uploaded 2026-10-15 gradebook methodology
- Midterm: **11.361110 / 18**
- Final: **6.750001 / 7**
- Total: **18.111 / 25** (rounded to 3 decimals)

The calculation uses the gradebook's **61 fixed assertion keys and individual test weights**, not the different strict-capability scoring function. Each affirmed PASS earns the attached sheet's weight. Non-PASS assertions are not awarded points in this particular gradebook methodology. The manual discussion criterion of 0.25 is not awarded by the automated test.

## Material runtime limitations
- Batch processing ran after recovering the fixed CSV path with an environment-only grader adjustment; student source was not edited.
- The PySpark runtime did not start on Linux because the student code contains a Windows-specific Spark executable path (`C:\\spark\\spark-4.2.0-bin-hadoop3`). This is recorded in the test evidence.
- Official final-suite runtime: 24 PASS, no technical FAIL, 1 manual discussion not automatically evaluated.

**No changes were made to the student's repository.** Historical P45/Ziad test artifacts remain intact.
