#!/usr/bin/env python3
"""Only P01 later-SHA orders_in_period: never rerun other four successful queries."""
import argparse
import json
from pathlib import Path
from pymongo import MongoClient
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.final_runtime import _probe_python, _probe_shell, _extract_probe

SHA="c43aae3d5e9c0d96731640206752f886f2618497"
DB="midterm_data_pipeline_bigdata"

def scoped_source():
    root=_probe_python()
    anchor='result = {"server_ready": False}'
    if root.count(anchor)!=1:
        raise RuntimeError("Cannot extract single API request helper")
    return root.split(anchor,1)[0]+r'''
result={"server_ready":False,"scope":["orders_in_period"]}
for _ in range(35):
    ready=request("GET","/openapi.json",timeout=2)
    if ready.get("ok"):
        result["server_ready"]=True
        break
    time.sleep(1)
if result["server_ready"]:
    listing=request("GET","/queries",timeout=15)
    names=(listing.get("body") or {})
    result["declared"]=isinstance(names,dict) and "orders_in_period" in names
    if result["declared"]:
        result["query"]=request(
            "GET","/queries/orders_in_period?start=2026-01-01&end=2026-12-31&limit=10",
            timeout=60
        )
print("FINAL_PROBE_JSON="+json.dumps(result,ensure_ascii=False))
'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    result={"project_id":"P01","exact_student_sha":SHA,"original_run":38424927615,
            "scope":["final.queries.orders_in_period"],"old_4_pass_retested":0,
            "student_source_modified":False,"academic_grade_changed":False}
    mount=Path.cwd()/"sandboxes"/"P01"/"orders_in_period_only"
    mount.mkdir(parents=True,exist_ok=True)
    try:
        (mount/"only_period.py").write_text(scoped_source(),encoding="utf-8")
        shell=_probe_shell()
        needle="python /grader-tests/final_api_probe.py"
        if shell.count(needle)!=1:
            raise RuntimeError("Cannot safely scope grader final probe")
        (mount/"only_period.sh").write_text(
            shell.replace(needle,"python /grader-tests/only_period.py"),encoding="utf-8")
        sb=DockerSandbox(Path.cwd(),"P01-later-only-period",args.repo,mount,
                         SandboxConfig(network_profile="isolated",timeout_seconds=700))
        try:
            built=sb.build()
            result["build_ok"]=bool(built.get("ok"))
            if not built.get("ok"):
                result["verdict"]="INCONCLUSIVE"
                result["block_owner"]="GRADER_INFRA_FAILURE_OR_STUDENT_DEPENDENCY_UNRESOLVED"
                result["build_error"]=str(built.get("stderr_tail") or "")[-1100:]
                return
            sb.start()
            sb.reset_database(DB)
            with MongoClient(sb.mongo_host_uri,serverSelectionTimeoutMS=10000) as client:
                col=client[DB]["orders_validated"]
                col.insert_many([
                    {"order_id":"GRADER-P01-2026","order_date":"2026-03-01",
                     "customer_id":"CUST-001","status":"delivered","city":"Sanaa",
                     "total_amount":420.0},
                    {"order_id":"GRADER-P01-2025","order_date":"2025-03-01",
                     "customer_id":"CUST-002","status":"pending","city":"Aden",
                     "total_amount":85.0}
                ])
            executed=sb.run_student("bash /grader-tests/only_period.sh",
                 env={"FINAL_API_TARGET":"src.api:app","DB_NAME":DB,
                      "MONGODB_DATABASE":DB,"MONGO_DATABASE":DB}, timeout=630)
            probe=_extract_probe(str(executed.get("stdout") or ""))
            reply=probe.get("query") or {}
            body=reply.get("body") or {}
            rows=body.get("results") if isinstance(body,dict) else None
            exact=(isinstance(rows,list) and len(rows)==1
                   and rows[0].get("order_id")=="GRADER-P01-2026")
            result["evidence"]={
                "api_ready":probe.get("server_ready"),"declared_name":probe.get("declared"),
                "http_status":reply.get("status"),"http_ok":reply.get("ok"),
                "positive_and_negative_date_filter_exact":exact,
                "observed_rows":len(rows) if isinstance(rows,list) else None,
                "returncode":executed.get("returncode"),
                "timed_out":executed.get("timed_out")}
            result["verdict"]="PASS" if all((
                 result["evidence"]["api_ready"],result["evidence"]["declared_name"],
                 result["evidence"]["http_ok"],exact,
                 executed.get("returncode")==0,not executed.get("timed_out")
            )) else "INCONCLUSIVE"
            if result["verdict"]!="PASS":
                result["stderr_tail"]=str(executed.get("stderr") or "")[-1300:]
        finally:
            try:sb.cleanup()
            except Exception as exc:result["cleanup_warning"]=type(exc).__name__
    except Exception as exc:
        result["verdict"]="INCONCLUSIVE"
        result["error"]=type(exc).__name__+": "+str(exc)[:900]
    finally:
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({k:result.get(k) for k in ("project_id","verdict","evidence","error")},ensure_ascii=False))
if __name__=="__main__":
    main()
