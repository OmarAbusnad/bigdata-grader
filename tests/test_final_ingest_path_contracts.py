import ast

from grader.final_runtime import _probe_python


def _attempts(openapi):
    code=_probe_python()
    tree=ast.parse(code)
    fn=next(n for n in tree.body
            if isinstance(n,ast.FunctionDef) and n.name=="build_ingest_attempts")
    namespace={
        "DATASET":"/grader-tests/grader_hidden_input.csv",
        "resolve_schema":lambda _openapi,schema:schema,
        "sample_value":lambda name,schema:"test",
    }
    exec(compile(ast.Module(body=[fn],type_ignores=[]),"probe","exec"),namespace)
    return namespace["build_ingest_attempts"](openapi)


def test_p32_freeform_dict_body_triggers_real_path_probe():
    o={"paths":{"/ingest":{"post":{"requestBody":{"content":{
      "application/json":{"schema":{"type":"object","additionalProperties":True}}
    }}}}}}
    attempts=_attempts(o)
    assert attempts[0]=={"kind":"json","body":{
        "file_path":"/grader-tests/grader_hidden_input.csv"
    }}
    assert len(attempts)==6
    assert not any(a["body"]=={} for a in attempts)


def test_p42_input_file_is_actual_hidden_dataset_not_dummy_test_string():
    o={"paths":{"/ingest":{"post":{"requestBody":{"content":{
      "application/json":{"schema":{"type":"object","properties":{
        "input_file":{"type":"string"}
      },"required":["input_file"]}}
    }}}}}}
    assert _attempts(o)==[{"kind":"json","body":{
      "input_file":"/grader-tests/grader_hidden_input.csv"
    }}]


def test_explicit_non_path_schema_keeps_defined_fields_only():
    o={"paths":{"/ingest":{"post":{"requestBody":{"content":{
      "application/json":{"schema":{"type":"object","properties":{
        "count":{"type":"integer"}
      },"required":["count"]}}
    }}}}}}
    assert _attempts(o)==[{"kind":"json","body":{"count":"test"}}]
