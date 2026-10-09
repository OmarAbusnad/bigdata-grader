"""Re-assess ONLY previously failed midterm count assertions from immutable saved evidence.

No student code is executed, no hidden data is regenerated, and previous PASS
assertions are frozen. The output is a review-only overlay, not a formal grade.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .count_policy import (
    CountDecision,
    compare_count,
    compare_new_inserts,
    compare_stability,
    compare_baseline_replay,
)

POLICY_VERSION = "midterm-evidence-overlay-v1.0"
AFFECTED_KEYS = {
    "batch.validated_count", "batch.quarantine_count",
    "spark.raw_count", "spark.validated_count", "spark.quarantine_count",
    "upsert.baseline_validated", "upsert.final_validated",
    "idempotency.validated_stable", "incremental.final_validated",
    "incremental.rerun_validated_stable",
}


def _integer(x: Any) -> int | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = int(x)
        return v if v >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _executed(case: dict[str, Any] | None) -> bool:
    if not case:
        return False
    run = case.get("run") or {}
    # A successful command and an actual snapshot are mandatory before any
    # PASS may be established from old measurements.
    return (run.get("returncode") == 0 and not run.get("timed_out")
            and isinstance(case.get("snapshot_after"), dict))


def regrade_saved_midterm(report: dict[str, Any], *, source_run_id: int) -> dict[str, Any]:
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("Expected reports/<project>/result.json with runtime")
    assertions = runtime.get("assertions") or {}
    cases = {c.get("name"): c for c in (runtime.get("cases") or []) if isinstance(c, dict)}
    pid = report.get("project_id")
    if not pid or not isinstance(assertions, dict):
        raise ValueError("Missing project identifier or midterm assertions")

    payload_hash = hashlib.sha256(json.dumps(runtime, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    overrides: dict[str, Any] = {}
    preserved_passes = [key for key, a in assertions.items() if a.get("verdict") == "PASS"]
    skipped = []
    for key in sorted(AFFECTED_KEYS):
        old = assertions.get(key)
        if not old or old.get("verdict") != "FAIL":
            continue
        decision: CountDecision | None = None
        deps = []
        if key.startswith("batch."):
            deps = ["batch_pipeline"]
            if _executed(cases.get("batch_pipeline")):
                decision = compare_count(old.get("actual"), old.get("expected"))
        elif key.startswith("spark."):
            deps = ["spark_pipeline"]
            if _executed(cases.get("spark_pipeline")):
                decision = compare_count(old.get("actual"), old.get("expected"))
        elif key == "upsert.baseline_validated":
            deps = ["batch_pipeline", "upsert_baseline"]
            if all(_executed(cases.get(n)) for n in deps):
                expected_batch_observed = (cases["batch_pipeline"].get("snapshot_after") or {}).get("validated")
                current = (cases["upsert_baseline"].get("snapshot_after") or {}).get("validated")
                decision = compare_baseline_replay(current, expected_batch_observed)
        elif key == "upsert.final_validated":
            deps = ["upsert_baseline", "upsert_first"]
            base = assertions.get("upsert.baseline_validated") or {}
            expected_delta = None
            x,y = _integer(old.get("expected")),_integer(base.get("expected"))
            if x is not None and y is not None:
                expected_delta = x-y
            if all(_executed(cases.get(n)) for n in deps):
                case = cases["upsert_first"]
                decision = compare_new_inserts((case.get("snapshot_after") or {}).get("validated"),
                                               (case.get("snapshot_before") or {}).get("validated"),
                                               expected_delta)
        elif key == "incremental.final_validated":
            deps = ["upsert_first", "incremental_first"]
            base = assertions.get("upsert.final_validated") or {}
            expected_delta = None
            x,y = _integer(old.get("expected")),_integer(base.get("expected"))
            if x is not None and y is not None:
                expected_delta = x-y
            if all(_executed(cases.get(n)) for n in deps):
                case = cases["incremental_first"]
                decision = compare_new_inserts((case.get("snapshot_after") or {}).get("validated"),
                                               (case.get("snapshot_before") or {}).get("validated"),
                                               expected_delta)
        elif key in {"idempotency.validated_stable", "incremental.rerun_validated_stable"}:
            step = "upsert_rerun" if key.startswith("idempotency") else "incremental_rerun"
            deps = ["upsert_first", "upsert_rerun"] if step == "upsert_rerun" else ["incremental_first", "incremental_rerun"]
            if all(_executed(cases.get(n)) for n in deps):
                case = cases[step]
                decision = compare_stability((case.get("snapshot_after") or {}).get("validated"),
                                             (case.get("snapshot_before") or {}).get("validated"))

        if decision is None or decision.verdict == "FAIL":
            skipped.append({"key":key, "reason":"insufficient_executable_evidence_or_still_failing"})
            continue
        overrides[key] = {
            "previous": old.get("verdict"),
            "new": decision.verdict,
            "expected": decision.expected,
            "observed": decision.actual,
            "relative_error": decision.error_ratio,
            "reason": decision.reason,
            "proof_cases": deps,
            "source": "immutable_runtime_snapshots",
            "scope": "count_only_not_full_pipeline_correctness",
        }
    # This is NOT an automatic score. Previous PASS and unaffected FAIL remain fixed.
    revised = dict(runtime.get("assertion_counts") or {})
    for key, entry in overrides.items():
        revised["FAIL"] = revised.get("FAIL", 0)-1
        revised[entry["new"]] = revised.get(entry["new"], 0)+1

    return {
        "policy": POLICY_VERSION,
        "project_id": pid,
        "student_commit": report.get("commit_sha"),
        "source_run_id": source_run_id,
        "source_runtime_sha256": payload_hash,
        "source_midterm_status": runtime.get("status"),
        "original_assertion_counts": runtime.get("assertion_counts"),
        "revised_assertion_counts": revised,
        "preserved_pass_keys": preserved_passes,
        "overrides": overrides,
        "remaining_fail_keys": [k for k,a in assertions.items()
                                if a.get("verdict")=="FAIL" and k not in overrides],
        "skipped_affected_failed_keys": skipped,
        "official_grade_approved": False,
        "student_execution_performed": False,
    }
