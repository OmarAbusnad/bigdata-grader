"""Retry only frozen P32/P42 Final POST /ingest after proven request-body grader bug.

Does not replay successful Final tests. Requires both HTTP success and a
persisted MongoDB change, never equates a 2xx with academic correctness alone.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from grader.final_runtime import _probe_python, _probe_shell, _extract_probe
from grader.sandbox import DockerSandbox, SandboxConfig
from targeted_final_ingest import _counts


ALLOWED = {"P32": "grader_p32", "P42": "midterm_data_pipeline"}


def json_ingest_only_probe() -> str:
    full=_probe_python()
    anchor='result = {"server_ready": False}'
    if full.count(anchor)!=1:
        raise RuntimeError("Cannot isolate the original grader's helpers")
    support=full.split(anchor,1)[0]
    scoped=r'''
proof = {"server_ready": False, "scope": "only_final.api.ingest", "attempts": []}
openapi = None
for _ in range(35):
    response = request("GET", "/openapi.json", timeout=2)
    if response.get("ok") and isinstance(response.get("body"), dict):
        openapi = response["body"]
        proof["server_ready"] = True
        break
    time.sleep(1)
if openapi:
    json_variants = [a for a in build_ingest_attempts(openapi)
                     if a.get("kind") == "json"]
    proof["json_variants"] = len(json_variants)
    for attempt in json_variants[:7]:
        body = attempt.get("body") or {}
        outcome=request("POST", "/ingest", body, timeout=240)
        proof["attempts"].append({
            "kind": "json", "keys": sorted(body.keys()),
            "status": outcome.get("status"), "ok": outcome.get("ok"),
            "response": str(outcome.get("body") or outcome.get("error") or "")[:900],
        })
        if outcome.get("ok"):
            break
print("FINAL_PROBE_JSON="+json.dumps(proof,ensure_ascii=False))
'''
    return support+scoped


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--project",required=True,choices=sorted(ALLOWED))
    p.add_argument("--repo",required=True,type=Path)
    p.add_argument("--hidden",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    db=ALLOWED[args.project]
    work=Path.cwd()
    mount=work/"sandboxes"/args.project/"final_ingest_only_json"
    mount.mkdir(parents=True,exist_ok=True)
    source=args.hidden/"test_01_small_batch_pipeline.csv"
    if not source.is_file():
        raise FileNotFoundError(source)
    shutil.copy2(source,mount/source.name)
    (mount/"probe_ingest_json.py").write_text(json_ingest_only_probe(),encoding="utf-8")
    shell=_probe_shell()
    token="python /grader-tests/final_api_probe.py"
    if shell.count(token)!=1:
        raise RuntimeError("Expected one API probe invocation")
    (mount/"run_json_ingest_only.sh").write_text(
        shell.replace(token,"python /grader-tests/probe_ingest_json.py"),encoding="utf-8",
    )
    evidence={
        "project":args.project, "scope":"only_final.api.ingest",
        "original_run":37874152827,"freeze_run":37390623044,
        "previous_pass_assertions_preserved":True,
        "other_final_assertions_executed":False,"official_grades_modified":False,
    }
    sandbox=DockerSandbox(work,args.project+"-final-json-ingest",args.repo,mount,
                          SandboxConfig(network_profile="isolated",timeout_seconds=850))
    try:
        build=sandbox.build()
        evidence["build_ok"]=bool(build.get("ok"))
        if not build.get("ok"):
            evidence["verdict"]="INCONCLUSIVE"
            evidence["reason"]="student_container_dependency_build_blocked"
            evidence["build_error"]=str(build.get("stderr_tail") or "")[-2200:]
            return
        sandbox.start()
        sandbox.reset_database(db)
        collections=("orders_raw","orders_validated","orders_quarantine","quarantine_orders")
        before=_counts(sandbox.mongo_host_uri,collections)
        evidence["before"]=before
        result=sandbox.run_student(
            "bash /grader-tests/run_json_ingest_only.sh",
            env={"FINAL_API_TARGET":"src.api:app",
                 "MONGO_DB_NAME":db,"MONGO_DATABASE":db,
                 "MONGODB_DATABASE":db,"DB_NAME":db},
            timeout=720,
        )
        evidence["runtime"]={
            "returncode":result.get("returncode"),
            "timed_out":bool(result.get("timed_out")),
            "stderr_tail":str(result.get("stderr") or "")[-1800:],
        }
        probe=_extract_probe(str(result.get("stdout") or ""))
        evidence["probe"]=probe
        after=_counts(sandbox.mongo_host_uri,collections)
        evidence["after"]=after
        all_success=any(x.get("ok") for x in probe.get("attempts") or [])
        before_total=sum(sum(d.values()) for d in before.values())
        after_total=sum(sum(d.values()) for d in after.values())
        if all_success and after_total>before_total:
            evidence["verdict"]="PASS"
            evidence["reason"]="correct_request_contract_and_new_persisted_mongodb_documents"
        else:
            evidence["verdict"]="INCONCLUSIVE"
            evidence["reason"]="http_response_or_database_side_effect_not_proven"
    except Exception as exc:
        evidence["verdict"]="INCONCLUSIVE"
        evidence["error"]=f"{type(exc).__name__}: {exc}"
    finally:
        try:sandbox.cleanup()
        except Exception as exc:evidence["cleanup_warning"]=str(exc)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:evidence.get(k) for k in (
            "project","verdict","reason","error")},ensure_ascii=False))


if __name__=="__main__":
    main()
