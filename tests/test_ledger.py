import json
from pathlib import Path

import pytest

from build_ledger import write_outputs
from grader.ledger import Ledger

SHA = "a" * 40


def A(verdict, expected=None, actual=None):
    return {"verdict": verdict, "expected": expected, "actual": actual}


def write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def mid(pid, assertions, sha=SHA, status="COMPLETED_WITH_FAILURES"):
    return {"project_id": pid, "commit_sha": sha, "students": "s",
            "runtime": {"status": status, "assertions": assertions}}


def fin(pid, assertions, sha=SHA):
    return {"project_id": pid, "commit_sha": sha,
            "runtime": {"status": "COMPLETED_WITH_REVIEW",
                        "assertions": [dict(key=k, **v) for k, v in assertions.items()]}}


@pytest.fixture
def base(tmp_path):
    root = tmp_path / "base"
    write(root / "unified-P05-1/reports/P05/result.json", mid("P05", {
        "batch_pipeline.command": A("PASS"),
        "spark_pipeline.command": A("INCONCLUSIVE"),
        "spark.raw_count": A("INCONCLUSIVE", 100000),
        "upsert.final_validated": A("FAIL", 600, 100),
    }))
    write(root / "unified-P05-1/reports_final/P05/result.json", fin("P05", {
        "final.api.health": A("PASS"),
        "final.api.ingest": A("FAIL", actual="TimeoutError: timed out"),
    }))
    write(root / "unified-P06-1/reports/P06/result.json", mid("P06", {"batch.raw_count": A("PASS")}, sha="b" * 40))
    return root


def build(base):
    ledger = Ledger()
    ledger.load_base(base, run_id=1)
    return ledger


def entry(ledger, pid, phase, key):
    return ledger.projects[pid]["phases"][phase]["entries"][key]


def test_base_loads_both_phases_and_shapes(base):
    ledger = build(base)
    assert set(ledger.projects) == {"P05", "P06"}
    assert entry(ledger, "P05", "final", "final.api.health")["verdict"] == "PASS"
    assert ledger.projects["P05"]["frozen_sha"] == SHA
    assert ledger.verify(expected_projects=2)["ok"]


def test_duplicate_base_project_is_an_error(base):
    write(base / "other/reports/P05/result.json", mid("P05", {}))
    with pytest.raises(ValueError):
        build(base)


def test_spark_proof_promotes_only_non_pass_and_keeps_pass(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "spark"
    write(ov / "P05/spark_only.json", {
        "project_id": "P05", "source_run": 37874152827, "frozen_commit": SHA,
        "only_test": "spark_pipeline.command", "passed_tests_reexecuted": 0,
        "other_tests_reexecuted": 0, "official_grade_changed": False, "verdict": "PASS",
        "run": {"returncode": 0, "timed_out": False}, "engine": "pyspark",
        "after": {"raw": 100000, "validated": 100000, "quarantine": 0, "duplicate_business_keys": 0}})
    stats = ledger.apply_overlay_dir(ov, run_id=38003977105)
    assert stats["spark_proofs"] == 1
    assert entry(ledger, "P05", "midterm", "spark_pipeline.command")["verdict"] == "PASS"
    assert entry(ledger, "P05", "midterm", "spark.raw_count")["verdict"] == "PASS"
    assert entry(ledger, "P05", "midterm", "batch_pipeline.command")["verdict"] == "PASS"
    assert entry(ledger, "P05", "midterm", "upsert.final_validated")["verdict"] == "FAIL"
    assert entry(ledger, "P05", "midterm", "spark.raw_count")["history"][0]["source"]["run_id"] == 38003977105
    assert ledger.verify()["ok"]


def test_spark_proof_with_other_sha_is_refused(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "spark"
    write(ov / "x.json", {"project_id": "P05", "source_run": 37874152827, "frozen_commit": "c" * 40,
                          "only_test": "spark_pipeline.command", "passed_tests_reexecuted": 0,
                          "other_tests_reexecuted": 0, "official_grade_changed": False,
                          "verdict": "PASS", "run": {"returncode": 0, "timed_out": False},
                          "engine": "pyspark", "after": {"raw": 1, "validated": 1}})
    ledger.apply_overlay_dir(ov, run_id=2)
    assert entry(ledger, "P05", "midterm", "spark_pipeline.command")["verdict"] == "INCONCLUSIVE"
    assert ledger.rejected and ledger.rejected[0]["reason"] == "spark_overlay_refused"


def test_midterm_rerun_never_overwrites_pass_and_logs_conflict(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "rerun"
    write(ov / "reports/P05/result.json", mid("P05", {
        "batch_pipeline.command": A("FAIL"),
        "spark_pipeline.command": A("PASS"),
        "upsert.final_validated": A("INCONCLUSIVE")}))
    ledger.apply_overlay_dir(ov, run_id=3)
    assert entry(ledger, "P05", "midterm", "batch_pipeline.command")["verdict"] == "PASS"
    assert any(c["reason"] == "would_overwrite_pass" for c in ledger.conflicts)
    assert entry(ledger, "P05", "midterm", "spark_pipeline.command")["verdict"] == "PASS"
    kept = entry(ledger, "P05", "midterm", "upsert.final_validated")
    assert kept["verdict"] == "FAIL" and kept["flags"]


def test_rerun_with_wrong_sha_rejected(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "rerun"
    write(ov / "reports/P05/result.json", mid("P05", {"spark_pipeline.command": A("PASS")}, sha="d" * 40))
    ledger.apply_overlay_dir(ov, run_id=3)
    assert entry(ledger, "P05", "midterm", "spark_pipeline.command")["verdict"] == "INCONCLUSIVE"
    assert ledger.rejected[0]["reason"] == "sha_mismatch"


def test_evidence_overlay_may_reclassify_fail_to_inconclusive(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "ev"
    write(ov / "overlays.json", {"student_tests_reexecuted": 0, "projects": {"P05": {
        "student_commit": SHA, "overrides": {"upsert.final_validated": {
            "previous": "FAIL", "new": "INCONCLUSIVE", "expected": 600, "observed": 590, "reason": "within band"}}}}})
    ledger.apply_overlay_dir(ov, run_id=4)
    assert entry(ledger, "P05", "midterm", "upsert.final_validated")["verdict"] == "INCONCLUSIVE"


def test_final_ingest_proof_promotes_fail_and_flags_missing_sha(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "fi"
    write(ov / "P05/result.json", {"project": "P05", "scope": "only_final.api.ingest", "verdict": "PASS",
                                   "reason": "correct_request_contract_and_new_persisted_mongodb_documents"})
    ledger.apply_overlay_dir(ov, run_id=5)
    e = entry(ledger, "P05", "final", "final.api.ingest")
    assert e["verdict"] == "PASS" and "sha_not_in_proof" in e["flags"]


def test_final_inconclusive_proof_does_not_erase_fail(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "fi"
    write(ov / "P05/result.json", {"project": "P05", "scope": "only_final.api.ingest", "verdict": "INCONCLUSIVE"})
    ledger.apply_overlay_dir(ov, run_id=5)
    assert entry(ledger, "P05", "final", "final.api.ingest")["verdict"] == "FAIL"


def test_rulings_need_reason_and_cannot_overwrite_pass_silently(base):
    ledger = build(base)
    ledger.apply_rulings([
        {"project_id": "P05", "phase": "final", "key": "final.api.ingest", "to": "INCONCLUSIVE",
         "reason": "timeout without HTTP status", "decided_by": "instructor"},
        {"project_id": "P05", "phase": "final", "key": "final.api.health", "to": "FAIL",
         "reason": "x", "decided_by": "instructor"},
        {"project_id": "P05", "phase": "final", "key": "final.api.docs", "to": "PASS"},
    ])
    assert entry(ledger, "P05", "final", "final.api.ingest")["verdict"] == "INCONCLUSIVE"
    assert entry(ledger, "P05", "final", "final.api.health")["verdict"] == "PASS"
    assert any(r["reason"] == "ruling_missing_field" for r in ledger.rejected)


def test_explicit_pass_override_is_listed_and_not_counted_as_lost(base):
    ledger = build(base)
    ledger.apply_rulings([{"project_id": "P05", "phase": "final", "key": "final.api.health", "to": "FAIL",
                           "reason": "evidence shows endpoint 500", "decided_by": "instructor",
                           "override_pass": True}])
    inv = ledger.verify()
    assert inv["ok"] and inv["pass_overrides"] == 1


def test_outputs_written_and_review_queue_has_only_non_pass(base, tmp_path):
    ledger = build(base)
    data = write_outputs(ledger, tmp_path / "out", expected=2)
    assert data["invariants"]["ok"]
    queue = (tmp_path / "out/review_queue.csv").read_text(encoding="utf-8-sig")
    assert "final.api.health" not in queue and "final.api.ingest" in queue
    assert "candidate_transport_timeout_no_http_status" in queue
    assert (tmp_path / "out/project_summary.csv").exists()


def test_invariant_flags_wrong_project_count(base):
    assert not build(base).verify(expected_projects=68)["ok"]


def test_midterm_report_at_artifact_root_is_recognized(base, tmp_path):
    ledger = build(base)
    ov = tmp_path / "root_layout"
    rep = mid("P05", {"spark_pipeline.command": A("PASS")})
    rep["execution_plan"] = {}
    write(ov / "targeted-midterm-P05-123/result.json", rep)
    stats = ledger.apply_overlay_dir(ov, run_id=7)
    assert stats["midterm_reports"] == 1 and stats["ignored_files"] == 0
    assert entry(ledger, "P05", "midterm", "spark_pipeline.command")["verdict"] == "PASS"


def test_final_report_at_root_is_not_taken_as_midterm(base):
    rep = fin("P05", {"final.api.health": A("PASS")})
    rep["final_plan"] = {}
    from grader.ledger import _is_midterm_report, _is_final_report
    assert not _is_midterm_report("x/result.json", rep) and _is_final_report("x/result.json", rep)

def test_overlay_unknown_json_causes_hard_failure(base, tmp_path):
    ledger = build(base)
    root = tmp_path / "unknown-run"
    write(root / "P05/not_accepted.json", {
        "project_id": "P05", "result": {"verdict": "PASS"},
        "reason": "unrecognized structure must not be silently discarded",
    })
    with pytest.raises(ValueError, match="unrecognized evidence"):
        ledger.apply_overlay_dir(root, run_id=8800)
    assert entry(ledger, "P05", "midterm", "spark_pipeline.command")["verdict"] == "INCONCLUSIVE"


def test_archive_metadata_is_explicitly_counted_but_not_applied(base, tmp_path):
    ledger = build(base)
    root = tmp_path / "archive-recovery"
    write(root / "reports/P05/result.json", mid("P05", {"spark_pipeline.command": A("PASS")}))
    write(root / "reports_archive_recovery/P05/extraction_proof.json", {
        "container": "zip", "frozen_archive": "P05.zip",
        "source_root": "/tmp/safe/P05", "student_code_executed_during_extraction": False,
        "official_result_modified": False,
    })
    stats = ledger.apply_overlay_dir(root, run_id=1)
    assert stats["files_seen"] == 2
    assert stats["midterm_reports"] == 1
    assert stats["metadata_files"] == 1
    assert stats["ignored_files"] == 0
    assert stats["changes"] == 1
    assert {x["kind"] for x in stats["files"]} == {
        "safe_extraction_metadata", "midterm_full",
    }


def test_run_with_only_metadata_rejected(base, tmp_path):
    ledger = build(base)
    root=tmp_path/"only-metadata"
    write(root/"extraction_proof.json",{
        "container":"zip", "frozen_archive":"a.zip","source_root":"/safe",
        "student_code_executed_during_extraction": False,
        "official_result_modified":False,
    })
    with pytest.raises(ValueError, match="only metadata"):
        ledger.apply_overlay_dir(root, run_id=77)


def test_malformed_overlay_json_is_not_silently_ignored(base, tmp_path):
    ledger=build(base)
    folder=tmp_path/"bad"
    folder.mkdir()
    (folder/"grade.json").write_text("{'not-json'",encoding="utf-8")
    with pytest.raises(ValueError,match="Cannot parse overlay evidence"):
        ledger.apply_overlay_dir(folder,run_id=123)


def test_missing_overlay_directory_is_not_silent(base, tmp_path):
    ledger=build(base)
    with pytest.raises(ValueError,match="is missing"):
        ledger.apply_overlay_dir(tmp_path/"does-not-exist",run_id=123)


def test_review_and_source_audit_csv_exports(base, tmp_path):
    ledger=build(base)
    root=tmp_path/"proof"
    write(root/"P05/spark_only.json", {
        "project_id":"P05","source_run":37874152827,"frozen_commit":SHA,
        "only_test":"spark_pipeline.command",
        "passed_tests_reexecuted":0,"other_tests_reexecuted":0,
        "official_grade_changed":False,"verdict":"PASS",
        "run":{"returncode":0,"timed_out":False},"engine":"pyspark",
        "after":{"raw":100000,"validated":100000,"quarantine":0,"duplicate_business_keys":0},
    })
    stats=ledger.apply_overlay_dir(root,run_id=38003977105)
    write_outputs(ledger,tmp_path/"results",expected=2)
    assert stats["changes"] == 2
    summary=(tmp_path/"results/source_audit.csv").read_text(encoding="utf-8-sig")
    assert "38003977105" in summary and "spark_recovery" in summary
    assert "P05/spark_only.json" in summary
    assert "review_queue.csv" in [p.name for p in (tmp_path/"results").iterdir()]


def test_frozen_http_timeouts_are_review_not_fail(base):
    ledger=build(base)
    ledger._base_probes["P05"]={
        "ingest_attempts":[{"response":{"status":None,"ok":False,
                     "error":"TimeoutError: timed out"}}],
        "refresh_mv_first":{"status":500,"ok":False,
                           "body":{"detail":"student failed"}},
    }
    result=ledger.apply_frozen_transport_preconditions(base_run_id=1)
    assert result["changes"] == 1
    assert result["cases"][0]["project_id"]=="P05"
    assert result["cases"][0]["key"]=="final.api.ingest"
    assert entry(ledger,"P05","final","final.api.ingest")["verdict"]=="INCONCLUSIVE"
    assert entry(ledger,"P05","final","final.api.health")["verdict"]=="PASS"
    assert ledger.verify()["ok"]


def test_transport_http_500_not_downgraded(base):
    ledger=build(base)
    ledger._base_probes["P05"]={
        "ingest_attempts":[{"response":{"status":500,"ok":False,
                                           "error":"timeout in database"}}]}
    ledger.apply_frozen_transport_preconditions(base_run_id=1)
    assert entry(ledger,"P05","final","final.api.ingest")["verdict"]=="FAIL"


def test_transport_respects_later_pass_and_mixed_http_results(base,tmp_path):
    ledger=build(base)
    ledger._base_probes["P05"]={
        "ingest_attempts":[
            {"response":{"status":500,"error":"server internal"}},
            {"response":{"status":None,"error":"TimeoutError: timed out"}}
        ]}
    ledger.apply_frozen_transport_preconditions(base_run_id=1)
    assert entry(ledger,"P05","final","final.api.ingest")["verdict"]=="FAIL"
    ov=tmp_path/"proof"
    write(ov/"result.json", {
        "project":"P05","scope":"only_final.api.ingest","verdict":"PASS",
        "reason":"persisted after correct input"
    })
    ledger.apply_overlay_dir(ov,run_id=999)
    ledger._base_probes["P05"]={"ingest_attempts":[{"response":{
        "status":None,"error":"TimeoutError: timed out"}}]}
    assert ledger.apply_frozen_transport_preconditions(base_run_id=1)["changes"]==0
    assert entry(ledger,"P05","final","final.api.ingest")["verdict"]=="PASS"
