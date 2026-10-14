#!/usr/bin/env python3
"""Correct preliminary readiness with verified later SHA-specific artifacts; no academic scoring."""
import argparse,collections,csv,json,pathlib

def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8-sig"))

def verdict_map(report):
    raw=(report.get("runtime") or {}).get("assertions") or {}
    items=(raw.values() if isinstance(raw,dict) else raw)
    if isinstance(raw,dict):
        return {k:v["verdict"] for k,v in raw.items() if isinstance(v,dict) and v.get("verdict")}
    return {v["key"]:v["verdict"] for v in items if isinstance(v,dict) and v.get("key") and v.get("verdict")}

def merge(older, latest, *, pid, phase, sha, protected, new_pass):
    result=dict(older)
    for key, verdict in latest.items():
        previous=result.get(key)
        if previous=="PASS":
            if verdict!="PASS":
                protected.append({"project":pid,"phase":phase,"key":key,"sha":sha,"later_verdict":verdict})
            continue
        if verdict=="PASS" and previous not in (None,"PASS"):
            new_pass.append({"project":pid,"phase":phase,"key":key,"sha":sha,
                             "prior":previous,"proposed":"PASS","officially_applied":False})
        if previous=="FAIL" and verdict in ("INCONCLUSIVE","ERROR","SKIP"):
            continue
        result[key]=verdict
    return result

def main():
    ap=argparse.ArgumentParser()
    for arg in ("manifest","late-root","base-ledger","out"):
        ap.add_argument("--"+arg,required=True)
    args=ap.parse_args()
    manifest=load(args.manifest);base=load(args.base_ledger)
    out=pathlib.Path(args.out)
    aggregate_path=out/"RECONCILIATION_READINESS.json"
    agg=load(aggregate_path)
    old_by_pid=base["projects"]
    all_rows={};source_log=[];protected=[];new_pass=[]
    root=pathlib.Path(args.late_root).resolve()
    for entry in manifest["entries"]:
        pid,sha,run,artifact=entry["project_id"],entry["sha"],int(entry["run"]),entry["artifact"]
        if len(sha)!=40 or not all(c in "0123456789abcdef" for c in sha):
            raise ValueError(pid+" invalid SHA")
        pfile=pathlib.Path("project-results")/pid/"forensics"/"RECONCILIATION_READINESS_20261014.json"
        record=load(pfile)
        old=old_by_pid.get(pid)
        same_base=bool(old and old.get("frozen_sha")==sha)
        initial={phase:({k:v.get("verdict") for k,v in old["phases"][phase]["entries"].items()} if same_base else {})
                 for phase in ("midterm","final")}
        assessed_phases={}
        for phase,rel in entry["phases"].items():
            relpath=pathlib.Path(rel)
            if phase not in ("midterm","final") or relpath.is_absolute() or ".." in relpath.parts:
                raise ValueError(pid+" unexpected manifest path")
            actual=(root/pid/relpath).resolve()
            if not actual.is_relative_to(root/pid) or not actual.is_file():
                raise ValueError(pid+" assessed report missing: "+str(actual))
            doc=load(actual)
            if doc.get("project_id")!=pid or doc.get("commit_sha")!=sha:
                raise ValueError(pid+" report SHA mismatch in "+phase)
            new=verdict_map(doc)
            if not new:
                raise ValueError(pid+" empty assertions in "+phase)
            initial[phase]=merge(initial[phase],new,pid=pid,phase=phase,sha=sha,
                                 protected=protected,new_pass=new_pass)
            assessed_phases[phase]=len(new)
        # A missing phase cannot borrow reports from another SHA.
        verdicts={phase:dict(collections.Counter(initial[phase].values())) for phase in ("midterm","final")}
        record.update(selected_student_sha=sha,assessed_source_run=run,verdicts=verdicts,
                      phase_coverage={ph:("ASSESSED" if initial[ph] else "NOT_ASSESSED") for ph in ("midterm","final")},
                      phase_provenance={ph:(run if ph in entry["phases"] else (38196458648 if same_base and initial[ph] else None))
                                        for ph in ("midterm","final")},
                      unverified_source=False,official_midterm_points=None,official_final_points=None,
                      official_old_points=None,official_new_points=None,delta=None,
                      human_discussion="REQUIRES_INSTRUCTOR",grades_approved=False)
        pfile.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        all_rows[pid]=record
        source_log.append({"project_id":pid,"source_artifact":artifact,"original_run":run,"exact_sha":sha,
                           "same_sha_as_baseline":same_base,"phases":assessed_phases,
                           "missing_phases":[ph for ph in ("midterm","final") if not initial[ph]],
                           "old_sha_superseded":old.get("frozen_sha") if old and not same_base else None,
                           "academic_grade_change":0})
    csv_path=out/"PENDING_GRADES_REVIEW.csv"
    with csv_path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        fieldnames=reader.fieldnames
        rows=list(reader)
    for row in rows:
        pid=row["project_id"]
        if pid not in all_rows:
            continue
        report=all_rows[pid]
        row["selected_student_sha"]=report["selected_student_sha"]
        row["assessed_source_run"]=str(report["assessed_source_run"])
        row["candidate_same_sha_corrections"]=str(report.get("candidate_same_sha_corrections",0))
        for phase in ("midterm","final"):
            for verdict in ("PASS","FAIL","INCONCLUSIVE"):
                row[phase+"_"+verdict.lower()]=(
                    str(report["verdicts"][phase].get(verdict,0))
                    if report["phase_coverage"][phase]=="ASSESSED" else ""
                )
        row["official_old_points"]=row["official_new_points"]=row["delta"]=""
        row["grades_approved"]="False"
    with csv_path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fieldnames)
        writer.writeheader();writer.writerows(rows)
    agg["late_verified_source_reports"]=source_log
    agg["late_same_sha_pass_overwrites_prevented"]=protected
    agg["late_same_sha_pass_review_candidates"]=new_pass
    agg["late_report_source_count"]=len(source_log)
    agg["not_graded_not_zero_projects"]=[d["project_id"] for d in source_log if d["missing_phases"]]
    agg["academic_grade_changes"]=0
    agg["student_code_executions"]=0
    agg["publish_grades_allowed"]=False
    agg["coverage_warning"]="Baseline 68-project ledger and later version-selected P01/P26+8 additional late artifacts; NOT an authorized scored ledger or approved marks. Blank phase is NOT_ASSESSED, not 0 points."
    aggregate_path.write_text(json.dumps(agg,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PRELIMINARY","late_sources_verified":len(source_log),
       "new_projects_with_evidence":[p for p in ("P69","P70") if p in all_rows],
       "same_sha_passes_protected":len(protected),"candidate_pass_for_review":len(new_pass),
       "grade_changes":0},ensure_ascii=False))
if __name__=="__main__":
    main()
