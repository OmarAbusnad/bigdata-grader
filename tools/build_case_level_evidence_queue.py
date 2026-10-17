#!/usr/bin/env python3
"""Build a source-SHA-specific OPEN adjudication queue. Never execute student code or set grades."""
from __future__ import annotations
import argparse,collections,csv,json,pathlib

PHASES=("midterm","final")
NONPASS={"FAIL","INCONCLUSIVE","ERROR","SKIP","NO_EVIDENCE"}
P01_SHA="c43aae3d5e9c0d96731640206752f886f2618497"
P26_SHA="fc4f5d9924fe9a59f09e4167d323eaf4672ccca2"

def read(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8-sig"))

def latest_items(report):
    data=(report.get("runtime") or {}).get("assertions") or {}
    if isinstance(data,list):
        return {v["key"]:v for v in data if isinstance(v,dict) and v.get("key") and v.get("verdict")}
    return {key:value for key,value in data.items() if isinstance(value,dict) and value.get("verdict")}

def ingest_assessment(selection, pid, sha, paths, run, *, history, guards):
    for phase,path in paths.items():
        report=read(path)
        if report.get("project_id")!=pid or report.get("commit_sha")!=sha:
            raise ValueError(pid+": cannot merge different student SHA in "+phase)
        for key,detail in latest_items(report).items():
            verdict=detail["verdict"]
            before=selection[phase].get(key)
            if before and before["verdict"]=="PASS":
                if verdict!="PASS":
                    guards.append({"project_id":pid,"phase":phase,"key":key,
                                   "prior_PASS_unchanged":True,"later_verdict":verdict,"later_run":run})
                continue
            if before and before["verdict"]=="FAIL" and verdict in {"INCONCLUSIVE","ERROR","SKIP"}:
                history.append({"project_id":pid,"phase":phase,"key":key,
                                "action":"IGNORED_WEAKER_LATER_EVIDENCE","run":run})
                continue
            selection[phase][key]={"verdict":verdict,"source_run":run,"source_kind":"exact_sha_assessed_report"}

def classify(pid, phase, key, verdict):
    issue=11; owner="HUMAN_REVIEW_REQUIRED"; category="CAUSE_NOT_YET_PROVEN"
    if "schema_validator" in key:
        issue=35; category="SCHEMA_VALIDATOR_RUNTIME_UNVERIFIED"
    elif "audit_trail" in key:
        issue=36; category="AUDIT_SAMPLES_REQUIRE_REDACTED_COMPARISON"
    elif "discussion" in key or "viva" in key:
        issue=30; category="INSTRUCTOR_MANUAL_SCORE_REQUIRED"
    elif "code_tests_docs" in key or "readme" in key or "static" in key:
        issue=33; category="STATIC_DOCUMENTATION_EVIDENCE_REVIEW"
    elif pid=="P01" and phase=="final" and key=="final.queries.runtime":
        issue=37; owner="STUDENT_DEPENDENCY_FAILURE"
        category="API_STARTUP_BLOCKED_BY_FROZEN_UNDECLARED_PSUTIL_NOT_QUERY_LOGIC_FAIL"
    elif pid=="P04" and key=="spark_pipeline.command":
        issue=39; owner="STUDENT_CONFIGURATION_FAILURE"
        category="SOURCE_SPARK4_CONNECTOR10_MISMATCH_BUT_OLDER_ENVIRONMENT_FAILURE_ALSO_RECORDED"
    elif pid=="P39" and ("upsert." in key or "incremental." in key):
        issue=41; category="OBSERVED_COUNT_DISCREPANCY_AFTER_CORRECT_NO_RESET;ATTRIBUTION_PENDING"
    elif key.startswith("spark."):
        issue=39;category="DEPENDENT_ON_SPARK_STAGE_AND_ENVIRONMENT_TRIAGE"
    elif phase=="final" and key.startswith("final.queries"):
        issue=37; category="NAMED_QUERY_SCOPE_REVIEW;NO_PARENT_ASSERTION_PASS_INFERRED"
    elif pid=="P47" and "dependenc" in key:
        issue=34;category="UNIVERSAL_ENV_GATE_VS_STUDENT_DOCUMENTATION_REVIEW"
    return {"root_cause_owner":owner,"cause_category":category,
            "tracking_issue":f"https://github.com/omrbosnd/bigdata-grader/issues/{issue}"}

def main():
    a=argparse.ArgumentParser()
    for flag in ("ledger","manifest","late-root","p01-root","p26-root","register","out"):
        a.add_argument("--"+flag,required=True)
    opt=a.parse_args()
    ledger,manifest,register=read(opt.ledger),read(opt.manifest),read(opt.register)
    old=ledger["projects"];root=pathlib.Path(opt.late_root).resolve()
    sources={x["project_id"]:(x["sha"],int(x["run"]),{
       ph:root/x["project_id"]/rel for ph,rel in x["phases"].items()})
       for x in manifest["entries"]}
    sources.update({
       "P01":(P01_SHA,38424927615,{
           "midterm":pathlib.Path(opt.p01_root)/"reports/P01/result.json",
           "final":pathlib.Path(opt.p01_root)/"reports_final/P01/result.json"}),
       "P26":(P26_SHA,38317234359,{
           "midterm":pathlib.Path(opt.p26_root)/"reports/P26/result.json",
           "final":pathlib.Path(opt.p26_root)/"reports_final/P26/result.json"})})
    register_by_pid=collections.defaultdict(list)
    for item in register["cases"]:
        register_by_pid[item["project_id"]].append(item)
    with pathlib.Path("submission_groups.csv").open(encoding="utf-8-sig",newline="") as f:
        roster=list(csv.DictReader(f))
    open_cases=[];review_rows=[];guarded=[];ignored=[];all_outcomes=collections.Counter();source_selection=[]
    output=pathlib.Path(opt.out)
    for item in roster:
        pid=item["project_id"]
        reference=read(pathlib.Path("project-results")/pid/"forensics"/"RECONCILIATION_READINESS_20261014.json")
        sha=reference.get("selected_student_sha")
        active={phase:{} for phase in PHASES}
        original=old.get(pid)
        if original and sha and original.get("frozen_sha")==sha:
            for phase in PHASES:
                active[phase]={k:{"verdict":v["verdict"],
                                   "source_run":(v.get("origin") or {}).get("run_id") or 38196458648,
                                   "source_kind":"immutable_68_project_ledger"}
                               for k,v in original["phases"][phase]["entries"].items()}
        if pid in sources:
            exact,run,paths=sources[pid]
            if sha!=exact:
                raise ValueError(pid+": readiness source differs from accepted exact SHA")
            ingest_assessment(active,pid,sha,paths,run,history=ignored,guards=guarded)
        existing={ph:collections.Counter(e["verdict"] for e in active[ph].values()) for ph in PHASES}
        # Absolute protection: reconstructed verdict counts must match already published review-only counters.
        for phase in PHASES:
            expected=reference["verdicts"].get(phase,{})
            if dict(existing[phase])!=expected:
                raise ValueError(pid+" "+phase+" mismatch against version-selected reviewed reconciliation "+str((dict(existing[phase]),expected)))
        cases=[]
        for phase in PHASES:
            for key,e in sorted(active[phase].items()):
                verdict=e["verdict"]
                all_outcomes[verdict]+=1
                if verdict=="PASS":
                    continue
                if verdict not in NONPASS:
                    raise ValueError(pid+" unexpected verdict "+str(verdict))
                cls=classify(pid,phase,key,verdict)
                proof=[f"https://github.com/omrbosnd/bigdata-grader/actions/runs/{e['source_run']}"]
                if pid=="P01" and cls["root_cause_owner"]=="STUDENT_DEPENDENCY_FAILURE":
                    proof.append("https://github.com/omrbosnd/bigdata-grader/actions/runs/38626460727")
                    proof.append("project-results/P01/forensics/LATER_SHA_API_IMPORT_DIAGNOSIS_20261014.json")
                if "schema_validator" in key or "audit_trail" in key:
                    if pid in {"P16","P41","P44","P47","P50","P52"}:
                        proof.append(f"project-results/{pid}/forensics/FROZEN_STATIC_SCHEMA_AUDIT_20261014.json")
                record={"project_id":pid,"phase":phase,"assertion_key":key,"student_sha":sha,
                        "existing_verdict":verdict,"source_run":e["source_run"],
                        "original_source_kind":e["source_kind"],**cls,
                        "evidence_links":proof,"new_verdict_awarded":False,
                        "official_grade_changed":False,"instructor_review_required":True}
                cases.append(record)
                open_cases.append(record)
                review_rows.append({k:record.get(k) for k in ("project_id","phase","assertion_key","student_sha",
                                 "existing_verdict","root_cause_owner","cause_category","source_run","tracking_issue")})
        dest=pathlib.Path("project-results")/pid/"forensics"/"OPEN_ASSERTION_TRIAGE_20261014.json"
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps({"project_id":pid,"exact_student_sha":sha,
                  "phase_coverage":reference.get("phase_coverage"),
                  "passing_assertions_preserved":sum(v.get("PASS",0) for v in existing.values()),
                  "open_cases":cases,"open_count":len(cases),
                  "official_marks_unchanged":True},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        source_selection.append({"project_id":pid,"sha":sha,"open":len(cases),"pass_preserved":sum(v.get("PASS",0) for v in existing.values())})
    output.mkdir(parents=True,exist_ok=True)
    report={"status":"EVIDENCE_TRIAGE_OPEN_NOT_A_GRADE","submitted_projects":len(roster),
            "selected_sources":source_selection,"assertion_totals":dict(all_outcomes),
            "open_verdicts":len(open_cases),"open_owner_summary":dict(collections.Counter(c["root_cause_owner"] for c in open_cases)),
            "same_sha_PASS_overwrite_attempts_blocked":guarded,
            "same_sha_weaker_attempts_ignored":ignored,
            "not_all_nonpass_cases_have_proven_liability":True,
            "student_execution_count":0,"official_grade_changes":0,
            "source_policy":"Use only the exact selected student SHA and preserved same-SHA PASS. Empty phase means NOT_ASSESSED; never zero. This is a review queue, not a scoring ledger."}
    (output/"OPEN_ASSERTION_TRIAGE_SUMMARY_20261014.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (output/"OPEN_ASSERTION_TRIAGE_QUEUE_20261014.csv").open("w",encoding="utf-8-sig",newline="") as f:
        if review_rows:
            w=csv.DictWriter(f,fieldnames=list(review_rows[0]));w.writeheader();w.writerows(review_rows)
    print(json.dumps({"open_cases":len(open_cases),"selected_project_count":len(roster),
                      "protected_same_sha_pass":len(guarded),"student_executions":0,
                      "academic_changes":0},ensure_ascii=False))
if __name__=="__main__":main()
