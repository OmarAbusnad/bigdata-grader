from grader.mongo_checker import MongoChecker


class FakeCollection:
    def __init__(self, count):
        self.count = count

    def count_documents(self, selector):
        assert selector == {}
        return self.count


class FakeDatabase:
    def __init__(self, collections):
        self.collections = collections

    def list_collection_names(self):
        return list(self.collections)

    def __getitem__(self, name):
        return FakeCollection(self.collections[name])


class FakeClient:
    def __init__(self, databases):
        self.databases = {name: FakeDatabase(collections) for name, collections in databases.items()}

    def list_database_names(self):
        return list(self.databases)

    def __getitem__(self, name):
        return self.databases[name]


def checker(databases):
    value = MongoChecker.__new__(MongoChecker)
    value.client = FakeClient(databases)
    value.collections = {
        "raw": "orders_raw",
        "validated": "orders_validated",
        "quarantine": "orders_quarantine",
    }
    value.database_name = "grader_sample"
    value.db = value.client.databases.get("grader_sample", FakeDatabase({}))
    return value


def test_unique_active_database_discovered():
    c = checker({"grader_sample": {}, "student_orders": {"orders_raw": 12, "orders_validated": 10}})
    name, evidence = c.locate_active_database()
    assert name == "student_orders"
    assert evidence
    c.switch_database(name)
    assert c.counts()["validated"] == 10


def test_empty_setup_collections_do_not_count_as_pipeline_activity():
    c = checker({"grader_sample": {}, "student_orders": {"orders_raw": 0, "orders_validated": 0}})
    assert c.locate_active_database()[0] is None


def test_ambiguous_databases_are_never_silently_selected():
    c = checker({
        "one": {"orders_raw": 5},
        "two": {"orders_validated": 5},
    })
    name, evidence = c.locate_active_database()
    assert name is None
    assert len(evidence) == 2


def test_system_database_is_ignored():
    c = checker({"admin": {"orders_raw": 3}, "student": {"orders_validated": 1}})
    assert c.locate_active_database()[0] == "student"
