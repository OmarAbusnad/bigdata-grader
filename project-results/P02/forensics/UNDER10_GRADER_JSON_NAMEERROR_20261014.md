# Confirmed grader runtime failure in under10 retests — 2026-10-14

- Reproduced in [under10 exact-SHA run 38632370130](https://github.com/omrbosnd/bigdata-grader/actions/runs/38632370130), P02 artifact `under10-deadline-P02-38632370130` ID `11926891059`.
- P02 frozen SHA `f5558c250922f306e0389c7c915edc5c78e9ba05`: midterm report reports `INFRA_OR_RUNTIME_ERROR` with `NameError: name 'json' is not defined` before the assessed midterm assertions.
- Grader root cause: `grader/sandbox_runtime.py` line ~719 serializes MongoDB schema validator evidence using `json.dumps(...)`, but its imports lacked `import json`.
- **Responsibility:** `GRADER_PROBE_FAILURE` / grader implementation. This is not proof of a student error. Do not make any academic deductions from this incomplete run.
- Fix: standard-library JSON import plus regression test. A follow-up only on affected and explicitly blocked midterm stages may be considered after guarding exact assessed student SHAs. Do not re-run already passing final P02 tests.
- P02 final same-SHA output was `24 PASS / 0 FAIL / 1 INCONCLUSIVE`, with discussion manually pending. Historical PASS protection applies.
