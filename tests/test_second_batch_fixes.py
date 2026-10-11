import ast

from grader.final_compliance import job_log_compliance
from grader.final_runtime import _probe_python
from grader.input_staging import plan_flag_retry, plan_processed_input_retry
from grader.normalization import audit_entries, error_codes
from grader.sandbox_runtime import _copy_without_bom


def test_bom_is_removed_from_csv_inputs_only(tmp_path):
    (tmp_path / "a.csv").write_bytes(b"\xef\xbb\xbforder_id,x\n1,2\n")
    (tmp_path / "b.csv").write_bytes(b"order_id\n1\n")
    (tmp_path / "c.txt").write_bytes(b"\xef\xbb\xbfhi")
    for name in ("a.csv", "b.csv", "c.txt"):
        _copy_without_bom(tmp_path / name, tmp_path / f"o_{name}")
    assert (tmp_path / "o_a.csv").read_bytes() == b"order_id,x\n1,2\n"
    assert (tmp_path / "o_b.csv").read_bytes() == b"order_id\n1\n"
    assert (tmp_path / "o_c.txt").read_bytes() == b"\xef\xbb\xbfhi"


def test_audit_and_error_fields_accept_equivalent_names():
    assert audit_entries({"cleaning_log": [{"field": "phone"}]})
    assert audit_entries({"changes_made": {"phone": "old->new"}})
    assert not audit_entries({"record_clean": {"order_id": "1"}})
    assert not audit_entries({"order_id": "1", "corrections_count": 3})
    assert error_codes({"validation_errors": ["A", "B"]}) == ["A", "B"]
    assert error_codes({"order_id": 1}) == []


def test_job_log_fields_accept_equivalent_names():
    rows = [{"job_id": "x", "started": 1, "finished": 2, "outcome": "ok", "records_processed": 3}]
    assert job_log_compliance(rows)["supported"] is True


def test_processed_other_csv_triggers_single_staging_candidate():
    out = "FINAL SUMMARY:\n  file_name: data/orders_small.csv\n  rows_read: 500"
    kwargs = dict(expected_rows=20000, hidden_file_rel="test_01_small_batch_pipeline.csv", fresh=True, already_staged=False)
    assert plan_processed_input_retry(out, {"raw": 500}, **kwargs) == "data/orders_small.csv"
    assert plan_processed_input_retry(out, {"raw": 20000}, **kwargs) is None
    assert plan_processed_input_retry("Input file : test_01_small_batch_pipeline.csv", {"raw": 500}, **kwargs) is None
    assert plan_processed_input_retry(out, {"raw": 500}, **{**kwargs, "already_staged": True}) is None


def test_check_only_run_with_execute_hint_is_retried_once():
    out = "ROUTER MODE: CHECK ONLY\nNo data was written.\nUse --execute to run the complete ELT pipeline."
    empty = {"raw": 0, "validated": 0, "quarantine": 0}
    assert plan_flag_retry(out, "python src/main.py --input x.csv", empty, fresh=True) == "python src/main.py --input x.csv --execute"
    assert plan_flag_retry(out, "python src/main.py --input x.csv --execute", empty, fresh=True) is None
    assert plan_flag_retry(out, "python main.py", {"raw": 5, "validated": 0, "quarantine": 0}, fresh=True) is None


def test_probe_handles_job_id_and_alternative_run_endpoints():
    code = _probe_python()
    ast.parse(code)
    assert 'item.get("job_id")' in code
    assert "def job_run_alternatives(" in code


def test_audit_list_of_strings_counts():
    assert audit_entries({"corrections": ["phone normalised", "city trimmed"]})
    assert not audit_entries({"corrections": []})


def test_external_audit_collection_is_accepted():
    from grader.mongo_checker import MongoChecker

    class FakeCol:
        def __init__(self, hit):
            self.hit = hit

        def find_one(self, query, projection=None):
            wanted = {"order_id": "A-1"}
            return {"_id": 1} if self.hit and any(c == wanted for c in query["$or"]) else None

    class FakeDb:
        def list_collection_names(self):
            return ["orders_raw", "orders_validated", "orders_quarantine", "correction_audit", "job_logs"]

        def __getitem__(self, name):
            return FakeCol(name == "correction_audit")

    mc = MongoChecker.__new__(MongoChecker)
    mc.db = FakeDb()
    mc.collections = {"raw": "orders_raw", "validated": "orders_validated", "quarantine": "orders_quarantine"}
    assert mc.external_audit("A-1") is True
    assert mc.external_audit("B-2") is False


def test_probe_waits_for_uninitialized_watermark():
    code = _probe_python()
    ast.parse(code)
    assert "def refresh_waiting_for_initialization(" in code
    assert "def precondition_refresh_first(" in code
