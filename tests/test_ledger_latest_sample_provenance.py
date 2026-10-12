"""A same-FAIL new run must replace stale diagnostic samples, never the verdict."""
from grader.ledger import Ledger

SHA = "a"*40

def new_ledger():
    ledger=Ledger()
    ledger.projects["P11"]={"frozen_sha":SHA,"phases":{
        "midterm":{"entries":{},"status":"COMPLETED_WITH_FAILURES"},
        "final":{"entries":{},"status":"COMPLETED_WITH_FAILURES"},
    }}
    return ledger

def test_later_same_fail_replaces_stale_sample_note_and_evidence():
    ledger=new_ledger()
    source1={"type":"midterm_full","run_id":1}
    source2={"type":"midterm_full","run_id":2}
    first={"expected":">=70%","observed":"0/18 (0%)",
           "reason":"narrow midterm rerun after grader fix",
           "evidence":["طلب-714670: لم يتم العثور على سجل أعمال قابل للقراءة داخل الوثيقة."]}
    second={"expected":">=70%","observed":"0/18 (0%)",
            "reason":"narrow midterm rerun after grader fix",
            "evidence":["طلب-714670: حقول مختلفة: items; تطابق الحقول بعد التطبيع: 16/17"]}
    assert ledger.apply_change("P11","midterm","batch.cleaning_samples","FAIL",
                               source1,sha=SHA,detail=first)=="added"
    assert ledger.apply_change("P11","midterm","batch.cleaning_samples","FAIL",
                               source2,sha=SHA,detail=second)=="same"
    entry=ledger.projects["P11"]["phases"]["midterm"]["entries"]["batch.cleaning_samples"]
    assert entry["verdict"]=="FAIL"
    assert entry["origin"]["run_id"]==2
    assert "items" in entry["evidence_preview"]
    assert "لم يتم العثور" in entry["history"][-1]["previous_values"]["evidence_preview"]
    assert ledger.evidence_refreshes[0]["fields"]==["evidence_preview"]

def test_previous_pass_keeps_original_evidence():
    ledger=new_ledger()
    entry={"expected":1,"observed":1,"evidence":["baseline evidence"]}
    later={"expected":1,"observed":0,"evidence":["contradictory later evidence"]}
    ledger.apply_change("P11","midterm","batch_pipeline.command","PASS",
                        {"type":"midterm_full","run_id":1},sha=SHA,detail=entry)
    ledger.apply_change("P11","midterm","batch_pipeline.command","PASS",
                        {"type":"midterm_full","run_id":2},sha=SHA,detail=later)
    current=ledger.projects["P11"]["phases"]["midterm"]["entries"]["batch_pipeline.command"]
    assert current["origin"]["run_id"]==1
    assert "baseline evidence" in current["evidence_preview"]
