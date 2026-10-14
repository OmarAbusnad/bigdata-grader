#!/usr/bin/env python3
"""P54 sales_by_period: only originally malformed named query, BSON date fixture."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from pymongo import MongoClient

from grader.sandbox import DockerSandbox, SandboxConfig
from grader.final_runtime import _probe_python, _probe_shell, _extract_probe

SHA = "81d9b76c452f27c8941e6da34e00c20071993e49"
DB = "midterm_data_pipeline_bigdata"

def scoped_source():
    root = _probe_python()
    anchor = 'result = {"server_ready": False}'
    if root.count(anchor) != 1:
        raise RuntimeError("Cannot extract only API helpers")
    return root.split(anchor, 1)[0] + r'''
result = {"server_ready": False, "scope": ["sales_by_period"]}
for _ in range(35):
    health = request("GET", "/openapi.json", timeout=2)
    if health.get("ok"):
        result["server_ready"] = True
        break
    time.sleep(1)
if result["server_ready"]:
    listing = request("GET", "/queries", timeout=15)
    items = (listing.get("body") or {}).get("queries") or []
    result["advertised"] = any(
        (isinstance(item, dict) and item.get("name") == "sales_by_period")
        or item == "sales_by_period" for item in items
    )
    if result["advertised"]:
        result["query"] = request(
            "GET",
            "/queries/sales_by_period?start=2026-01-01&end=2026-12-31&limit=20",
            timeout=60,
        )
print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = {"project_id":"P54", "student_sha":SHA,
              "scope":["final.queries.sales_by_period"], "prior_pass_retested":0,
              "academic_grade_changed":False}
    mount = Path.cwd()/"sandboxes"/"P54"/"only_failed_period_query"
    mount.mkdir(parents=True,exist_ok=True)
    (mount/"scoped_period_probe.py").write_text(scoped_source(),encoding="utf-8")
    source = _probe_shell()
    target = "python /grader-tests/final_api_probe.py"
    if source.count(target) != 1:
        raise RuntimeError("Unexpected grader API probe shell")
    (mount/"scoped_period_probe.sh").write_text(
        source.replace(target,"python /grader-tests/scoped_period_probe.py"),
        encoding="utf-8")
    sb=DockerSandbox(Path.cwd(),"P54-period-only",args.repo,mount,
                     SandboxConfig(network_profile="isolated", timeout_seconds=700))
    try:
        build=sb.build()
        result["build_ok"]=bool(build.get("ok"))
        if not build.get("ok"):
            result["verdict"]="INCONCLUSIVE"
            result["build_error"]=str(build.get("stderr_tail") or "")[-1400:]
            return
        sb.start()
        sb.reset_database(DB)
        with MongoClient(sb.mongo_host_uri,serverSelectionTimeoutMS=10000) as client:
            client[DB]["orders_validated"].insert_many([
                {"order_id":"GRADER-DT-001","order_date":datetime(2026,3,2,tzinfo=timezone.utc),
                 "city":"صنعاء","status":"تم التسليم","total_amount":450.0},
                {"order_id":"GRADER-DT-002","order_date":datetime(2025,3,2,tzinfo=timezone.utc),
                 "city":"تعز","status":"تم التسليم","total_amount":650.0}
            ])
        run=sb.run_student(
            "bash /grader-tests/scoped_period_probe.sh",
            env={"FINAL_API_TARGET":"src.api:app","DB_NAME":DB,
                 "MONGODB_DATABASE":DB,"MONGO_DATABASE":DB},timeout=630)
        probe=_extract_probe(str(run.get("stdout") or ""))
        res=probe.get("query") or {}
        body=res.get("body") or {}
        rows=body.get("rows") if isinstance(body,dict) else None
        matched=(isinstance(rows,list) and len(rows)==1 and
                 rows[0].get("order_id")=="GRADER-DT-001")
        result["evidence"]={"server_ready":probe.get("server_ready"),
              "advertised":probe.get("advertised"),
              "http_status":res.get("status"),
              "http_ok":res.get("ok"),
              "returned_rows":len(rows) if isinstance(rows,list) else None,
              "date_filter_matched_expected":matched,
              "runtime_returncode":run.get("returncode"),
              "runtime_timed_out":run.get("timed_out")}
        result["verdict"]=("PASS" if all([
            probe.get("server_ready"),probe.get("advertised"),res.get("ok"),
            matched,run.get("returncode")==0,not run.get("timed_out"),
        ]) else "INCONCLUSIVE")
        if result["verdict"]!="PASS":
            result["stderr_excerpt"]=str(run.get("stderr") or "")[-1300:]
    except Exception as exc:
        result["verdict"]="INCONCLUSIVE"
        result["error"]=type(exc).__name__+": "+str(exc)[:800]
    finally:
        try:sb.cleanup()
        except Exception as exc:result["cleanup_warning"]=type(exc).__name__
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),
                           encoding="utf-8")
        print(json.dumps({"project_id":"P54","verdict":result.get("verdict"),
                          "evidence":result.get("evidence"),"error":result.get("error")},
                          ensure_ascii=False))


if __name__=="__main__":
    main()
