#!/usr/bin/env python3
"""Retry ONLY saved unsuccessful Spark test02 using the original student command."""
import argparse
import json
import shutil
from pathlib import Path
from grader.mongo_checker import MongoChecker
from grader.sandbox import DockerSandbox, SandboxConfig
from grader.runtime_evidence import detect_engine


def main():
    p=argparse.ArgumentParser()
    for k in ("project", "repo", "original-report", "hidden", "out"):
        p.add_argument("--"+k,required=True)
    a=p.parse_args()
    repo,hidden,out=Path(a.repo),Path(a.hidden),Path(a.out)
    original=json.loads(Path(a.original_report).read_text(encoding="utf-8"))
    if original.get("project_id")!=a.project:
        raise ValueError("Frozen project mismatch")
    runtime=original.get("runtime") or {}
    previous=(runtime.get("assertions") or {}).get("spark_pipeline.command") or {}
    if previous.get("verdict") not in {"INCONCLUSIVE","FAIL"}:
        raise ValueError("Cannot retry a previously passing test")
    case=next((c for c in (runtime.get("cases") or []) if c.get("name")=="spark_pipeline"),None)
    command=(case or {}).get("command") or ""
    if "/grader-tests/test_02_large_spark.csv" not in command or not command.startswith(("python ","python3 ","py ")):
        raise ValueError("Only the frozen Spark test02 command may be retried")
    if any(m in command for m in ("&&","||",";","|",">","<",chr(96),"$(")):
        raise ValueError("Shell metacharacters blocked")
    visible=Path.cwd()/"sandboxes"/a.project/"only_failed_spark"
    visible.mkdir(parents=True,exist_ok=True)
    file=hidden/"test_02_large_spark.csv"
    if not file.is_file():raise FileNotFoundError(file)
    shutil.copy2(file,visible/file.name)
    plan=original.get("execution_plan") or {}
    db=f"grader_{a.project.lower()}" if plan.get("database_configurable") else (plan.get("database_name") or f"grader_{a.project.lower()}")
    result={"project_id":a.project,"source_run":37874152827,
            "frozen_commit":original.get("commit_sha"),"only_test":"spark_pipeline.command",
            "prior_verdict":previous["verdict"],"passed_tests_reexecuted":0,
            "other_tests_reexecuted":0,"official_grade_changed":False}
    sb=DockerSandbox(Path.cwd(),a.project+"-spark-only",repo,visible,SandboxConfig(network_profile="isolated",timeout_seconds=1200))
    try:
        built=sb.build()
        result["build"]={
            "ok":built.get("ok"),
            "spark_dependency_prewarm":built.get("spark_dependency_prewarm"),
            "spark_prefetch_log_tail":str(built.get("spark_prefetch_log_tail") or "")[-1200:],
            "build_error":str(built.get("stderr_tail") or "")[-1800:] if not built.get("ok") else "",
        }
        if not built.get("ok"):
            result.update(verdict="INCONCLUSIVE",reason="dependency_image_build_failure")
            return
        sb.start()
        mongo=MongoChecker(sb.mongo_host_uri,db,plan.get("collections") or {},
                           business_key=plan.get("business_key") or "order_id")
        mongo.ping()
        mongo.drop_database()
        env={
            "MONGO_DB_NAME":db,"MONGO_DATABASE":db,"DATABASE_NAME":db,
            "MONGODB_DATABASE":db,"DB_NAME":db,
            "SMALL_FILE_THRESHOLD_MB":"20","FILE_SIZE_THRESHOLD_MB":"20",
            "THRESHOLD_MB":"20","GRADER_RUN":"1",
        }
        if plan.get("setup_command"):
            setup=sb.run_student(plan["setup_command"],env=env,timeout=240)
            result["setup"]={"returncode":setup.get("returncode"),"timed_out":setup.get("timed_out"),
                             "stderr":str(setup.get("stderr") or "")[-1200:]}
        before=mongo.snapshot().to_dict()
        run=sb.run_student(command,env=env,timeout=1100)
        after=mongo.snapshot().to_dict()
        result["run"]={"returncode":run.get("returncode"),"timed_out":run.get("timed_out"),
                       "stdout_tail":str(run.get("stdout") or "")[-1800:],
                       "stderr_tail":str(run.get("stderr") or "")[-2800:]}
        result["before"]=before
        result["after"]=after
        engine,signals=detect_engine(run.get("stdout",""),run.get("stderr",""),None,mongo.distinct_engine_values())
        result["engine"]=engine
        result["engine_evidence"]=signals
        if run.get("returncode")==0 and not run.get("timed_out") and engine=="pyspark" and int(after.get("raw") or 0)>0:
            result.update(verdict="PASS",reason="original Spark stage ran successfully and persisted raw records")
        else:
            result.update(verdict="INCONCLUSIVE",reason="Spark stage remains unproved; inspect saved stderr")
    except Exception as exc:
        result.update(verdict="INCONCLUSIVE",error=f"{type(exc).__name__}: {exc}")
    finally:
        try:sb.cleanup()
        except Exception as exc:result["cleanup_warning"]=str(exc)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:result.get(k) for k in ("project_id","verdict","reason","error")},
                         ensure_ascii=False))


if __name__=="__main__":
    main()
