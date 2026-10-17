import json
from types import SimpleNamespace

import grader.tests_midterm as tm
from grader.mongo_checker import MongoChecker
from grader.sandbox import DockerSandbox, SandboxConfig


class FakeDb:
    def __init__(self, options=None, rows=True, failure=None):
        self.options = options or {}
        self.rows = rows
        self.failure = failure

    def command(self, spec):
        if self.failure:
            raise RuntimeError("cannot introspect")
        return {"cursor": {"firstBatch": [
            {"options": self.options}
        ] if self.rows else []}}


def _checker(db):
    obj = MongoChecker.__new__(MongoChecker)
    obj.db = db
    obj.collections = {"validated": "orders_validated"}
    return obj


def test_validator_inspection_distinguishes_present_absent_missing_and_query_error():
    assert _checker(FakeDb({"validator": {"$jsonSchema": {"bsonType": "object"}}})).inspect_json_schema_validator()["status"] == "PRESENT"
    assert _checker(FakeDb({"validator": {}})).inspect_json_schema_validator()["status"] == "ABSENT"
    assert _checker(FakeDb(rows=False)).inspect_json_schema_validator()["status"] == "COLLECTION_MISSING"
    assert _checker(FakeDb(failure=True)).inspect_json_schema_validator()["status"] == "UNVERIFIED"


def test_audit_trail_per_sample_evidence_is_redacted_and_attributes_source(monkeypatch):
    monkeypatch.setattr(tm, "compare_clean_record", lambda doc, expected: (bool(doc), []))
    monkeypatch.setattr(tm, "audit_entries", lambda doc: [])
    class FakeMongo:
        def find_validated(self, key):
            return {"order_id": key}
        def inspect_external_audit(self, key):
            if key.endswith("A"):
                return {"status": "FOUND", "collection": "audit_history"}
            if key.endswith("B"):
                return {"status": "NO_MATCH", "audit_collections": 1}
            return {"status": "UNVERIFIED", "reason": "audit_query_TimeoutError"}
    cases = [SimpleNamespace(expected_order_id=f"PRIVATE-{letter}",
              expected_clean_record={"order_id": f"PRIVATE-{letter}"})
             for letter in "ABC"]
    cleaning, audit = tm._verify_clean_samples(FakeMongo(), cases)
    assert len(audit.evidence) == 3
    assert all("PRIVATE-" not in x for x in audit.evidence)
    parsed = [json.loads(x) for x in audit.evidence]
    assert [x["audit_source"] for x in parsed] == ["external", "none", "none"]
    assert parsed[-1]["external_audit_status"] == "UNVERIFIED"
    assert audit.verdict == "INCONCLUSIVE"


def test_spark_prefetch_must_not_succeed_with_missing_jar(tmp_path, monkeypatch):
    root = tmp_path / "student"
    root.mkdir()
    (root / "requirements.txt").write_text("pyspark==3.5.1\npymongo>=4.6\n")
    (root / "spark_loader.py").write_text(
        'PACKAGE="org.mongodb.spark:mongo-spark-connector_2.12:10.3.0"\n'
        'df.write.format("mongodb").save()\n')
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    monkeypatch.setenv("GRADER_PREWARM_SPARK", "1")
    sb = DockerSandbox(tmp_path, "PTEST", root, hidden, SandboxConfig())
    sb.prepare_build_context()
    script = (sb.build_context / ".grader.spark-prewarm.sh").read_text()
    assert "GRADER_SPARK_PREFETCH_FAILED" in script
    assert "GRADER_SPARK_PREFETCH_MISSING_CONNECTOR" in script
    assert 'exit 41' in script and 'exit 42' in script
    assert "GRADER_SPARK_PREFETCH_VERIFIED" in script
