import ast
import json
import re

from grader.final_runtime import _probe_python
from grader.final_compliance import readme_contract


def _probe_functions():
    tree = ast.parse(_probe_python())
    selected = {
        "sample_value", "semantic_query_param_names", "sample_query_parameter",
        "missing_query_parameters", "query_param_names_from_listing",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in selected]
    scope = {
        "json": json,
        "re": re,
        "openapi": {"paths": {}},
        "resolve_schema": lambda _openapi, schema: schema,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<query-probe-tests>", "exec"), scope)
    return scope


def test_p50_high_value_does_not_invent_dates():
    probe = _probe_functions()
    available = {"start_date", "end_date", "min_amount", "limit"}
    got = probe["semantic_query_param_names"]("high_value_orders", available)
    assert got == {"min_amount", "limit"}


def test_p01_p21_p54_p59_documented_query_parameters():
    probe = _probe_functions()
    infer = probe["semantic_query_param_names"]
    assert {"start", "end"}.issubset(infer("orders_in_period", {"start", "end", "limit"}))
    assert "reason" in infer("quarantined_by_reason", {"reason", "limit"})
    assert "order_id" in infer("order_id", {"order_id", "limit"})
    assert {"start", "end"}.issubset(infer("sales_by_period", {"start", "end", "limit"}))


def test_p28_shared_value_uses_query_specific_fixture():
    probe = _probe_functions()
    infer = probe["semantic_query_param_names"]
    sample = probe["sample_query_parameter"]
    assert "value" in infer("customer_orders", {"value", "limit"})
    assert sample("customer_orders", "value") == "CUST-001"
    assert sample("city_orders", "value") == "Sanaa"
    assert sample("status_orders", "value") == "Delivered"


def test_missing_422_required_params_retry_is_grounded():
    probe = _probe_functions()["missing_query_parameters"]
    res = {"status": 422, "body": {"detail": [
        {"loc": ["query", "value"], "msg": "Field required", "type": "missing"}]}}
    assert probe(res, {"value", "limit"}, {"limit"}) == ["value"]
    assert probe({"status": 500, "body": res["body"]}, {"value"}, set()) == []
    assert probe(res, {"limit"}, set()) == []


def test_missing_400_app_error_params_retry_is_grounded():
    probe = _probe_functions()["missing_query_parameters"]
    assert probe({"status": 400, "body": {"detail": "Missing city or status"}}, {"city", "status", "limit"}, set()) == ["city", "status"]
    assert probe({"status": 400, "body": {"detail": "Missing dates"}}, {"start_date", "end_date", "limit"}, set()) == ["end_date", "start_date"]


def test_env_example_optional_until_readme_requires_copy(tmp_path):
    source = (
        "Install with pip install -r requirements.txt. Run FastAPI uvicorn. "
        "Use queries indexes explain aggregations materialized views scheduled jobs."
    )
    (tmp_path / "README.md").write_text(source, encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    evidence = readme_contract(tmp_path)
    assert not evidence["env_instruction_broken"]
    assert not evidence["env_example"]
    (tmp_path / "README.md").write_text(source + "\ncp .env.example .env\n", encoding="utf-8")
    evidence = readme_contract(tmp_path)
    assert evidence["env_instruction_broken"]
    (tmp_path / ".env.example").write_text("DB_NAME=example\n", encoding="utf-8")
    assert not readme_contract(tmp_path)["env_instruction_broken"]
