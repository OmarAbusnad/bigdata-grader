#!/usr/bin/env python3
"""P28: re-evaluate only five originally malformed named queries on frozen SHA."""
import argparse
import json
from pathlib import Path

from pymongo import MongoClient
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.final_runtime import _probe_python, _probe_shell, _extract_probe

SHA = "20f40dafa79b47a7d78f3cecf428d24345ccc05a"
DB = "bigdata_midterm"
NAMES = ["customer_orders", "city_orders", "status_orders", "date_orders", "quality_orders"]


def scoped_probe():
    source = _probe_python()
    marker = 'result = {"server_ready": False}'
    if source.count(marker) != 1:
        raise RuntimeError("Unsafe API request helper extraction")
    return source.split(marker, 1)[0] + r'''
result = {"server_ready": False, "scope": [
    "customer_orders", "city_orders", "status_orders",
    "date_orders", "quality_orders"
]}
for _ in range(35):
    health = request("GET", "/openapi.json", timeout=2)
    if health.get("ok"):
        result["server_ready"] = True
        break
    time.sleep(1)
if result["server_ready"]:
    listing = request("GET", "/queries", timeout=15)
    advertised = (listing.get("body") or {}).get("queries") or {}
    result["advertised"] = sorted(advertised) if isinstance(advertised, dict) else []
    params = {
        "customer_orders": "?value=CUST-001&limit=10",
        "city_orders": "?value=Sanaa&limit=10",
        "status_orders": "?value=Delivered&limit=10",
        "date_orders": "?start=2026-01-01&end=2026-12-31&limit=10",
        "quality_orders": "?value=valid&limit=10",
    }
    result["query_results"] = {}
    for name, suffix in params.items():
        if name in result["advertised"]:
            result["query_results"][name] = request(
                "GET", "/queries/" + name + suffix, timeout=45
            )
print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = {"project_id": "P28", "frozen_sha": SHA, "original_run": 37874152827,
              "scope": NAMES, "previous_passes_retested": 0,
              "student_files_modified": False, "grades_modified": False}
    mount = Path.cwd() / "sandboxes" / "P28" / "query_recovery"
    mount.mkdir(parents=True, exist_ok=True)
    (mount / "focused_query.py").write_text(scoped_probe(), encoding="utf-8")
    shell = _probe_shell()
    anchor = "python /grader-tests/final_api_probe.py"
    if shell.count(anchor) != 1:
        raise RuntimeError("Cannot scope original API shell")
    (mount / "focused_query.sh").write_text(
        shell.replace(anchor, "python /grader-tests/focused_query.py"),
        encoding="utf-8")
    sb = DockerSandbox(Path.cwd(), "P28-queries-only", args.repo, mount,
                       SandboxConfig(network_profile="isolated", timeout_seconds=700))
    try:
        built = sb.build()
        result["build_ok"] = bool(built.get("ok"))
        if not built.get("ok"):
            result["verdict"] = "INCONCLUSIVE"
            result["build_error"] = str(built.get("stderr_tail") or "")[-1200:]
            return
        sb.start()
        sb.reset_database(DB)
        with MongoClient(sb.mongo_host_uri, serverSelectionTimeoutMS=10000) as client:
            client[DB]["orders_validated"].insert_many([
                {"order_id": "GRADER-P28-001", "customer_id": "CUST-001",
                 "city": "Sanaa", "status": "Delivered", "quality_status": "valid",
                 "order_date": "2026-03-01", "total_amount": 120.0},
                {"order_id": "GRADER-P28-002", "customer_id": "CUST-002",
                 "city": "Aden", "status": "Pending", "quality_status": "corrected",
                 "order_date": "2025-03-01", "total_amount": 90.0},
            ])
        run = sb.run_student(
            "bash /grader-tests/focused_query.sh",
            env={"FINAL_API_TARGET": "src.phase2.api:app", "MONGO_DATABASE": DB,
                 "DB_NAME": DB, "MONGODB_DATABASE": DB},
            timeout=630)
        p = _extract_probe(str(run.get("stdout") or ""))
        test_results = {}
        for name in NAMES:
            response = (p.get("query_results") or {}).get(name) or {}
            body = response.get("body") or {}
            rows = body.get("rows") if isinstance(body, dict) else None
            matched = (isinstance(rows, list) and len(rows) == 1 and
                       rows[0].get("order_id") == "GRADER-P28-001")
            test_results[name] = {
                "http_status": response.get("status"),
                "returned_count": body.get("returned") if isinstance(body, dict) else None,
                "only_expected_record": matched,
                "verdict": "PASS" if response.get("ok") and matched and
                                     body.get("returned") == 1 else "INCONCLUSIVE",
            }
        result["evidence"] = {"api_ready": p.get("server_ready"),
                             "advertised": p.get("advertised"),
                             "queries": test_results,
                             "runtime_code": run.get("returncode"),
                             "timed_out": run.get("timed_out")}
        result["verdict"] = ("PASS" if p.get("server_ready") and
                            all(t["verdict"] == "PASS" for t in test_results.values())
                            else "INCONCLUSIVE")
        if result["verdict"] != "PASS":
            result["stderr_tail"] = str(run.get("stderr") or "")[-1200:]
    except Exception as exc:
        result["verdict"] = "INCONCLUSIVE"
        result["error"] = type(exc).__name__ + ": " + str(exc)[:800]
    finally:
        try: sb.cleanup()
        except Exception as exc: result["cleanup_warning"] = type(exc).__name__
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(json.dumps({
            "project_id": "P28", "verdict": result.get("verdict"),
            "queries": (result.get("evidence") or {}).get("queries"),
            "error": result.get("error"),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
