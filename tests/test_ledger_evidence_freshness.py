"""Ledger regression: a newer FAIL can contain different, actionable evidence."""
import csv
import json
from build_ledger import write_outputs
from grader.ledger import Ledger

SHA = "a" * 40


def report(*, count, verdict="FAIL", note="aggregate_count_band"):
    return {"project_id": "P37", "commit_sha": SHA, "grader_version": "4.4-unified",
            "execution_plan": {},
            "runtime": {"status": "COMPLETED_WITH_FAILURES",
                        "assertions": {
                            "batch.validated_count": {"verdict": verdict, "expected": 17000,
                                                       "actual": count, "note": note},
                            "batch_pipeline.command": {"verdict": "PASS", "actual": 0},
                        }}}


def test_same_fail_refreshes_observed_count_without_altering_verdict(tmp_path):
    base = tmp_path/"base"/"reports"/"P37"
    base.mkdir(parents=True)
    (base/"result.json").write_text(json.dumps(report(count=0)), encoding="utf-8")
    ledger = Ledger()
    ledger.load_base(tmp_path/"base", run_id=1)
    ov = tmp_path/"overlays"/"regrade-P37-2"/"reports"/"P37"
    ov.mkdir(parents=True)
    (ov/"result.json").write_text(json.dumps(report(count=18250)), encoding="utf-8")
    stats = ledger.apply_overlay_dir(tmp_path/"overlays", run_id=2)
    ph = ledger.projects["P37"]["phases"]["midterm"]["entries"]
    current = ph["batch.validated_count"]
    assert current["verdict"] == "FAIL"
    assert current["actual"] == 18250
    assert current["origin"]["run_id"] == 2
    assert current["history"][-1]["previous_values"]["actual"] == 0
    assert stats["changes"] == 0 and stats["evidence_refreshes"] == 1
    assert len(ledger.evidence_refreshes) == 1
    assert ph["batch_pipeline.command"]["verdict"] == "PASS"
    assert ph["batch_pipeline.command"]["origin"]["run_id"] == 1
    assert ledger.verify(expected_projects=1)["baseline_pass_preserved"] == 1

    data=write_outputs(ledger, tmp_path/"out", 1)
    with (tmp_path/"out"/"review_queue.csv").open(encoding="utf-8-sig",newline="") as h:
        queue=list(csv.DictReader(h))
    assert queue[0]["actual"] == "18250"
    with (tmp_path/"out"/"source_audit.csv").open(encoding="utf-8-sig",newline="") as h:
        audit=list(csv.DictReader(h))
    assert audit[0]["evidence_refreshes"] == "1"
    assert data["invariants"]["ok"]


def test_untrusted_metadata_cannot_refresh_saved_failure(tmp_path):
    base = tmp_path/"base"/"reports"/"P37"
    base.mkdir(parents=True)
    (base/"result.json").write_text(json.dumps(report(count=0)), encoding="utf-8")
    ledger=Ledger()
    ledger.load_base(tmp_path/"base",run_id=1)
    source={"type":"metadata","run_id":2}
    result=ledger.apply_change("P37","midterm","batch.validated_count","FAIL",source,
                               detail={"observed":18250,"reason":"unsupported evidence"})
    e=ledger.projects["P37"]["phases"]["midterm"]["entries"]["batch.validated_count"]
    assert result=="same"
    assert e["actual"] == 0 and e["origin"]["run_id"] == 1
    assert ledger.evidence_refreshes == []
