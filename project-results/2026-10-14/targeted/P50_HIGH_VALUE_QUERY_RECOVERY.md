# P50 — high_value_orders query is now proven on the identical frozen student source

- **Student:** رغد إسكندر ثابت الصغير مقبل
- **Frozen SHA:** `e3c74fdd8e5a36e80ce1a8d0337733f0ca64add3`
- **Student source:** [src/api.py](https://github.com/raghadeskander27/hybrid-bigdata-elt-pipeline/blob/e3c74fdd8e5a36e80ce1a8d0337733f0ca64add3/src/api.py) and [src/queries.py](https://github.com/raghadeskander27/hybrid-bigdata-elt-pipeline/blob/e3c74fdd8e5a36e80ce1a8d0337733f0ca64add3/src/queries.py)
- **Original assessment:** [run 37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827); `final.queries.runtime` INCONCLUSIVE when extra dates were injected.
- **Guarded targeted rerun:** [run 38609876440](https://github.com/omrbosnd/bigdata-grader/actions/runs/38609876440)
- **Raw Actions result:** `p50-high-value-only-38609876440` (artifact `11917640064`)
- **New source unchanged:** freeze and original `reports_final/P50/result.json` SHA guard passed.
- **Grader code at rerun:** `a70e5a77b7f8b1fde51333974fa2e99bc19262ee` (execution on branch, with subsequent source-documentation commit not affecting this test).

## Actual output from the targeted step

```json
{
  "project_id": "P50",
  "verdict": "PASS",
  "error": null,
  "probe": {
    "server_ready": true,
    "documented_params": ["limit", "min_amount"],
    "request_params": {"min_amount": 200.0, "limit": 10},
    "probe_blocked": null,
    "http_status": 200,
    "ok": true,
    "response_status": "SUCCESS",
    "observed_count": 7,
    "expected_count": 7,
    "data_consistent": true
  }
}
```

## Fair academic interpretation

The fifth named query `high_value_orders` PASSED when invoked according to its frozen API metadata. Four other named queries had already succeeded on the **same source SHA** in earlier final evidence; preserve those PASS. The original `final.queries.runtime` INCONCLUSIVE was caused by an **invalid grader-generated request**, not a failing query implementation. The combined same-SHA evidence now supports completing the five-query runtime coverage without re-running the four successes.

This is an assertion-level PASS proof; **no academic score has been modified or published**. All evidence must be folded into the approved rubric and the historic-PASS ledger, with the discussion assessed separately.

[Grader issue #31](https://github.com/omrbosnd/bigdata-grader/issues/31).
