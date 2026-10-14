"""Guard same-SHA PASS union and preserve missing late phase semantics."""
import json,pathlib
from tools.merge_late_grade_readiness import merge
def test_historical_pass_survives_weaker_later_verdict():
    protected=[]; candidates=[]
    actual=merge({"final.aggregations.runtime":"PASS","final.jobs.count":"FAIL",
                  "final.jobs.manual_run":"FAIL","final.api.ingest":"INCONCLUSIVE"},
                 {"final.aggregations.runtime":"INCONCLUSIVE","final.jobs.count":"PASS",
                  "final.jobs.manual_run":"PASS","final.api.ingest":"PASS"},
                 pid="P50",phase="final",sha="same",protected=protected,new_pass=candidates)
    assert actual=={"final.aggregations.runtime":"PASS","final.jobs.count":"PASS",
                     "final.jobs.manual_run":"PASS","final.api.ingest":"PASS"}
    assert len(protected)==1
    assert len(candidates)==3
    assert all(not item["officially_applied"] for item in candidates)
def test_missing_phase_never_construed_as_zero_mark():
    data=json.loads(pathlib.Path("docs/verified-late-source-manifest-20261014.json").read_text())
    entries={x["project_id"]:x for x in data["entries"]}
    assert "midterm" not in entries["P69"]["phases"]
    assert "final" not in entries["P68"]["phases"]
    assert set(entries["P70"]["phases"])=={"midterm","final"}
    assert len(set(entries))==len(data["entries"])
def test_failed_to_inconclusive_does_not_silently_erase_failure():
    actual=merge({"a":"FAIL"},{"a":"INCONCLUSIVE"},pid="T",phase="midterm",sha="same",protected=[],new_pass=[])
    assert actual["a"]=="FAIL"
