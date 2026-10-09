#!/usr/bin/env python3
"""P59: prove ONLY formerly failed /refresh-mv and incremental behavior.

Based on frozen P59 src/api.py: /refresh-mv requires query name; permitted
source names are city_sales and daily_sales. This run cannot regrade any PASS.
"""
import argparse
import json
from pathlib import Path

from pymongo import MongoClient
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.final_runtime import _probe_python, _probe_shell, _extract_probe, _fixture_docs


def restricted_probe_source():
    helper = _probe_python().split('result = {"server_ready": False}', 1)[0]
    if not helper or "def request(" not in helper:
        raise RuntimeError("Cannot isolate probe helpers")
    code = String = r'''
result = {"server_ready": False, "scope": ["final.mv.refresh", "final.mv.incremental"]}
for _ in range(35):
    health = request("GET", "/openapi.json", timeout=2)
    if health.get("ok"):
        result["server_ready"] = True
        break
    time.sleep(1)
if result["server_ready"]:
    # Frozen P59's validated src/api.py defines name: str = Query(...).
    # Frozen src/materialized_views/mv_01_city_sales.py supports both modes.
    path = "/refresh-mv?name=city_sales&full_refresh="
    result["first"] = request("POST", path + "true", {}, timeout=120)
    result["second"] = request("POST", path + "false", {}, timeout=120)
print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''
    return helper + code


def snapshot(client, name):
    db=client[name]
    return {
        "validated": db["orders_validated"].count_documents({}),
        "mv_city_sales": db["mv_city_sales"].count_documents({}),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    base=Path.cwd()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    mount=base/"sandboxes"/"P59"/"only_failed_refresh"
    mount.mkdir(parents=True,exist_ok=True)
    (mount/"targeted_refresh_probe.py").write_text(restricted_probe_source(),encoding="utf-8")
    old="python /grader-tests/final_api_probe.py"
    shell=_probe_shell()
    if shell.count(old)!=1:raise RuntimeError("Unable to restrict API probe")
    (mount/"targeted_refresh.sh").write_text(shell.replace(old,"python /grader-tests/targeted_refresh_probe.py"),encoding="utf-8")
    db_name="midterm_orders_pipeline_30m_final"
    result={
        "project_id":"P59",
        "scope":["final.mv.refresh","final.mv.incremental"],
        "source_run_id":37874152827,
        "freeze_run_id":37390623044,
        "other_checks_executed":False,
        "official_grades_modified":False,
    }
    sandbox=DockerSandbox(base,"P59-only-refresh",args.repo,mount,SandboxConfig(network_profile="isolated",timeout_seconds=700))
    try:
        build=sandbox.build()
        result["build_ok"]=bool(build.get("ok"))
        if not build.get("ok"):
            result["build_error"]=str(build.get("stderr_tail") or "")[-2000:]
            return
        sandbox.start()
        sandbox.reset_database(db_name)
        with MongoClient(sandbox.mongo_host_uri,serverSelectionTimeoutMS=10000) as client:
            client[db_name]["orders_validated"].insert_many(_fixture_docs(),ordered=False,bypass_document_validation=True)
            result["before"]=snapshot(client,db_name)
        executed=sandbox.run_student(
            "bash /grader-tests/targeted_refresh.sh",
            env={"FINAL_API_TARGET":"src.api:app","MONGO_DATABASE":db_name,
                 "MONGODB_DATABASE":db_name,"MONGO_DB_NAME":db_name,"DB_NAME":db_name},
            timeout=630,
        )
        result["probe"]=_extract_probe(str(executed.get("stdout") or ""))
        result["runtime"]={"returncode":executed.get("returncode"),
                           "timed_out":executed.get("timed_out"),
                           "log":str(executed.get("stderr") or executed.get("stdout") or "")[-2200:]}
        with MongoClient(sandbox.mongo_host_uri,serverSelectionTimeoutMS=10000) as client:
            result["after"]=snapshot(client,db_name)
        probe=result["probe"]
        first,second=probe.get("first") or {},probe.get("second") or {}
        result["refresh_http_2xx"]=bool(first.get("ok"))
        result["incremental_http_2xx"]=bool(second.get("ok"))
        result["refresh_data_proven"]=bool(first.get("ok") and result["after"]["mv_city_sales"]>0)
        second_text=json.dumps(second.get("body"),ensure_ascii=False).lower()
        result["incremental_mode_proven"]=bool(second.get("ok") and "incremental" in second_text)
        result["verdict_refresh"]="PASS" if result["refresh_data_proven"] else "INCONCLUSIVE"
        result["verdict_incremental"]="PASS" if result["incremental_mode_proven"] else "INCONCLUSIVE"
    except Exception as exc:
        result["error"]=f"{type(exc).__name__}: {exc}"
        result["verdict_refresh"]="INCONCLUSIVE"
        result["verdict_incremental"]="INCONCLUSIVE"
    finally:
        try:sandbox.cleanup()
        except Exception as exc:result["cleanup_warning"]=str(exc)
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:result.get(k) for k in ["project_id","verdict_refresh","verdict_incremental","error"]},ensure_ascii=False))


if __name__=="__main__":
    main()
