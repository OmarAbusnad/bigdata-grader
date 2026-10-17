#!/usr/bin/env python3
"""Only P21's previously malformed quarantined_by_reason query; exact frozen SHA."""
import argparse
import json
from pathlib import Path
from pymongo import MongoClient
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.final_runtime import _probe_python, _probe_shell, _extract_probe

FROZEN_SHA = "30abeb6575d41c4f173af0bfcf9517f43f120156"
DB = "midterm_data_pipeline"

def probe_source():
    full = _probe_python()
    anchor = 'result = {"server_ready": False}'
    if full.count(anchor) != 1:
        raise RuntimeError("Unsafe API helper extraction")
    prefix = full.split(anchor, 1)[0]
    payload = r'''
result = {"server_ready": False, "scope": ["quarantined_by_reason"]}
for _ in range(35):
    health = request("GET", "/openapi.json", timeout=2)
    if health.get("ok"):
        result["server_ready"] = True
        break
    time.sleep(1)
if result["server_ready"]:
    listing = request("GET", "/queries", timeout=10)
    declared = (listing.get("body") or {}).get("available_queries") or []
    result["declared"] = "quarantined_by_reason" in declared
    if result["declared"]:
        result["query"] = request(
            "GET", "/queries/quarantined_by_reason?reason=INVALID_EMAIL&limit=10", timeout=45
        )
print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''
    return prefix + payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "project_id": "P21", "frozen_sha": FROZEN_SHA,
        "original_run": 37874152827,
        "scope": ["final.queries.quarantined_by_reason"],
        "prior_passes_retested": 0, "academic_grade_modified": False,
    }
    mount = Path.cwd() / "sandboxes" / "P21" / "only_bad_named_query"
    mount.mkdir(parents=True, exist_ok=True)
    (mount / "targeted_query_probe.py").write_text(probe_source(), encoding="utf-8")
    source = _probe_shell()
    needle = "python /grader-tests/final_api_probe.py"
    if source.count(needle) != 1:
        raise RuntimeError("Unsafe helper shell extraction")
    (mount / "targeted_query.sh").write_text(
        source.replace(needle, "python /grader-tests/targeted_query_probe.py"),
        encoding="utf-8",
    )
    sandbox = DockerSandbox(Path.cwd(), "P21-only-query", a.repo, mount,
                            SandboxConfig(network_profile="isolated", timeout_seconds=650))
    try:
        build = sandbox.build()
        result["build_ok"] = bool(build.get("ok"))
        if not build.get("ok"):
            result["verdict"] = "INCONCLUSIVE"
            result["build_error"] = str(build.get("stderr_tail") or "")[-1300:]
            return
        sandbox.start()
        sandbox.reset_database(DB)
        with MongoClient(sandbox.mongo_host_uri, serverSelectionTimeoutMS=10000) as client:
            col = client[DB]["orders_quarantine"]
            col.insert_many([
                {"order_id": "GRADER-Q-001", "quarantine_reasons": "INVALID_EMAIL"},
                {"order_id": "GRADER-Q-002", "quarantine_reasons": "MISSING_PRICE"},
            ])
        executed = sandbox.run_student(
            "bash /grader-tests/targeted_query.sh",
            env={"FINAL_API_TARGET": "src.api:app",
                 "MONGODB_DATABASE": DB, "MONGO_DATABASE": DB, "DB_NAME": DB},
            timeout=560,
        )
        probe = _extract_probe(str(executed.get("stdout") or ""))
        reply = probe.get("query") or {}
        body = reply.get("body") or {}
        data = body.get("data") if isinstance(body, dict) else None
        result["probe"] = {
            "server_ready": probe.get("server_ready"),
            "advertised_name": probe.get("declared"),
            "http_status": reply.get("status"),
            "http_ok": reply.get("ok"),
            "observed_count": len(data) if isinstance(data, list) else None,
            "matched_only_expected_reason": isinstance(data, list) and len(data) == 1
                    and data[0].get("order_id") == "GRADER-Q-001"
                    and data[0].get("quarantine_reasons") == "INVALID_EMAIL",
        }
        result["runtime"] = {
            "returncode": executed.get("returncode"),
            "timed_out": executed.get("timed_out"),
            "stderr_tail": str(executed.get("stderr") or "")[-1200:],
        }
        result["verdict"] = ("PASS" if result["probe"]["server_ready"]
            and result["probe"]["advertised_name"] and result["probe"]["http_ok"]
            and result["probe"]["matched_only_expected_reason"] else "INCONCLUSIVE")
    except Exception as exc:
        result["verdict"] = "INCONCLUSIVE"
        result["error"] = type(exc).__name__ + ": " + str(exc)[:800]
    finally:
        try: sandbox.cleanup()
        except Exception as exc: result["cleanup_warning"] = type(exc).__name__
        a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({
            "project_id": "P21", "verdict": result.get("verdict"),
            "probe": result.get("probe"), "error": result.get("error"),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
