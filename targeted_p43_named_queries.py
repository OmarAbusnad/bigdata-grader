#!/usr/bin/env python3
"""P43: re-evaluate only five originally malformed named queries on frozen SHA."""
import argparse
import json
from pathlib import Path

from pymongo import MongoClient
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.final_runtime import _probe_python, _probe_shell, _extract_probe

SHA = "cbbc33924cccddfd77ae0e4cc5784c36db3d22c5"
DB = "shehab_bigdata"
NAMES = ["orders_by_city", "orders_by_status", "customer_orders", "orders_by_date_range", "high_value_orders"]


def scoped_probe():
    source = _probe_python()
    marker = 'result = {"server_ready": False}'
    if source.count(marker) != 1:
        raise RuntimeError("Unsafe API request helper extraction")
    return source.split(marker, 1)[0] + r'''
result = {"server_ready": False, "scope": [
    "orders_by_city", "orders_by_status", "customer_orders",
    "orders_by_date_range", "high_value_orders"
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
    result["advertised"] = [item.get("name") for item in advertised if isinstance(item, dict)]
    params = {
        "orders_by_city": "?city=Sanaa&limit=10",
        "orders_by_status": "?status=Delivered&limit=10",
        "customer_orders": "?customer_id=CUST-001&limit=10",
        "orders_by_date_range": "?start_date=2026-01-01&end_date=2026-12-31&limit=10",
        "high_value_orders": "?min_total=200&limit=10",
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
    result = {"project_id": "P43", "frozen_sha": SHA, "original_run": 37874152827,
              "scope": NAMES, "previous_passes_retested": 0,
              "student_files_modified": False, "grades_modified": False}
    mount = Path.cwd() / "sandboxes" / "P43" / "query_recovery"
    mount.mkdir(parents=True, exist_ok=True)
    (mount / "focused_query.py").write_text(scoped_probe(), encoding="utf-8")
    shell = _probe_shell()
    anchor = "python /grader-tests/final_api_probe.py"
    if shell.count(anchor) != 1:
        raise RuntimeError("Cannot scope original API shell")
    (mount / "focused_query.sh").write_text(
        shell.replace(anchor, "python /grader-tests/focused_query.py"),
        encoding="utf-8")
    sb = DockerSandbox(Path.cwd(), "P43-queries-only", args.repo, mount,
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
                {"order_id": "GRADER-P43-001", "customer_id": "CUST-001",
                 "city": "Sanaa", "status": "Delivered", "quality_status": "valid",
                 "order_date": "2026-03-01", "total_amount": 500.0},
                {"order_id": "GRADER-P43-002", "customer_id": "CUST-002",
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
            rows = body.get("documents") if isinstance(body, dict) else None
            matched = (isinstance(rows, list) and len(rows) == 1 and
                       rows[0].get("order_id") == "GRADER-P43-001")
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
            "project_id": "P43", "verdict": result.get("verdict"),
            "queries": (result.get("evidence") or {}).get("queries"),
            "error": result.get("error"),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
