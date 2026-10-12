"""Read-only final grading evidence gate: never infer student fault from FAIL.

Usage: python tools/final_closure_gate.py --evidence-dir .audit/source --out closure_report
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

REFERENCE_COUNTS = {"PASS": 2678, "FAIL": 353, "INCONCLUSIVE": 656}
FROZEN_ROOTS = {
    "P01": ("FROZEN_DEPENDENCY", "STUDENT_SUBMISSION_CANDIDATE", "psutil import omitted from frozen requirements"),
    "P02": ("FROZEN_DEPENDENCY", "STUDENT_SUBMISSION_CANDIDATE", "psutil import omitted from frozen requirements"),
    "P10": ("FROZEN_SOURCE_IMPORT", "STUDENT_SUBMISSION_CANDIDATE", "undefined imported config constants"),
    "P17": ("PACKAGE_OR_COMMAND_MISMATCH", "OWNER_UNRESOLVED", "README command and frozen source layout conflict"),
    "P29": ("FROZEN_SOURCE_SYNTAX", "STUDENT_SUBMISSION_CANDIDATE", "late from __future__ import"),
    "P33": ("TIMEOUT_UNPROVEN", "OWNER_UNRESOLVED", "no completed pipeline proof"),
    "P41": ("GRADER_SETUP_INTERFERENCE_RESOLVED", "PRIOR_GRADER_ISSUE_FIXED", "rerun 38196157736 after isolated replay: 27 PASS / 6 FAIL / 2 INCONCLUSIVE"),
    "P51": ("GRADER_OR_DATABASE_DISCOVERY", "OWNER_UNRESOLVED", "database provenance not resolved"),
    "P55": ("FINAL_STAGE_BLOCK", "OWNER_UNRESOLVED", "final dependency chain unresolved"),
    "P63": ("FROZEN_PACKAGE_ABSENT", "STUDENT_SUBMISSION_CANDIDATE", "src package absent from frozen commit"),
    "P67": ("FROZEN_DEPENDENCY", "STUDENT_SUBMISSION_CANDIDATE", "tqdm omitted from frozen requirements"),
    "P68": ("FROZEN_CONFIG_ABSENT", "STUDENT_SUBMISSION_CANDIDATE", "config.settings absent from frozen commit"),
}

def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))

def classify(row):
    key = row["key"].lower()
    note = (row.get("note") or "").lower()
    actual = str(row.get("actual") or "").lower()
    if "discussion" in key or "0.25 remains manual" in note:
        return "HUMAN_DISCUSSION"
    if "blocked by root cause" in note or actual == "blocked":
        return "UPSTREAM_BLOCKED"
    if "maven" in note and ("isolated" in note or "could not be resolved" in note):
        return "GRADER_ENVIRONMENT"
    if any(s in note for s in ("spark-submit.cmd", "java was not found", "mongodb.defaultsource", "ivy jar cache")):
        return "SPARK_CLASSPATH_OR_PLATFORM"
    if "timeout" in note or "timed out" in note:
        return "TIMEOUT_UNPROVEN"
    if "aggregate_count_band" in note or key.endswith("_count") or key.endswith(".raw_count") or key.endswith(".validated_count"):
        return "ORACLE_COUNT_UNVERIFIED"
    if any(s in key for s in ("cleaning", "upsert", "quarantine", "idempotency", "incremental", "audit_trail", "validator", "duplicates")):
        return "PIPELINE_BEHAVIOR_UNVERIFIED"
    if row["phase"] == "final" and any(s in key for s in ("queries", "indexes", "aggregations", "jobs", "api", "mv")):
        return "FINAL_API_UNVERIFIED"
    if any(s in key for s in ("command", "engine", "pipeline", "discovered")):
        return "STARTUP_DISCOVERY_UNVERIFIED"
    return "OTHER_UNVERIFIED"

def dump_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def run(evidence, output):
    evidence = Path(evidence)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((evidence / "ledger.json").read_text(encoding="utf-8"))
    review = read_csv(evidence / "review_queue.csv")
    projects = read_csv(evidence / "project_summary.csv")
    sources = read_csv(evidence / "source_audit.csv")
    counts = Counter(
        e["verdict"] for project in ledger["projects"].values()
        for phase in project["phases"].values() for e in phase["entries"].values()
    )
    assert len(ledger["projects"]) == len(projects) == 68
    assert len(sources) == 19
    assert len(review) == counts["FAIL"] + counts["INCONCLUSIVE"] == 1009
    assert all(counts[k] == v for k,v in REFERENCE_COUNTS.items()), counts
    assert ledger["invariants"]["ok"] and ledger["invariants"]["baseline_pass_preserved"] == 2022
    assert not ledger["rejected"] and not ledger["pass_overrides"]
    audits = []
    for row in review:
        pid = row["project_id"]
        assert pid in ledger["projects"]
        family = classify(row)
        root, owner, proof = FROZEN_ROOTS.get(pid, ("", "OWNER_UNRESOLVED", ""))
        if family == "HUMAN_DISCUSSION":
            decision = "INSTRUCTOR_ACTION"
        elif family == "UPSTREAM_BLOCKED":
            decision = "DO_NOT_DEDUCT_DEPENDENT_TEST"
        elif pid == "P41" and row["phase"] == "midterm":
            decision = "REPLAY_CONFIRMED_REVIEW_SIX_ACTUAL_BEHAVIOR_FAILURES"
        else:
            decision = "REVIEW_SOURCE_RUNTIME_AND_RUBRIC"
        evidence_run = row.get("run_id") or ""
        audits.append({
            "project_id": pid, "frozen_sha": ledger["projects"][pid].get("frozen_sha",""),
            "phase": row["phase"], "test_key": row["key"], "verdict": row["verdict"],
            "family": family, "root_cluster": pid + ":" + (root if family == "UPSTREAM_BLOCKED" and root else row["phase"]+":"+family),
            "ownership": owner if family == "UPSTREAM_BLOCKED" and root else "UNPROVEN_FROM_VERDICT_ALONE",
            "review_decision": decision, "rubric_penalty_authorized": "NO",
            "expected": row.get("expected",""), "actual": row.get("actual",""),
            "evidence_note": row.get("note",""), "source_run_id": evidence_run,
            "source_url": "https://github.com/omrbosnd/bigdata-grader/actions/runs/" + str(evidence_run),
            "frozen_root_evidence": proof if root else "",
        })
    assert len(audits) == len(review)
    assert len({(x["project_id"],x["phase"],x["test_key"]) for x in audits}) == 1029
    group = defaultdict(list)
    for x in audits:
        group[x["root_cluster"]].append(x)
    clusters = [{
        "root_cluster": key, "project_id": rs[0]["project_id"],
        "linked_verdicts": len(rs), "FAIL": sum(x["verdict"] == "FAIL" for x in rs),
        "INCONCLUSIVE": sum(x["verdict"] == "INCONCLUSIVE" for x in rs),
        "family": rs[0]["family"], "gate": "OPEN_NEEDS_EVIDENCE_OR_HUMAN_ACTION"
    } for key,rs in sorted(group.items())]
    roster = [{
        "project_id": p["project_id"], "frozen_sha": p["frozen_sha"],
        "midterm_PASS": p["midterm_PASS"], "midterm_FAIL": p["midterm_FAIL"],
        "midterm_INCONCLUSIVE": p["midterm_INCONCLUSIVE"],
        "final_PASS": p["final_PASS"], "final_FAIL": p["final_FAIL"],
        "final_INCONCLUSIVE": p["final_INCONCLUSIVE"],
        "root_groups": len({x["root_cluster"] for x in audits if x["project_id"] == p["project_id"]}),
        "grade_status": "NOT_APPROVED", "manual_discussion": "PENDING",
        "reason": "MIDTERM_RUBRIC_DRAFT_OR_CAUSAL_PROOF_INCOMPLETE"
    } for p in projects]
    dump_csv(output / "cases_1029.csv", audits, list(audits[0]))
    dump_csv(output / "root_clusters.csv", clusters, list(clusters[0]))
    dump_csv(output / "projects_68.csv", roster, list(roster[0]))
    state = {
        "closure_gate": "OPEN", "publish_grades_allowed": False,
        "total_projects": 68, "verdicts": dict(counts),
        "audited_nonpassing_cases": len(audits),
        "root_review_groups": len(clusters),
        "conflicts_preserved": len(ledger["conflicts"]),
        "evidence_refreshes": len(ledger.get("evidence_refreshes",[])),
        "baseline_pass_preserved": 2022,
        "pending_academic_controls": ["midterm_18 DRAFT_DISABLED", "oral discussion 0.25 manual"],
        "pending_technical_controls": ["causal ownership proof", "oracle count checks", "post-replay P41 behavior and rubric review"],
        "categories": dict(Counter(x["family"] for x in audits)),
        "root_reference_projects": len(FROZEN_ROOTS),
        "no_automatic_fail_attribution": True,
    }
    (output / "closure_gate.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    (output / "REPORT_AR.md").write_text(
        "# نتيجة بوابة إغلاق تصحيح Big Data\n\n"
        "**OPEN — لم يتم إثبات مسؤولية الطالب في جميع حالات FAIL ولا يجوز إصدار الدرجات بعد.**\n\n"
        "حُصر 1009 أحكام وربط كل منها بمصدره؛ تُراجع مجموعات السبب الجذري قبل أي خصم.\n\n"
        "نجاحات الأساس 2022/2022 محفوظة. المناقشة بشرية وRubric النصفي DRAFT_DISABLED.\n",
        encoding="utf-8"
    )
    print(json.dumps(state,ensure_ascii=False))
    return state

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    run(args.evidence,args.out)
