# P59 — completed guarded MV-only recovery (14 Oct 2026)

- **Student project:** `abeeraun/midterm-data-pipeline`
- **Frozen immutable student SHA:** `33cb41e1fe61209929e15e070d73ebe614d47fba`
- **Original grading run:** [37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827)
- **Frozen archive run:** `37390623044`, artifact `frozen-P59-37390623044`
- **Targeted run:** [38607512434](https://github.com/omrbosnd/bigdata-grader/actions/runs/38607512434)
- **Raw artifact:** `targeted-final-refresh-P59-38607512434` (GitHub Actions)
- **Grader commit:** `e899af3f5f540b89157600d5e9a503850792f649`
- **Source verification:** GitHub step `Verify exact assessed frozen P59 revision before student execution` PASSED, confirming exact SHA and frozen tar SHA-256 `f3b14cbee644a8252d4669af9b82b64867a7964214192544b7db20f250cfdb6c`.

## New machine-run outcomes (verbatim step summary)

```json
{"project_id": "P59", "verdict_refresh": "PASS", "verdict_incremental": "PASS", "error": null}
```

| Test assertion | New result |
|---|---|
| `final.mv.refresh` | **PASS** |
| `final.mv.incremental` | **PASS** |

### Integrity restrictions

1. This focused script attempted only documented `POST /refresh-mv?name=city_sales&full_refresh=true` and the corresponding `false` incremental mode, on an isolated MongoDB seeded with fixed fixture documents. No prior PASS was re-tested.
2. This result is a **targeted evidence overlay**, not an overwrite of original grading reports, and **no official mark changed**. Merge into academic grading only when confirmed identical SHA and under active rubric; preserve all previous same-SHA PASS.
3. The raw JSON result and runtime diagnostics remain attached to the Actions run, not embedded publicly because of hidden test data safeguards.
4. The code run exited SUCCESS. Two focused functional verdicts were explicitly PASS, so this is more than mere workflow completion.

**Issue:** [#38](https://github.com/omrbosnd/bigdata-grader/issues/38), where the original grader omitted required view `name`.
