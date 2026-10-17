#!/usr/bin/env python3
"""Diagnose P01 later-SHA API import in an isolated Docker sandbox only. No grading."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from grader.sandbox import DockerSandbox,SandboxConfig

SOURCE_SHA="c43aae3d5e9c0d96731640206752f886f2618497"
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();a.out.parent.mkdir(parents=True,exist_ok=True)
    report={"project_id":"P01","student_commit_sha":SOURCE_SHA,"original_run":38424927615,
            "focused_query_run":38625479332,"phase":"final","focus":"isolated_API_import_precondition_only",
            "previous_query_verdict":"INCONCLUSIVE","student_code_modified":False,
            "historical_successful_queries_reexecuted":0,"official_grades_changed":False,
            "root_cause_owner":"PRECONDITION_NOT_SATISFIED"}
    source=(a.repo/"src/spark_loader.py")
    mon=(a.repo/"src/monitor.py")
    req=(a.repo/"requirements.txt")
    api=(a.repo/"src/api.py")
    report["frozen_source_observations"]={
       "api_imports_spark_loader": api.exists() and "from src.spark_loader import run_spark_loader" in api.read_text(errors="replace"),
       "spark_loader_imports_monitor": source.exists() and "from src.monitor import SystemMonitor" in source.read_text(errors="replace"),
       "monitor_imports_psutil":mon.exists() and "import psutil" in mon.read_text(errors="replace"),
       "psutil_in_declared_requirements":req.exists() and any(x.strip().lower().startswith("psutil") for x in req.read_text(errors="replace").splitlines())
    }
    sb=DockerSandbox(Path.cwd(),"P01-only-API-import-precondition",a.repo,Path.cwd()/"sandboxes"/"P01"/"only_api_import",
                     SandboxConfig(network_profile="isolated",timeout_seconds=240))
    try:
        built=sb.build()
        report["build_ok"]=bool(built.get("ok"))
        if not built.get("ok"):
            report["reason"]="isolated_environment_build_failed"
            report["build_stderr_tail"]=str(built.get("stderr_tail") or "")[-1300:]
            return
        sb.start()
        output=sb.run_student("python -c 'from src.api import app; print(\"P01_API_IMPORT_OK\")'",timeout=75)
        err=str(output.get("stderr") or "")
        # Store only sanitized Python exception text; no student records or hidden test data.
        tb=err[-2500:]
        report["import_probe"]={"returncode":output.get("returncode"),
                 "timed_out":output.get("timed_out"),"stderr_tail":tb,
                 "import_success":"P01_API_IMPORT_OK" in str(output.get("stdout") or "")}
        if "ModuleNotFoundError: No module named 'psutil'" in err and all(
          (report["frozen_source_observations"].get("api_imports_spark_loader"),
           report["frozen_source_observations"].get("spark_loader_imports_monitor"),
           report["frozen_source_observations"].get("monitor_imports_psutil"),
           not report["frozen_source_observations"].get("psutil_in_declared_requirements"))):
            report["root_cause_owner"]="STUDENT_DEPENDENCY_FAILURE"
            report["root_cause"]="P01 src.api imports src.spark_loader -> src.monitor -> psutil, but frozen requirements.txt does not declare psutil; isolated import raises ModuleNotFoundError."
            report["query_logic_judged"]=False
            report["next_action"]="Do not add undeclared dependency in grader and do not change source. Preserve 4 historical query PASS; scope final orders_in_period as blocked by independently proven student dependency precondition. Teacher review before grades."
        elif report["import_probe"]["import_success"]:
            report["root_cause_owner"]="GRADER_PROBE_FAILURE_OR_API_STARTUP_UNRESOLVED"
            report["next_action"]="API import works; diagnose shell server startup without rerunning successful queries."
        else:
            report["root_cause_owner"]="HUMAN_REVIEW_REQUIRED"
            report["next_action"]="Inspect traceback and source for precise startup blocker; no academic penalty."
    except Exception as ex:
        report["error"]=type(ex).__name__+": "+str(ex)[:600]
    finally:
        try:sb.cleanup()
        except Exception:pass
        a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({k:report.get(k) for k in ("project_id","root_cause_owner","root_cause","error","import_probe")},ensure_ascii=False))
if __name__=="__main__":main()
