# Controlled targeted retest plan — 2026-10-14

**Audit branch**: fix/consolidated-fair-grading-20261014, [draft PR #42](https://github.com/omrbosnd/bigdata-grader/pull/42).

## Hard gates
1. CI must pass and proposed fixes must be reviewed/merged before official reruns. Do not rerun with older runner source.
2. All retests use the student's **identical immutable commit SHA** underlying the historical verdict. For late submissions P01, P24 and P26, the original 37390623044 freeze may be **older**; do not silently re-use it. Compare frozen manifest to project-results/<id>/FROZEN_REF.md, and fail closed on mismatch.
3. Preserve EVERY previous PASS for the same project + phase + exact SHA + assertion key; merge only improved outcomes and supporting evidence.
4. Do not rerun all 70 projects or re-test unrelated known PASS stages. Keep the original baseline artifact intact and output separate proof artifact per targeted cohort.
5. A corrected malformed probe that is *still not run successfully* remains GRADER_PROBE_FAILURE or unresolved — **not** automatic PASS. Test student implementation using the valid contract before awarding.
6. No grade publication without approved midterm rubric (issue #30) and discussion assessment.

## Planned impacted cohorts

| Cause | Target project snapshots | Only affected stages | Issue |
|---|---|---|---|
| Named queries missing conditional query params | P01 P21 P28 P43 P50 P54 P59 | Final query runtime (five named query requests); reuse already seeded isolated DB when possible | #31 #37 |
| MV refresh omitted required view name | P59 | Final MV refresh and its incremental preconditions | #38 |
| Engine evidence votes polluted by prose | P54 | Re-adjudicate saved Batch engine evidence first; if already definitive, **no student rerun required** | #40 |
| Missing documented --no-reset | P39 | Midterm Upsert insert/update/unchanged; Idempotency; Incremental; baseline only as required to establish state | #41 |
| Spark connector unavailable in network-isolated environment | P04 P05 P14 P15 P26 | Prewarm *exact declared connector* outside sandbox, verify cache, then Spark stage only | #39 |
| Universal env sample requirement | P15 P18 P20 P24 P47 P56 | Static dependency / README checks on frozen source; **no student runtime rerun** | #34 |
| ZIP-only P52 discovery | P52 | Already recovered with 29 PASS. No repeat if same-SHA evidence sufficient | #29 |
| P50 job discovery | P50 | Already PASS on same SHA. No retest needed | #32 |
| Schema validator and Audit sample gaps | Separate evidence-only review per project | Analyze frozen source and recorded samples; no rerun until deterministic probe defined | #35 #36 |
| Unassessed tests/docs and manual discussion | All affected projects | Rubric review / human decision | #30 #33 |

## Execution control
- Prefer the existing targeted workflows (`targeted-final-refresh.yml`, `targeted-midterm-recovery.yml`, `targeted-spark-cohort.yml`) only where the steps demonstrably limit stages.
- The older generic `regrade-affected.yml` performs whole phases and must **not** be used as if it were an assertion-only rerun.
- New runs must produce `project_id, student_frozen_sha, original_run, repair_branch_sha, targeted_assertion_keys, before, after, evidence_refs, grader_root_cause`.
- CI green is required but **is not proof** that a student has passed a retest.
- PR can be merged by an authorized maintainer after review; do not merge or change production grade sheets implicitly.

## Snapshot caveat
The initial freeze run (37390623044) is NOT guaranteed to include the later submissions at the SHAs audited on 2026-10-13. P01/P24/P26 require source-by-source SHA confirmation before triggering any workflow. Never substitute current HEAD for an assessed frozen revision.
