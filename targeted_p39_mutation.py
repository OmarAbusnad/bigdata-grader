#!/usr/bin/env python3
"""P39 targeted Upsert/Incremental recovery; setup baseline is NOT rescored."""
import argparse
import json
import shutil
from pathlib import Path

from grader.mongo_checker import MongoChecker
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.oracle import HiddenOracle


FROZEN_SHA = "ec844f735a04f351b8e9785d209ddfce74a0c829"
DB_NAME = "midterm_data_pipeline"
COLLECTIONS = {
    "raw": "orders_raw",
    "validated": "orders_validated",
    "quarantine": "orders_quarantine",
}
STAGES = [
    ("baseline_prerequisite_not_rescored", "test_01", False),
    ("upsert_first", "test_03", True),
    ("upsert_rerun", "test_03", True),
    ("incremental_first", "test_04", True),
    ("incremental_rerun", "test_04", True),
]
STAGE_EXPECTATION = {
    "baseline_prerequisite_not_rescored": ("test_03", "baseline_validated_before_test"),
    "upsert_first": ("test_03", "validated_after_first_run"),
    "upsert_rerun": ("test_03", "validated_after_rerun"),
    "incremental_first": ("test_04", "validated_after_first_run"),
    "incremental_rerun": ("test_04", "validated_after_rerun"),
}


def main() -> None:
    p = argparse.ArgumentParser()
    for k in ("repo", "hidden", "original-report", "out"):
        p.add_argument("--" + k, required=True, type=Path)
    a = p.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "project_id": "P39",
        "frozen_sha": FROZEN_SHA,
        "original_run_id": 37874152827,
        "scope": [
            "upsert.final_validated", "idempotency.validated_stable",
            "incremental.final_validated", "incremental.rerun_validated_stable",
        ],
        "prior_PASS_verdicts_unchanged": True,
        "official_grade_changed": False,
        "student_source_modified": False,
        "stages": [],
    }
    sandbox = None
    mongo = None
    try:
        repo = a.repo.resolve()
        source = (repo / "src" / "main.py").read_text(encoding="utf-8-sig")
        docs = (repo / "README.md").read_text(encoding="utf-8-sig")
        assert "--no-reset" in source and "--no-reset" in docs
        assert "reset=not args.no_reset" in source
        old = json.loads(a.original_report.read_text(encoding="utf-8"))
        if old.get("project_id") != "P39" or old.get("commit_sha") != FROZEN_SHA:
            raise ValueError("Original assessed SHA differs from P39 frozen snapshot")
        old_assert = (old.get("runtime") or {}).get("assertions") or {}
        if isinstance(old_assert, dict):
            matched = {k: old_assert.get(k, {}) for k in result["scope"]}
        else:
            matched = {x.get("key"): x for x in old_assert if isinstance(x, dict)}
        if not any(matched.get(k, {}).get("verdict") in ("FAIL", "INCONCLUSIVE")
                   for k in result["scope"]):
            raise ValueError("No unfinished P39 mutation assertion proven; abort retest")

        hidden = a.hidden.resolve()
        oracle = HiddenOracle(hidden / "teacher_key.json",
                              hidden / "teacher_manifest.csv")
        mount = Path.cwd() / "sandboxes" / "P39" / "only_failed_mutation"
        mount.mkdir(parents=True, exist_ok=True)
        for _, dataset, _ in STAGES:
            name = str(oracle.test(dataset)["file"])
            src = hidden / name
            if not src.is_file() or src.name != name:
                raise ValueError("Deterministic fixture missing or unsafe")
            shutil.copy2(src, mount / name)
        sandbox = DockerSandbox(
            Path.cwd(), "P39-mutation-only", repo, mount,
            SandboxConfig(network_profile="isolated", timeout_seconds=900),
        )
        build = sandbox.build()
        result["build_ok"] = bool(build.get("ok"))
        if not build.get("ok"):
            result["build_error"] = str(build.get("stderr_tail") or "")[-1500:]
            result["verdict"] = "INCONCLUSIVE"
            return
        sandbox.start()
        sandbox.reset_database(DB_NAME)
        mongo = MongoChecker(sandbox.mongo_host_uri, DB_NAME, COLLECTIONS)
        mongo.ping()
        for stage, dataset, no_reset in STAGES:
            spec = oracle.test(dataset)
            filename = spec["file"]
            command = "python src/main.py --file-path /grader-tests/" + filename
            if no_reset:
                command += " --no-reset"
            before = mongo.snapshot().to_dict()
            run = sandbox.run_student(command, env={
                "MONGO_DATABASE": DB_NAME,
                "MONGO_DB_NAME": DB_NAME,
                "DB_NAME": DB_NAME,
                "GRADER_RUN": "1",
            }, timeout=600)
            after = mongo.snapshot().to_dict()
            test_key, count_key = STAGE_EXPECTATION[stage]
            expected = int(oracle.test(test_key)[count_key])
            observed = int(after.get("validated") or 0)
            rc = run.get("returncode")
            completed = rc == 0 and not run.get("timed_out")
            checked = (completed and observed == expected and
                       int(after.get("duplicate_business_keys") or 0) == 0)
            record = {
                "stage": stage, "no_reset": no_reset,
                "command": command, "returncode": rc,
                "timed_out": run.get("timed_out"),
                "validated_before": before.get("validated"),
                "validated_after": observed, "expected_validated": expected,
                "duplicates_after": after.get("duplicate_business_keys"),
                "passes_count_and_uniqueness": checked,
                "stderr_tail": str(run.get("stderr") or "")[-1500:] if not completed else "",
            }
            result["stages"].append(record)
            if not completed:
                result["verdict"] = "INCONCLUSIVE"
                result["reason"] = "student_execution_incomplete"
                break
        else:
            scope = result["stages"][1:]
            result["verdict"] = ("PASS" if all(x["passes_count_and_uniqueness"]
                                               for x in scope) else "FAIL")
            result["reason"] = ("documented_no_reset_mutation_pipeline_proven"
                                if result["verdict"] == "PASS" else
                                "completed_mutation_counts_or_uniqueness_differ_from_oracle")
    except Exception as exc:
        result["verdict"] = "INCONCLUSIVE"
        result["error"] = type(exc).__name__ + ": " + str(exc)[:1000]
    finally:
        try:
            if mongo: mongo.close()
            if sandbox: sandbox.cleanup()
        except Exception as exc:
            result["cleanup_warning"] = type(exc).__name__
        a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        print(json.dumps({
            "project_id": "P39", "verdict": result.get("verdict"),
            "reason": result.get("reason"), "error": result.get("error"),
            "stages": [{"stage": x["stage"], "count": x["validated_after"],
                        "expected": x["expected_validated"],
                        "ok": x["passes_count_and_uniqueness"]}
                       for x in result["stages"]],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
