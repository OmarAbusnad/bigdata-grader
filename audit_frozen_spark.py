#!/usr/bin/env python3
"""Frozen-only Spark Maven attribution. Never starts student code."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from grader.spark_dependency_audit import check_submission


def collect_saved_error(report: dict) -> str:
    runtime = report.get("runtime") or report.get("midterm") or {}
    logs = []
    for case in runtime.get("cases") or []:
        if case.get("name") not in {"batch_pipeline", "spark_pipeline"}:
            continue
        run = case.get("runtime_log") or case.get("command_result") or {}
        logs.extend([str(run.get("stdout_tail") or run.get("stdout") or ""),
                     str(run.get("stderr_tail") or run.get("stderr") or "")])
        for a in case.get("assertions") or []:
            logs.extend(str(x) for x in (a.get("evidence") or []))
    for a in (runtime.get("assertions") or {}).values():
        if a.get("key") in {"spark_pipeline.command", "batch_pipeline.command"}:
            logs.extend(str(x) for x in a.get("evidence") or [])
    return "\n".join(logs)[-200000:]


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--original-report", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args=p.parse_args()
    report=json.loads(args.original_report.read_text(encoding="utf-8"))
    if report.get("project_id") != args.project:
        raise ValueError("Frozen original report/project mismatch")
    error=collect_saved_error(report)
    result=check_submission(args.repo, runtime_error=error)
    result["project_id"]=args.project
    result["frozen_commit"]=report.get("commit_sha")
    result["original_run_id"]=37874152827
    result["original_saved_error_sha256"]=hashlib.sha256(error.encode()).hexdigest()
    result["student_submission_changed"]=False
    result["source"]=str(args.original_report)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"project":args.project,"status":result["status"],
                      "owner":result["owner"],"source_errors":result["source_errors"]},
                      ensure_ascii=False))


if __name__=="__main__":
    main()
