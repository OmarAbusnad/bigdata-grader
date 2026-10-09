import ast

from targeted_final_ingest import ingest_probe_source


def test_targeted_probe_is_valid_and_calls_only_ingest():
    source = ingest_probe_source()
    tree = ast.parse(source)
    assert 'request_file_upload("/ingest"' in source
    assert 'request("GET", "/openapi.json"' in source
    assert 'kind") == "upload"' in source
    # The standalone grading body must never request these formerly passed checks.
    focused = source.split('result = {"server_ready": False, "scope": "only_post_ingest"', 1)[1]
    assert 'request("GET", "/queries"' not in focused
    assert 'request("POST", "/indexes"' not in focused
    assert 'request("POST", "/refresh-mv"' not in focused
    assert 'request("GET", "/jobs"' not in focused
    assert any(isinstance(node, ast.FunctionDef) and node.name == 'request_file_upload'
               for node in tree.body)
