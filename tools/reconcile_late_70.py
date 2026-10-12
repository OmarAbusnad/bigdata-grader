#!/usr/bin/env python3
"""Evidence-only versioned ledger: 68 historical projects + 10 targeted snapshots => 70.
No student code, no score inference, no frozen-baseline modification.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIP")
LATEST_RUN = 38317234359
P10_RECOVERY_RUN = 38317798470
TARGET_MODES = {
    "P01": "all", "P10": "final", "P24": "all", "P26": "all",
    "P40": "all", "P50": "final", "P67": "midterm",
    "P68": "midterm", "P69": "final", "P70": "all",
}

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def dump_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def assertions(raw):
    if isinstance(raw, dict):
        pairs = raw.items()
    elif isinstance(raw, list):
        pairs = [(a["key"], a) for a in raw if isinstance(a, dict) and a.get("key")]
    else:
        raise ValueError("Report has no recognizable assertion collection")
    result = {}
    for key, item in pairs:
        if key in result:
            raise ValueError(f"Duplicate assertion key {key}")
        if not isinstance(item, dict) or item.get("verdict") not in VERDICTS:
            raise ValueError(f"Unrecognized assertion verdict for {key}")
        result[key] = {
            "verdict": item["verdict"],
            "expected": item.get("expected"),
            "actual": item.get("actual"),
            "note": item.get("note"),
        }
    if not result:
        raise ValueError("Report contains zero graded assertions")
    return result

def recent_phase(path, project_id, phase, sha, run_id, artifact):
    if not path.is_file():
        raise ValueError(f"Missing required {project_id}/{phase} report in {artifact}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("project_id") != project_id:
        raise ValueError(f"Project ID mismatch: {path}")
    if report.get("commit_sha") != sha:
        raise ValueError(f"Frozen SHA mismatch for {project_id}/{phase}: {path}")
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError(f"Missing runtime for {project_id}/{phase}")
    return {
        "status": runtime.get("status") or "UNKNOWN",
        "commit_sha": sha,
        "source_run_id": run_id,
        "source_artifact": artifact,
        "grader_version": report.get("grader_version"),
        "assertions": assertions(runtime.get("assertions")),
        "source": "latest_targeted_snapshot",
    }

def historic_phase(project, phase, ledger_run):
    if not project:
        return None
    ph = project["phases"][phase]
    result = {}
    for key, entry in ph.get("entries", {}).items():
        result[key] = {
            "verdict": entry["verdict"], "expected": entry.get("expected"),
            "actual": entry.get("actual"), "note": entry.get("note"),
            "origin": entry.get("origin"), "history": entry.get("history", []),
            "flags": entry.get("flags", []),
        }
    return {
        "status": ph.get("status") or "NOT_PRESENT",
        "commit_sha": project.get("frozen_sha"),
        "source_run_id": ledger_run,
        "source": "historical_adjudicated_ledger",
        "assertions": result,
    }

def snapshot_diff(pid, phase, old, new):
    rows = []
    if new is None:
        return rows
    before = (old or {}).get("assertions", {})
    for key, item in sorted(new["assertions"].items()):
        previous = before.get(key, {})
        ov = previous.get("verdict")
        nv = item["verdict"]
        if ov == "PASS" and nv != "PASS":
            transition = "HISTORICAL_PASS_CONFLICT_REVIEW"
        elif ov == nv:
            transition = "SAME_VERDICT_NEW_SNAPSHOT"
        elif nv == "PASS":
            transition = "NEW_PASS"
        elif nv in {"INCONCLUSIVE", "ERROR", "SKIP"}:
            transition = "UNPROVEN_NEW_SNAPSHOT"
        else:
            transition = "NEW_FAIL_REQUIRES_CAUSAL_REVIEW"
        rows.append({
            "project_id": pid, "phase": phase, "test_key": key,
            "historical_sha": (old or {}).get("commit_sha") or "",
            "latest_sha": new["commit_sha"],
            "historical_verdict": ov or "",
            "latest_verdict": nv,
            "transition": transition,
            "latest_run_id": new["source_run_id"],
        })
    return rows

def count(phase):
    return Counter(a["verdict"] for a in (phase or {}).get("assertions", {}).values())

def reconcile(base_path, new_root, p10_root, roster_path, late_path, out_dir,
              *, base_ledger_run=38196458648, expected_projects=70):
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    historical = base["projects"]
    if len(historical) != 68 or not base.get("invariants", {}).get("ok"):
        raise ValueError("Expected a verified, immutable 68-project historical ledger")
    if base["invariants"].get("baseline_pass_preserved") != 2022:
        raise ValueError("Historical PASS preservation must be exactly 2022")
    roster = {r["project_id"]: r for r in read_csv(roster_path)}
    late = {r["project_id"]: r for r in read_csv(late_path)}
    if set(roster) != (set(historical) | {"P69", "P70"}) or set(late) != set(TARGET_MODES):
        raise ValueError("Roster or pinned target manifest differs from reviewed 68+10 selection")
    if len(late) != len(TARGET_MODES):
        raise ValueError("Duplicate project ID in late manifest")
    for pid in ("P69", "P70"):
        roster[pid] = late[pid]
    if len(roster) != expected_projects:
        raise ValueError(f"Expected {expected_projects} projects, got {len(roster)}")
    for pid, mode in TARGET_MODES.items():
        if late[pid]["grading_mode"] != mode:
            raise ValueError(f"Unexpected grading mode for {pid}")
        if len(late[pid]["ref"]) != 40:
            raise ValueError(f"Missing pinned 40-character student SHA for {pid}")

    projects, summary, review, diffs, students = {}, [], [], [], []
    inspected = []
    for pid in sorted(roster):
        old = historical.get(pid)
        phases = {}
        for phase in ("midterm", "final"):
            prior = historic_phase(old, phase, base_ledger_run)
            current = prior
            if pid in TARGET_MODES and TARGET_MODES[pid] in ("all", phase):
                run_id = P10_RECOVERY_RUN if pid == "P10" else LATEST_RUN
                root = Path(p10_root) if pid == "P10" else Path(new_root)
                artifact = f"late-grading-{pid}-{run_id}"
                location = root / artifact
                if not location.is_dir():
                    raise ValueError(f"Required artifact missing: {location}")
                filename = "reports" if phase == "midterm" else "reports_final"
                report_path = location / filename / pid / "result.json"
                current = recent_phase(report_path, pid, phase, late[pid]["ref"], run_id, artifact)
                inspected.append(f"{pid}/{phase}@{run_id}")
                diffs.extend(snapshot_diff(pid, phase, prior, current))
            phases[phase] = {"historical": prior, "current": current}
        row = roster[pid]
        projects[pid] = {
            "students": row.get("students", ""),
            "student_nos": row.get("student_nos", ""),
            "historical_ledger_run": base_ledger_run if old else None,
            "phases": phases,
        }
        sr = {"project_id": pid, "students": row.get("students", ""),
              "student_nos": row.get("student_nos", ""),
              "academic_grade": "", "grade_status": "NOT_APPROVED"}
        for phase, bundle in phases.items():
            oldph = bundle["historical"]
            latest = bundle["current"]
            sr[f"{phase}_sha"] = (latest or {}).get("commit_sha") or ""
            sr[f"{phase}_source_run"] = (latest or {}).get("source_run_id") or ""
            sr[f"{phase}_status"] = (latest or {}).get("status") or "NOT_TESTED"
            for verdict in VERDICTS:
                sr[f"{phase}_{verdict.lower()}"] = count(latest)[verdict]
            if latest is None:
                review.append({"project_id": pid, "students": row.get("students",""),
                               "phase": phase, "key": "PHASE_NOT_TESTED", "verdict": "NOT_TESTED",
                               "latest_sha": "", "run_id": "", "note": "No evidence for this phase",
                               "automatic_penalty_allowed": "NO"})
            else:
                for key, item in sorted(latest["assertions"].items()):
                    if item["verdict"] != "PASS":
                        review.append({
                            "project_id": pid, "students": row.get("students", ""),
                            "phase": phase, "key": key, "verdict": item["verdict"],
                            "latest_sha": latest.get("commit_sha") or "",
                            "run_id": latest.get("source_run_id") or "",
                            "note": str(item.get("note") or "")[:400],
                            "automatic_penalty_allowed": "NO",
                        })
            # A later snapshot cannot erase the historical evidence or retroactively
            # guarantee an old PASS still works on a different source commit.
            if oldph and latest and oldph.get("commit_sha") != latest.get("commit_sha"):
                sr[f"{phase}_version_changed"] = "YES"
            else:
                sr[f"{phase}_version_changed"] = "NO"
        summary.append(sr)
        names = [v.strip() for v in row.get("students", "").split("|") if v.strip()]
        nums = [v.strip() for v in row.get("student_nos", "").split(",") if v.strip()]
        if nums and len(nums) != len(names):
            raise ValueError(f"Student roster mismatch for {pid}: {nums} vs {names}")
        for index, name in enumerate(names):
            students.append({"project_id": pid, "student": name,
                             "student_no": nums[index] if nums else "",
                             "midterm_grade_18": "", "final_grade_7": "",
                             "total_grade_25": "", "grade_status": "NOT_APPROVED"})
    expected_reports = sum(2 if x == "all" else 1 for x in TARGET_MODES.values())
    if len(inspected) != expected_reports:
        raise ValueError(f"Expected {expected_reports} reports, got {len(inspected)}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "grade_release_allowed": False, "student_code_executed": False,
        "grading_policy": {"midterm": 18, "final": 7, "total": 25},
        "historical_ledger_run": base_ledger_run, "targeted_run": LATEST_RUN,
        "p10_recovery_run": P10_RECOVERY_RUN,
        "source_reports": inspected, "projects": projects,
    }
    (out / "snapshot_ledger_70.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["project_id","students","student_nos","academic_grade","grade_status"]
    for ph in ("midterm","final"):
        fields += [f"{ph}_{k}" for k in ("sha","source_run","status",
                   "pass","fail","inconclusive","error","skip","version_changed")]
    dump_csv(out / "project_summary_70.csv", summary, fields)
    dump_csv(out / "review_queue_70.csv", review,
             ["project_id","students","phase","key","verdict",
              "latest_sha","run_id","note","automatic_penalty_allowed"])
    dump_csv(out / "snapshot_diffs.csv", diffs,
             ["project_id","phase","test_key","historical_sha","latest_sha",
              "historical_verdict","latest_verdict","transition","latest_run_id"])
    dump_csv(out / "student_grade_preview.csv", students,
             ["project_id","student","student_no","midterm_grade_18",
              "final_grade_7","total_grade_25","grade_status"])
    audit = {
        "projects": len(projects), "students": len(students),
        "historical_projects": len(historical),
        "historical_baseline_pass_preserved": base["invariants"]["baseline_pass_preserved"],
        "new_evidence_reports": len(inspected), "reports": inspected,
        "review_rows": len(review),
        "historical_pass_changed_in_new_sha": sum(
            x["transition"] == "HISTORICAL_PASS_CONFLICT_REVIEW" for x in diffs),
        "grading_state": "PENDING_CAUSAL_REVIEW_AND_RUBRIC",
        "grade_release_allowed": False,
    }
    (out / "intake_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--late", type=Path, required=True)
    parser.add_argument("--p10", type=Path, required=True)
    parser.add_argument("--roster", type=Path, default=Path("submission_groups.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("late_submissions_20261013.csv"))
    parser.add_argument("--out", type=Path, default=Path("ledger_70_out"))
    args = parser.parse_args()
    reconcile(args.base, args.late, args.p10, args.roster, args.manifest, args.out)

if __name__ == "__main__":
    main()
