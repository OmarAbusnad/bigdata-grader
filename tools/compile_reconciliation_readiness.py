#!/usr/bin/env python3
"""Read-only exact-SHA preliminary grade evidence reconciliation; NEVER publish marks."""
import argparse,csv,json,pathlib,collections
LATE={"P01":("c43aae3d5e9c0d96731640206752f886f2618497",38424927615),"P26":("fc4f5d9924fe9a59f09e4167d323eaf4672ccca2",38317234359)}
def load(f):return json.loads(pathlib.Path(f).read_text(encoding="utf-8-sig"))
def keys(report):
    raw=((report or {}).get("runtime") or {}).get("assertions") or {}
    if isinstance(raw,list):return {v["key"]:v["verdict"] for v in raw if isinstance(v,dict) and v.get("key") and v.get("verdict")}
    if isinstance(raw,dict):return {k:v["verdict"] for k,v in raw.items() if isinstance(v,dict) and v.get("verdict")}
    return {}
def main():
    a=argparse.ArgumentParser()
    for k in ("ledger","register","rubric_mid","rubric_final","submissions","p01_mid","p01_final","p26_mid","p26_final","output"):
        a.add_argument("--"+k.replace("_","-"),required=True)
    x=a.parse_args()
    mid,fin=load(x.rubric_mid),load(x.rubric_final)
    assert (mid.get("status"),mid.get("total"),fin.get("status"),fin.get("total"))==("ACTIVE",18,"ACTIVE",7)
    previous,register=load(x.ledger),load(x.register)
    assert previous.get("formal_grade") is False
    saved_pass=sum(v.get("verdict")=="PASS" for p in previous["projects"].values() for ph in p["phases"].values() for v in ph["entries"].values())
    projects={}
    for pid,p in previous["projects"].items():
        projects[pid]={"sha":p.get("frozen_sha"),"run":38196458648,
                       "phases":{phase:{key:v.get("verdict") for key,v in p["phases"][phase]["entries"].items()} for phase in ("midterm","final")}}
    superseded=[]
    for pid,(sha,run) in LATE.items():
        old=projects.get(pid)
        superseded.append({"project_id":pid,"old_sha":old.get("sha") if old else None,"new_sha":sha,"mix_old_new":False})
        newer={"sha":sha,"run":run,"phases":{}}
        for phase in ("midterm","final"):
            doc=load(getattr(x,pid.lower()+"_"+("mid" if phase=="midterm" else "final")))
            assert doc.get("project_id")==pid and doc.get("commit_sha")==sha,pid+" "+phase+" assessed source SHA mismatch"
            newer["phases"][phase]=keys(doc)
        projects[pid]=newer
    source_audit=[];proposed=[];totals=collections.Counter()
    for i,e in enumerate(register.get("cases") or []):
        pid=e["project_id"];p=projects.get(pid);counts=collections.Counter()
        for key,verdict in (e.get("outcomes") or {}).items():
            if not p or p["sha"]!=e.get("frozen_sha"):
                counts["rejected_sha_mismatch"]+=1;continue
            if verdict!="PASS" and not str(verdict).startswith("PASS (historical"):
                counts["not_pass_not_applied"]+=1;continue
            found=[phase for phase in ("midterm","final") if key in p["phases"][phase]]
            if len(found)!=1:
                counts["scoped_pass_without_exact_grade_key"]+=1;continue
            phase=found[0];prior=p["phases"][phase][key]
            if prior=="PASS":
                counts["historical_pass_preserved"]+=1
            elif prior in ("FAIL","INCONCLUSIVE","ERROR","SKIP"):
                counts["candidate_changes_requires_review"]+=1
                proposed.append({"project_id":pid,"phase":phase,"assertion_key":key,"sha":p["sha"],
                                 "old_verdict":prior,"proposed_verdict":"PASS","source_run":e.get("focused_run"),"report":e.get("evidence_report"),"officially_applied":False})
            else:counts["unsupported_prior_verdict"]+=1
        totals.update(counts)
        source_audit.append({"case_index":i,"project_id":pid,"focused_run":e.get("focused_run"),
                             "frozen_sha":e.get("frozen_sha"),"evidence_report":e.get("evidence_report"),
                             "counts":dict(counts)})
    out=pathlib.Path(x.output);out.mkdir(parents=True,exist_ok=True)
    with pathlib.Path(x.submissions).open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    all_rows=[]
    for row in rows:
        pid=row["project_id"];p=projects.get(pid)
        counts={phase:dict(collections.Counter((p or {}).get("phases",{}).get(phase,{}).values())) for phase in ("midterm","final")}
        record={"project_id":pid,"selected_student_sha":p.get("sha") if p else None,
                "assessed_source_run":p.get("run") if p else None,"verdicts":counts,
                "candidate_same_sha_corrections":sum(v["project_id"]==pid for v in proposed),
                "unverified_source":not bool(p),"official_midterm_points":None,"official_final_points":None,
                "official_old_points":None,"official_new_points":None,"delta":None,
                "human_discussion":"REQUIRES_INSTRUCTOR","grades_approved":False}
        all_rows.append(record)
        dest=pathlib.Path("project-results")/pid/"forensics"/"RECONCILIATION_READINESS_20261014.json"
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={"status":"OPEN_PRELIMINARY_NOT_OFFICIAL","source_ledger_run":38196458648,"baseline_project_count":len(previous["projects"]),
            "submission_rows":len(rows),"historical_pass_saved_in_immutable_ledger":saved_pass,
            "active_rubric":{"midterm":18,"final":7,"manual_final_discussion":0.25},
            "later_assessment_provenance":superseded,"source_outcome_counts":dict(totals),
            "per_source_applied_ignored_conflicts":source_audit,
            "candidate_review_only_changes":proposed,
            "academic_grade_changes":0,"student_code_executions":0,"publish_grades_allowed":False,
            "aggregate_policy":"Passing a single named query does not automatically pass whole final.queries.runtime; source SHAs cannot mix."}
    (out/"RECONCILIATION_READINESS.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    cols=["project_id","selected_student_sha","assessed_source_run","midterm_pass","midterm_fail","midterm_inconclusive",
          "final_pass","final_fail","final_inconclusive","candidate_same_sha_corrections","official_old_points","official_new_points","delta","grades_approved"]
    with (out/"PENDING_GRADES_REVIEW.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for row in all_rows:
            v={k:row.get(k) for k in cols if not k.startswith(("midterm_","final_"))}
            for phase in ("midterm","final"):
                for status in ("pass","fail","inconclusive"):v[phase+"_"+status]=row["verdicts"][phase].get(status.upper(),0)
            w.writerow(v)
    print(json.dumps({"readiness":"OPEN","submission_rows":len(rows),"baseline_historical_PASS":saved_pass,
                      "per_source":len(source_audit),"counts":dict(totals),"grades_changed":0}))
if __name__=="__main__":main()
