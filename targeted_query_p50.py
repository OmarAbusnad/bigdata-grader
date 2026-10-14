#!/usr/bin/env python3
"""P50: retry only the formerly malformed high_value_orders named query.

The other four previously passing P50 named queries are NEVER called.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pymongo import MongoClient

from grader.final_runtime import _probe_python, _probe_shell, _extract_probe, _fixture_docs
from grader.sandbox import DockerSandbox, SandboxConfig


FROZEN_SHA = "e3c74fdd8e5a36e80ce1a8d0337733f0ca64add3"
DB_NAME = "bigdata_elt"
MIN_AMOUNT = 200.0
EXPECTED_FIXTURE_RESULTS = 7


def restricted_query_probe_source() -> str:
    full = _probe_python()
    anchor = 'result = {"server_ready": False}'
    if full.count(anchor) != 1:
        raise RuntimeError("Cannot safely isolate upstream API request helpers")
    support = full.split(anchor, 1)[0]
    focused = r'''
result = {"server_ready": False, "only_query": "high_value_orders"}
for _ in range(35):
    health = request("GET", "/openapi.json", timeout=2)
    if health.get("ok"):
        result["server_ready"] = True
        break
    time.sleep(1)
if result["server_ready"]:
    listing = request("GET", "/queries", timeout=30)
    metadata = ((listing.get("body") or {}).get("queries") or {}).get("high_value_orders") or {}
    declared_defaults = set(metadata.get("default_params") or {})
    result["documented_params"] = sorted(declared_defaults)
    if not {"min_amount", "limit"}.issubset(declared_defaults):
        result["probe_blocked"] = "required_query_metadata_missing"
    elif "start_date" in declared_defaults or "end_date" in declared_defaults:
        result["probe_blocked"] = "frozen_query_contract_changed"
    else:
        result["request_params"] = {"min_amount": 200.0, "limit": 10}
        result["query"] = request(
            "GET", "/queries/high_value_orders?min_amount=200&limit=10", timeout=60
        )
print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''
    return support + focused


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    mount = Path.cwd() / "sandboxes" / "P50" / "only_failed_high_value_query"
    mount.mkdir(parents=True, exist_ok=True)
    (mount / "targeted_query_probe.py").write_text(
        restricted_query_probe_source(), encoding="utf-8"
    )
    base_shell = _probe_shell()
    original = "python /grader-tests/final_api_probe.py"
    if base_shell.count(original) != 1:
        raise RuntimeError("Could not safely restrict original API probe")
    (mount / "targeted_query.sh").write_text(
        base_shell.replace(original, "python /grader-tests/targeted_query_probe.py"),
        encoding="utf-8",
    )
    evidence = {
        "project_id": "P50",
        "frozen_commit": FROZEN_SHA,
        "scope": ["final.queries.high_value_orders"],
        "source_run_id": 37874152827,
        "freeze_run_id": 37390623044,
        "previous_passes_retested": 0,
        "student_source_modified": False,
        "official_grade_changed": False,
    }
    sb = DockerSandbox(
        Path.cwd(), "P50-query-only", args.repo, mount,
        SandboxConfig(network_profile="isolated", timeout_seconds=700),
    )
    try:
        built = sb.build()
        evidence["build_ok"] = bool(built.get("ok"))
        if not built.get("ok"):
            evidence["build_error"] = str(built.get("stderr_tail") or "")[-1800:]
            evidence["verdict"] = "INCONCLUSIVE"
            return
        sb.start()
        sb.reset_database(DB_NAME)
        fixtures = _fixture_docs()
        with MongoClient(sb.mongo_host_uri, serverSelectionTimeoutMS=10000) as client:
            client[DB_NAME]["orders_validated"].insert_many(
                fixtures, ordered=False, bypass_document_validation=True
            )
            evidence["input_count"] = len(fixtures)
        executed = sb.run_student(
            "bash /grader-tests/targeted_query.sh",
            env={
                "FINAL_API_TARGET": "src.api:app",
                "DB_NAME": DB_NAME,
                "MONGO_DATABASE": DB_NAME,
                "MONGO_DB_NAME": DB_NAME,
                "MONGODB_DATABASE": DB_NAME,
            },
            timeout=630,
        )
        probe = _extract_probe(str(executed.get("stdout") or ""))
        result = probe.get("query") or {}
        body = result.get("body") if isinstance(result, dict) else {}
        body = body if isinstance(body, dict) else {}
        rows = body.get("data") or []
        expected = EXPECTED_FIXTURE_RESULTS
        data_ok = (
            isinstance(rows, list)
            and len(rows) == expected
            and body.get("count") == expected
            and all(
                isinstance(row, dict) and float(row.get("total_amount") or -1) >= MIN_AMOUNT
                for row in rows
            )
        )
        evidence["probe"] = {
            "server_ready": probe.get("server_ready"),
            "documented_params": probe.get("documented_params"),
            "request_params": probe.get("request_params"),
            "probe_blocked": probe.get("probe_blocked"),
            "http_status": result.get("status") if isinstance(result, dict) else None,
            "ok": result.get("ok") if isinstance(result, dict) else False,
            "response_status": body.get("status"),
            "observed_count": body.get("count"),
            "expected_count": expected,
            "data_consistent": data_ok,
        }
        evidence["runtime"] = {
            "returncode": executed.get("returncode"),
            "timed_out": executed.get("timed_out"),
            "log_excerpt": str(executed.get("stderr") or "")[-1800:],
        }
        evidence["verdict"] = (
            "PASS"
            if probe.get("server_ready") and result.get("ok")
            and body.get("status") == "SUCCESS" and data_ok
            else "INCONCLUSIVE"
        )
    except Exception as exc:
        evidence["verdict"] = "INCONCLUSIVE"
        evidence["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            sb.cleanup()
        except Exception as exc:
            evidence["cleanup_warning"] = str(exc)
        args.out.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({
            k: evidence.get(k)
            for k in ("project_id", "verdict", "error", "probe")
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
