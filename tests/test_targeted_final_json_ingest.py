import ast
from targeted_final_json_ingest import ALLOWED, json_ingest_only_probe


def test_targeted_final_json_probe_compiles_and_only_calls_ingest():
    source=json_ingest_only_probe()
    ast.parse(source)
    focused=source.split('proof = {"server_ready": False, "scope":')[1]
    assert 'request("POST", "/ingest"' in focused
    assert 'request("GET", "/openapi.json"' in focused
    for other in ("/indexes","/queries","/refresh-mv","/jobs"):
        assert other not in focused
    assert focused.count('request("POST", "/ingest"')==1


def test_only_proven_failed_projects_eligible_for_json_retry():
    assert ALLOWED=={"P32":"grader_p32","P42":"midterm_data_pipeline"}
