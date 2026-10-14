# Source-only audit for Schema Validator and Audit Trail, 2026-10-14

Trigger: [Guarded workflow](https://github.com/omrbosnd/bigdata-grader/blob/fix/consolidated-fair-grading-20261014/.github/workflows/guarded-frozen-schema-audit-20261014.yml).

**Purpose:** Gather SOURCE indicators from the identical immutable graded archives for P16, P41, P44, P47, P50 and P52, including student ZIP-only submissions, without running student code or testing already passed stages.

**Hard verdict limitations:** Finding `$jsonSchema` or an Audit Trail function in a file does **not** prove functional runtime correctness. This is not a PASS or FAIL. A proven source+report SHA match is a prerequisite to design the next isolated positive/negative MongoDB validator test and per-sample Audit Trail check. If source and report differ, output `BLOCKED_UNVERIFIED`; do not infer student fault.

**Outputs:** `project-results/Pxx/forensics/FROZEN_STATIC_SCHEMA_AUDIT_20261014.json` in PR branch (when Actions write permission succeeds) plus independent `frozen-schema-audit-<run_id>` artifacts. Reports redact hidden fixture payloads and student content; include only source relative file paths, line numbers, operator names, original verdicts, SHA, original run URLs, and root-cause unknown.

Previous success remains immutable, grade updates **zero**. [Issue #35](https://github.com/omrbosnd/bigdata-grader/issues/35), [Issue #36](https://github.com/omrbosnd/bigdata-grader/issues/36).
