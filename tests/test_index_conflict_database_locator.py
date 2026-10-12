"""Bounded recovery must never erase nonempty or ambiguous student DBs."""
from grader.mongo_checker import MongoChecker

class Coll:
    def __init__(self, n=0, indexes=()):
        self.n=n
        self.idx=list(indexes)
    def count_documents(self, _query):
        return self.n
    def list_indexes(self):
        return self.idx

class DB:
    def __init__(self, cols):
        self.cols=cols
    def list_collection_names(self):
        return list(self.cols)
    def __getitem__(self, key):
        return self.cols[key]

class Client:
    def __init__(self, dbs):
        self.dbs=dbs
    def list_database_names(self):
        return list(self.dbs)
    def __getitem__(self, key):
        return self.dbs[key]

UNIQUE = {"name":"order_id_1","unique":True,"key":{"order_id":1}}
NOT_UNIQUE = {"name":"order_id_1","key":{"order_id":1}}

def checker(dbs):
    chk=MongoChecker.__new__(MongoChecker)
    chk.client=Client(dbs)
    chk.database_name="grader_p41"
    chk.db=DB({})
    chk.collections={"raw":"orders_raw","validated":"orders_validated","quarantine":"orders_quarantine"}
    chk.business_key="order_id"
    return chk

def test_unique_empty_real_database_found_despite_nominal_alias():
    x=checker({"grader_p41":DB({}),
               "midterm_db":DB({"orders_validated":Coll(indexes=[UNIQUE]),"orders_raw":Coll()})})
    name,evidence=x.find_unambiguous_empty_unique_index_database()
    assert name=="midterm_db"
    assert any("unique business-key" in str(t) for t in evidence)

def test_nonempty_database_is_never_selected():
    x=checker({"midterm_db":DB({"orders_validated":Coll(indexes=[UNIQUE]),
                                 "orders_raw":Coll(n=1)})})
    name,notes=x.find_unambiguous_empty_unique_index_database()
    assert name is None and any("refusing reset" in t for t in notes)

def test_two_matching_databases_are_never_guessed():
    x=checker({"midterm_db":DB({"orders_validated":Coll(indexes=[UNIQUE])}),
               "second_db":DB({"orders_validated":Coll(indexes=[UNIQUE])})})
    name,notes=x.find_unambiguous_empty_unique_index_database()
    assert name is None and any("candidate_database_count=2" in t for t in notes)

def test_nonunique_or_unrelated_index_is_never_selected():
    x=checker({"midterm_db":DB({"orders_validated":Coll(indexes=[NOT_UNIQUE])})})
    assert x.find_unambiguous_empty_unique_index_database()[0] is None
    y=checker({"midterm_db":DB({"orders_validated":Coll(indexes=[
        {"name":"idx_other","unique":True,"key":{"customer_id":1}}
    ])})})
    assert y.find_unambiguous_empty_unique_index_database()[0] is None


def test_partial_failed_attempt_is_eligible_only_with_explicit_opt_in():
    x=checker({"midterm_db":DB({
        "orders_validated":Coll(n=18750,indexes=[UNIQUE]),
        "orders_raw":Coll(n=20000), "orders_quarantine":Coll(n=1250)
    })})
    assert x.find_unambiguous_empty_unique_index_database()[0] is None
    chosen,evidence=x.find_unambiguous_empty_unique_index_database(
        allow_partial_failed_attempt=True
    )
    assert chosen=="midterm_db"
    assert any("partial output from failed stage" in t for t in evidence)


def test_partial_opt_in_still_refuses_two_possible_databases():
    x=checker({
        "first":DB({"orders_validated":Coll(n=2,indexes=[UNIQUE])}),
        "second":DB({"orders_validated":Coll(n=2,indexes=[UNIQUE])}),
    })
    chosen,evidence=x.find_unambiguous_empty_unique_index_database(
        allow_partial_failed_attempt=True
    )
    assert chosen is None
    assert any("candidate_database_count=2" in t for t in evidence)
