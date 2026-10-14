"""Regression for audit evidence serialization path in live midterm suite."""
import grader.sandbox_runtime as module

def test_mongo_validator_assertion_evidence_json_available():
    """Failure before first student assertion was grader NameError, not a student defect."""
    record={"status":"ABSENT","collection":"orders_validated","validator_operators":[]}
    assert module.json.loads(module.json.dumps(record,ensure_ascii=False,sort_keys=True))==record
