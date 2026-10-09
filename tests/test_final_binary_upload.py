import ast

from grader.final_runtime import _probe_python


def _extract_function(name):
    code = _probe_python()
    module = ast.parse(code)
    fun = next(n for n in module.body
               if isinstance(n, ast.FunctionDef) and n.name == name)
    return compile(ast.Module(body=[fun], type_ignores=[]),
                   filename="<test probe>", mode="exec")


def test_openapi_binary_upload_generates_real_file_attempt():
    namespace = {
        "DATASET": "/workspace/data/grader_hidden_input.csv",
        "resolve_schema": lambda _openapi, schema: schema,
        "sample_value": lambda name, schema: "dummy",
    }
    exec(_extract_function("build_ingest_attempts"), namespace)
    api = {"paths": {
        "/ingest": {"post": {"requestBody": {"content": {
            "multipart/form-data": {"schema": {
                "type": "object", "properties": {
                    "file": {"type": "string", "format": "binary"}
                }, "required": ["file"],
            }}
        }}}}
    }}
    attempts = namespace["build_ingest_attempts"](api)
    assert any(a["kind"] == "upload" and a["file_field"] == "file" for a in attempts)


def test_actual_upload_is_present_in_probe_source():
    code = _probe_python()
    ast.parse(code)
    assert 'def request_file_upload(' in code
    assert 'open(DATASET, "rb")' in code
    assert 'filename="grader_hidden_input.csv"' in code
    assert 'elif kind == "upload"' in code
