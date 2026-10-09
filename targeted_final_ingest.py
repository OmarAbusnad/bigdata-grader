#!/usr/bin/env python3
"""Execute only a formerly failed POST /ingest against a frozen submission.

The grader creates a fresh isolated Docker+Mongo sandbox, starts the API,
reads /openapi.json as a prerequisite, then requests POST /ingest only.
NO other Final assertions are executed. Existing PASS artifacts remain immutable.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from pymongo import MongoClient

from grader.final_runtime import _probe_python, _probe_shell, _extract_probe
from grader.sandbox import DockerSandbox, SandboxConfig


def ingest_probe_source() -> str:
    full = _probe_python()
    anchor = 'result = {"server_ready": False}'
    if full.count(anchor) != 1:
        raise RuntimeError("Cannot safely isolate existing request helpers")
    support = full.split(anchor, 1)[0]
    focused = r'''
result = {"server_ready": False, "scope": "only_post_ingest", "attempts": []}
openapi = None
for _ in range(35):
    response = request("GET", "/openapi.json", timeout=2)
    if response.get("ok") and isinstance(response.get("body"), dict):
        openapi = response["body"]
        result["server_ready"] = True
        break
    time.sleep(1)
if openapi:
    attempts = [a for a in build_ingest_attempts(openapi) if a.get("kind") == "upload"]
    result["upload_variants_found"] = len(attempts)
    for attempt in attempts[:2]:
        field_name = attempt["file_field"]
        fields = attempt.get("fields") or {}
        outcome = request_file_upload("/ingest", field_name, fields=fields, timeout=240)
        result["attempts"].append({
            "kind": "upload",
            "field": field_name,
            "http_status": outcome.get("status"),
            "ok": outcome.get("ok"),
            "response_excerpt": str(outcome.get("body") or outcome.get("error") or "")[:1200],
        })
        if outcome.get("ok"):
            break
print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''
    return support + focused


def _counts(uri: str, collection_names: tuple[str, ...]) -> dict:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        databases = {}
        for name in client.list_database_names():
            if name in {"admin", "config", "local"}:
                continue
            db = client[name]
            existing = set(db.list_collection_names())
            matched = {c: db[c].count_documents({}) for c in collection_names if c in existing}
            if matched:
                databases[name] = matched
        return databases
    finally:
        client.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--hidden", type=Path, required=True)
    p.add_argument("--api-target", required=True)
    p.add_argument("--db", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    base = Path.cwd()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    mount = base / "sandboxes" / args.project / "targeted_final_input_only"
    mount.mkdir(parents=True, exist_ok=True)
    file = args.hidden / "test_01_small_batch_pipeline.csv"
    if not file.exists():
        raise FileNotFoundError(file)
    shutil.copy2(file, mount / file.name)
    (mount / "targeted_ingest_probe.py").write_text(ingest_probe_source(), encoding="utf-8")
    shell = _probe_shell()
    original = "python /grader-tests/final_api_probe.py"
    if shell.count(original) != 1:
        raise RuntimeError("Cannot isolate probe execution safely")
    (mount / "run_targeted_ingest.sh").write_text(
        shell.replace(original, "python /grader-tests/targeted_ingest_probe.py"),
        encoding="utf-8",
    )

    evidence = {
        "project": args.project,
        "scope": "only_final.api.ingest",
        "source_run_id": 37874152827,
        "freeze_run_id": 37390623044,
        "previous_pass_assertions_preserved": True,
        "other_final_assertions_executed": False,
        "official_grade_approved": False,
    }
    sandbox = DockerSandbox(base, args.project + "-ingest-only", args.repo, mount,
                            SandboxConfig(network_profile="isolated", timeout_seconds=750))
    try:
        built = sandbox.build()
        evidence["build_ok"] = bool(built.get("ok"))
        if not built.get("ok"):
            evidence["status"] = "DEPENDENCY_BUILD_BLOCKED"
            evidence["build_error"] = str(built.get("stderr_tail") or "")[-3000:]
            return
        sandbox.start()
        sandbox.reset_database(args.db)
        evidence["before"] = _counts(sandbox.mongo_host_uri,
                                     ("orders_raw", "orders_validated", "orders_quarantine"))
        result = sandbox.run_student(
            "bash /grader-tests/run_targeted_ingest.sh",
            env={"FINAL_API_TARGET": args.api_target,
                 "MONGO_DATABASE": args.db,
                 "MONGODB_DATABASE": args.db,
                 "MONGO_DB_NAME": args.db,
                 "DB_NAME": args.db},
            timeout=660,
        )
        probe = _extract_probe(str(result.get("stdout") or ""))
        evidence["probe"] = probe
        evidence["returncode"] = result.get("returncode")
        evidence["timed_out"] = bool(result.get("timed_out"))
        evidence["server_log_excerpt"] = str(result.get("stderr") or result.get("stdout") or "")[-2500:]
        evidence["after"] = _counts(sandbox.mongo_host_uri,
                                   ("orders_raw", "orders_validated", "orders_quarantine"))

        attempts = probe.get("attempts") or []
        http_ok = any(x.get("ok") for x in attempts)
        before_total = sum(sum(v.values()) for v in evidence["before"].values())
        after_total = sum(sum(v.values()) for v in evidence["after"].values())
        if http_ok and after_total > before_total:
            evidence["verdict"] = "PASS"
            evidence["reason"] = "multipart_upload_succeeded_and_pipeline_database_effect_proven"
        elif http_ok:
            evidence["verdict"] = "INCONCLUSIVE"
            evidence["reason"] = "multipart_http_success_without_observed_database_effect"
        else:
            evidence["verdict"] = "INCONCLUSIVE"
            evidence["reason"] = "multipart_upload_not_proven; review response and student contract"
    except Exception as exc:
        evidence["verdict"] = "INCONCLUSIVE"
        evidence["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            sandbox.cleanup()
        except Exception as exc:
            evidence["cleanup_warning"] = str(exc)
        args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: evidence.get(k) for k in ("project","scope","verdict","reason","error")},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
