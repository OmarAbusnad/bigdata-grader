"""Evidence-only repair of previously blocked Spark Test02 assertions.

Accepts only the exact originally frozen commit and an independently successful
Spark-only execution. Never changes a PASS or invents student grades.
"""
from __future__ import annotations

import json
from typing import Any

from .count_policy import compare_count

KEYS = (
    "spark_pipeline.command", "spark_pipeline.engine",
    "spark.raw_count", "spark.validated_count",
    "spark.quarantine_count", "spark.duplicates",
)


def spark_recovery_overlay(original: dict[str, Any], proof: dict[str, Any], *,
                           proof_run_id: int) -> dict[str, Any]:
    pid = original.get("project_id")
    if not pid or proof.get("project_id") != pid:
        raise ValueError("Project identity mismatch in frozen Spark evidence")
    if proof.get("source_run") != 37874152827:
        raise ValueError("Unexpected original grading source")
    if proof.get("frozen_commit") != original.get("commit_sha"):
        raise ValueError("Frozen student's source SHA differs")
    if proof.get("passed_tests_reexecuted") != 0 or proof.get("other_tests_reexecuted") != 0:
        raise ValueError("Proof did not preserve original successful tests")
    if proof.get("official_grade_changed") is not False:
        raise ValueError("Refusing altered official grade source")
    runtime = original.get("runtime") or {}
    current = runtime.get("assertions") or {}
    if not isinstance(current, dict):
        raise ValueError("Missing official assertions")
    old = current.get("spark_pipeline.command") or {}
    if old.get("verdict") == "PASS":
        raise ValueError("Original Spark stage was already PASS; must not replay")
    if proof.get("only_test") != "spark_pipeline.command":
        raise ValueError("Recovery proof outside permitted Spark-only scope")

    run = proof.get("run") or {}
    after = proof.get("after") or {}
    success = (
        proof.get("verdict") == "PASS"
        and run.get("returncode") == 0
        and run.get("timed_out") is False
        and proof.get("engine") == "pyspark"
        and isinstance(after.get("raw"), int)
        and after.get("raw") > 0
    )

    overrides = {}
    if success:
        tests = {
            "spark_pipeline.command": ("PASS", "Spark program finished with exit 0"),
            "spark_pipeline.engine": ("PASS", "Spark engine proved during execution"),
        }
        for key,field in [
            ("spark.raw_count", "raw"),
            ("spark.validated_count", "validated"),
            ("spark.quarantine_count", "quarantine"),
        ]:
            expected = (current.get(key) or {}).get("expected")
            observed = after.get(field)
            decision = compare_count(observed, expected)
            if decision.verdict in {"PASS", "FAIL"}:
                tests[key] = (
                    decision.verdict,
                    "MongoDB persisted count matches original frozen oracle under approved count band"
                    if decision.verdict == "PASS" else
                    "Executed Spark pipeline completed but validated/original expected count differs from persisted MongoDB evidence",
                )
        dup_expected = (current.get("spark.duplicates") or {}).get("expected")
        duplicates = after.get("duplicate_business_keys")
        if duplicates == 0 and dup_expected == 0:
            tests["spark.duplicates"] = ("PASS", "MongoDB duplicate business keys = 0")

        for key,(verdict,reason) in tests.items():
            current_test = current.get(key) or {}
            if current_test.get("verdict") in {"INCONCLUSIVE","FAIL"}:
                overrides[key] = {
                    "from": current_test["verdict"],
                    "to": verdict,
                    "reason": reason,
                    "observed": (run.get("returncode") if key == "spark_pipeline.command"
                                 else proof.get("engine") if key == "spark_pipeline.engine"
                                 else after.get({
                                     "spark.raw_count":"raw",
                                     "spark.validated_count":"validated",
                                     "spark.quarantine_count":"quarantine",
                                     "spark.duplicates":"duplicate_business_keys",
                                 }.get(key))),
                    "source_run": proof_run_id,
                    "source_assertion": key,
                    "scope": "spark_test02_only",
                }
    return {
        "project_id": pid,
        "source_run": 37874152827,
        "proof_run": proof_run_id,
        "source_commit": original.get("commit_sha"),
        "recovery_success": success,
        "overrides": overrides,
        "untouched_passes": sorted(
            k for k,v in current.items() if v.get("verdict") == "PASS"
        ),
        "other_tests_reexecuted": 0,
        "formal_grade_approved": False,
    }


def load_from_json(original_path, proof_path, proof_run_id):
    from pathlib import Path
    return spark_recovery_overlay(
        json.loads(Path(original_path).read_text(encoding="utf-8")),
        json.loads(Path(proof_path).read_text(encoding="utf-8")),
        proof_run_id=proof_run_id,
    )
