from grader.evidence_regrade import regrade_saved_midterm


def case(name, before, after, rc=0):
    return {
        "name": name,
        "snapshot_before": {"validated": before},
        "snapshot_after": {"validated": after},
        "run": {"returncode": rc, "timed_out": False},
    }


def assertion(verdict, expected=None, actual=None):
    return {"verdict": verdict, "expected": expected, "actual": actual, "key": "test"}


def fixture():
    return {
        "project_id": "P03",
        "commit_sha": "unchanged-frozen-student-sha",
        "runtime": {
            "status": "COMPLETED_WITH_FAILURES",
            "assertions": {
                "batch_pipeline.command": assertion("PASS", 0, 0),
                "batch.validated_count": assertion("FAIL", 17000, 18500),
                "upsert.baseline_validated": assertion("FAIL", 17000, 18500),
                "upsert.final_validated": assertion("FAIL", 17600, 19250),
                "idempotency.validated_stable": assertion("FAIL", 17600, 19250),
                "incremental.final_validated": assertion("FAIL", 18100, 19801),
                "incremental.rerun_validated_stable": assertion("FAIL", 18100, 19801),
                "upsert.update_samples": assertion("FAIL", ">=80%", "0/12"),
            },
            "assertion_counts": {"PASS": 1, "FAIL": 7, "INCONCLUSIVE": 0, "ERROR": 0},
            "cases": [
                case("batch_pipeline", 0, 18500),
                case("upsert_baseline", 0, 18500),
                case("upsert_first", 18500, 19250),
                case("upsert_rerun", 19250, 19250),
                case("incremental_first", 19250, 19801),
                case("incremental_rerun", 19801, 19801),
            ],
        },
    }


def test_only_failed_count_evidence_is_reassessed():
    original = fixture()
    audit = regrade_saved_midterm(original, source_run_id=37874152827)
    assert original["runtime"]["assertions"]["idempotency.validated_stable"]["verdict"] == "FAIL"
    assert audit["student_commit"] == "unchanged-frozen-student-sha"
    assert audit["student_execution_performed"] is False
    assert "batch_pipeline.command" in audit["preserved_pass_keys"]
    assert audit["overrides"]["idempotency.validated_stable"]["new"] == "PASS"
    assert audit["overrides"]["incremental.rerun_validated_stable"]["new"] == "PASS"
    assert audit["overrides"]["upsert.baseline_validated"]["new"] == "PASS"
    assert "batch.validated_count" not in audit["overrides"]
    assert "upsert.final_validated" not in audit["overrides"]
    assert "incremental.final_validated" not in audit["overrides"]
    assert "upsert.update_samples" in audit["remaining_fail_keys"]
    assert audit["revised_assertion_counts"]["PASS"] == 4
    assert audit["revised_assertion_counts"]["FAIL"] == 4


def test_zero_is_never_counted_as_idempotency_success():
    original = fixture()
    for c in original["runtime"]["cases"]:
        if c["name"] in {"upsert_first", "upsert_rerun"}:
            c["snapshot_before"]["validated"] = 0
            c["snapshot_after"]["validated"] = 0
    audit = regrade_saved_midterm(original, source_run_id=1)
    assert audit["overrides"]["idempotency.validated_stable"]["new"] == "INCONCLUSIVE"


def test_no_pass_without_executed_command():
    original = fixture()
    for c in original["runtime"]["cases"]:
        if c["name"] == "upsert_rerun":
            c["run"]["returncode"] = 1
    audit = regrade_saved_midterm(original, source_run_id=1)
    assert "idempotency.validated_stable" not in audit["overrides"]


def test_pass_assertions_never_rewritten():
    original = fixture()
    original["runtime"]["assertions"]["idempotency.validated_stable"]["verdict"] = "PASS"
    original["runtime"]["assertion_counts"]["PASS"] += 1
    original["runtime"]["assertion_counts"]["FAIL"] -= 1
    audit = regrade_saved_midterm(original, source_run_id=1)
    assert "idempotency.validated_stable" not in audit["overrides"]
    assert "idempotency.validated_stable" in audit["preserved_pass_keys"]
