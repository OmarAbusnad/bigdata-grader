"""Latest midterm execution metadata must not conceal preserved verdict evidence."""
import json
from grader.ledger import Ledger

SHA = "a" * 40


def report(status, assertions):
    return {"project_id": "P01", "commit_sha": SHA, "grader_version": "4.4-unified",
            "execution_plan": {}, "runtime": {"status": status, "assertions": assertions}}


def test_environment_block_without_assertions_updates_latest_status_not_verdict(tmp_path):
    root = tmp_path / "base" / "reports" / "P01"
    root.mkdir(parents=True)
    (root / "result.json").write_text(
        json.dumps(report("STARTUP_BLOCKED", {"batch_pipeline.command": {"verdict": "PASS"}})))
    ledger = Ledger()
    ledger.load_base(tmp_path / "base", run_id=1)
    overlay = tmp_path / "overlay" / "reports" / "P01"
    overlay.mkdir(parents=True)
    (overlay / "result.json").write_text(
        json.dumps(report("BLOCKED_BY_ENVIRONMENT", {})))
    stats = ledger.apply_overlay_dir(tmp_path / "overlay", run_id=2)
    phase = ledger.projects["P01"]["phases"]["midterm"]
    assert stats["changes"] == 0
    assert phase["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert phase["status_history"][-1]["from"] == "STARTUP_BLOCKED"
    assert phase["status_history"][-1]["to"] == "BLOCKED_BY_ENVIRONMENT"
    assert phase["entries"]["batch_pipeline.command"]["verdict"] == "PASS"
    assert ledger.verify(expected_projects=1)["baseline_pass_preserved"] == 1


def test_latest_midterm_status_tracks_successful_rerun_without_replacing_pass(tmp_path):
    base = tmp_path / "base" / "reports" / "P01"
    base.mkdir(parents=True)
    (base / "result.json").write_text(json.dumps(report(
        "STARTUP_BLOCKED", {"batch_pipeline.command": {"verdict": "PASS"}})))
    ledger = Ledger()
    ledger.load_base(tmp_path / "base", run_id=1)
    ov = tmp_path / "overlay" / "reports" / "P01"
    ov.mkdir(parents=True)
    (ov / "result.json").write_text(json.dumps(report(
        "COMPLETED_WITH_FAILURES", {"batch_pipeline.command": {"verdict": "FAIL"},
                                    "batch.raw_count": {"verdict": "PASS"}})))
    ledger.apply_overlay_dir(tmp_path / "overlay", run_id=2)
    phase = ledger.projects["P01"]["phases"]["midterm"]
    assert phase["status"] == "COMPLETED_WITH_FAILURES"
    assert phase["entries"]["batch_pipeline.command"]["verdict"] == "PASS"
    assert phase["entries"]["batch.raw_count"]["verdict"] == "PASS"
    assert any(c["reason"] == "would_overwrite_pass" for c in ledger.conflicts)
