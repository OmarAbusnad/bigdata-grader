import ast

from targeted_query_p50 import restricted_query_probe_source


def test_p50_query_only_probe_is_python_and_never_calls_other_queries():
    script = restricted_query_probe_source()
    ast.parse(script)
    assert "/queries/high_value_orders?min_amount=200&limit=10" in script
    assert '"start_date"' in script and '"end_date"' in script
    assert '"only_query": "high_value_orders"' in script
    assert 'request("POST", "/ingest"' not in script
    assert 'request("POST", "/refresh-mv"' not in script
    assert 'request("GET", "/aggregations"' not in script
    assert '"request_params"] = {"min_amount": 200.0, "limit": 10}' in script
