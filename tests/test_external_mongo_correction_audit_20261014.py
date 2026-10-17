from grader.mongo_checker import MongoChecker

class FakeAuditCollection:
    def __init__(self, records=None, fail=False):
        self.records = records or {}
        self.fail = fail
    def find_one(self, query, projection):
        if self.fail:
            raise RuntimeError("synthetic MongoDB audit read failure")
        clauses = query.get("$or") or []
        return {"_id": "found"} if any(
            any(self.records.get(k) == v for k,v in obj.items())
            for obj in clauses if isinstance(obj,dict)
        ) else None

class FakeDB:
    def __init__(self, matches=None,fail=False):
        self.audit = FakeAuditCollection(matches,fail)
    def list_collection_names(self):
        return ["orders_raw","orders_validated","orders_quarantine",
                "correction_audit","audit_job_runs"]
    def __getitem__(self, name):
        if name == "correction_audit":
            return self.audit
        raise AssertionError("Unrelated Mongo collection should not be queried: "+name)

def checker(db):
    m = MongoChecker.__new__(MongoChecker)
    m.db = db
    m.collections = {"raw":"orders_raw","validated":"orders_validated","quarantine":"orders_quarantine"}
    return m

def test_external_correction_audit_links_by_student_order_id():
    """Supports the separate correction_audit design in frozen P16 source."""
    found = checker(FakeDB({"order_id":"ORD-EXPECTED"})).inspect_external_audit("ORD-EXPECTED")
    assert found["status"] == "FOUND"
    assert found["collection"] == "correction_audit"
    assert found["examined"] == 1

def test_external_audit_absence_is_distinct_from_query_failure():
    missing = checker(FakeDB({"order_id":"OTHER"})).inspect_external_audit("ORD-EXPECTED")
    assert missing["status"] == "NO_MATCH"
    assert missing["audit_collections"] == 1
    error = checker(FakeDB(fail=True)).inspect_external_audit("ORD-EXPECTED")
    assert error["status"] == "UNVERIFIED"
    assert error["reason"] == "audit_query_RuntimeError"
