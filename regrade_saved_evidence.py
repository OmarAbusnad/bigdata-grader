#!/usr/bin/env python3
"""Read frozen GitHub Actions artifacts and output cumulative midterm evidence overlays.

Only previous FAIL assertions backed by usable execution snapshots are reevaluated.
Original artifacts and grades stay unchanged. NEVER runs student submissions.
"""
from __future__ import annotations
import argparse
import csv
import json
import zipfile
from pathlib import Path

from grader.evidence_regrade import regrade_saved_midterm


def read_reports(root: Path):
    seen = set()
    for path in sorted(root.rglob("reports/P*/result.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        project = obj["project_id"]
        if project in seen:
            raise ValueError(f"Duplicate cached report for {project}")
        seen.add(project)
        yield project, obj
    for path in sorted(root.glob("P??-official.zip")):
        with zipfile.ZipFile(path) as z:
            entries = [p for p in z.namelist() if p.startswith("reports/") and p.endswith("/result.json")]
            for name in entries:
                obj = json.loads(z.read(name))
                project = obj["project_id"]
                if project in seen:
                    raise ValueError(f"Duplicate cached report for {project}")
                seen.add(project)
                yield project, obj


def run(root: Path, output: Path, *, source_run_id: int, expected_projects: int = 68):
    overlays = {}
    for project, obj in read_reports(root):
        overlays[project] = regrade_saved_midterm(obj, source_run_id=source_run_id)
    if len(overlays) != expected_projects:
        raise ValueError(f"Missing source artifacts: expected {expected_projects}, found {len(overlays)}")
    output.mkdir(parents=True, exist_ok=True)
    (output/"overlays.json").write_text(
        json.dumps({"source_run_id":source_run_id,"projects":overlays,
                    "formal_grade":False,"student_tests_reexecuted":0},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for project, result in sorted(overlays.items()):
        original = result.get("original_assertion_counts") or {}
        revised = result.get("revised_assertion_counts") or {}
        rows.append({
            "project":project, "student_commit":result["student_commit"],
            "original_pass":original.get("PASS",0), "original_fail":original.get("FAIL",0),
            "revised_pass":revised.get("PASS",0), "revised_fail":revised.get("FAIL",0),
            "revised_review":revised.get("INCONCLUSIVE",0),
            "count_only_fixes":len(result["overrides"]),
            "unresolved_tests":len(result["remaining_fail_keys"]),
            "source_sha256":result["source_runtime_sha256"],
        })
    with (output/"project_summary.csv").open("w",newline="",encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle,fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "source_run_id": source_run_id, "projects_reviewed":len(overlays),
        "student_pipelines_executed":0,
        "previous_passes_preserved":sum(len(o["preserved_pass_keys"]) for o in overlays.values()),
        "updated_failed_assertions":sum(len(o["overrides"]) for o in overlays.values()),
        "remaining_failures":sum(len(o["remaining_fail_keys"]) for o in overlays.values()),
    },indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=Path("reports_cached_midterm"))
    parser.add_argument("--source-run-id",type=int,default=37874152827)
    parser.add_argument("--expected-projects",type=int,default=68)
    args=parser.parse_args()
    run(args.input,args.out,source_run_id=args.source_run_id,
        expected_projects=args.expected_projects)
