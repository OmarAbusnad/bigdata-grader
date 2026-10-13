# Evidence review for seven 10-15/25 projects — 14 Oct 2026

This is a documentation-only audit. No student tests were rerun, and no grades were changed.

## Project folders
- [P16](P16/AUDIT_AR.md) — [decisions](P16/DECISIONS.md)
- [P41](P41/AUDIT_AR.md) — [decisions](P41/DECISIONS.md) — Shahd and Rina: **12.361/25 credit-only provisional**.
- [P44](P44/AUDIT_AR.md) — [decisions](P44/DECISIONS.md)
- [P47](P47/AUDIT_AR.md) — [decisions](P47/DECISIONS.md)
- [P50](P50/AUDIT_AR.md) — [decisions](P50/DECISIONS.md)
- [P52](P52/AUDIT_AR.md) — [decisions](P52/DECISIONS.md)
- [P55](P55/AUDIT_AR.md) — [results note](P55/RESULTS_NOTE.md)

## Tracked grader defects and evidence gaps
- [#29](https://github.com/omrbosnd/bigdata-grader/issues/29) ZIP-only discovery of P52
- [#30](https://github.com/omrbosnd/bigdata-grader/issues/30) Draft-disabled midterm rubric
- [#31](https://github.com/omrbosnd/bigdata-grader/issues/31) P50 query argument selection
- [#32](https://github.com/omrbosnd/bigdata-grader/issues/32) P50 nested job list
- [#33](https://github.com/omrbosnd/bigdata-grader/issues/33) Unchecked documentation/test criteria
- [#34](https://github.com/omrbosnd/bigdata-grader/issues/34) P47 example env requirement policy
- [#35](https://github.com/omrbosnd/bigdata-grader/issues/35) Runtime schema validation evidence
- [#36](https://github.com/omrbosnd/bigdata-grader/issues/36) Per-sample audit trail diagnostics

## Evidence safeguards
- Do not count an unexecuted test as FAIL or PASS.
- Preserve historical same-SHA PASS.
- Distinguish student source/dependency failures from proven grader errors and insufficient test evidence.
- Publicly disclosed scores must not be called final until official rubric mapping and instructor-only criteria have been approved.
- Raw machine-output artifacts remain linked to the original GitHub Actions runs rather than copied to the student's public repository.
