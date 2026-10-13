import ast
import urllib.parse
from grader.final_runtime import _probe_python
from targeted_final_refresh import restricted_probe_source

def test_required_refresh_query_cannot_be_silently_omitted():
    tree=ast.parse(_probe_python())
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='refresh_mv_with_contract')
    scope={'resolve_schema':lambda _,s:s,'request':lambda method,path,body,timeout: {'status':200,'ok':True,'path':path}, 'urllib':urllib, 'discover_refresh_view_name':lambda _: None}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'test','exec'),scope)
    unresolved={'paths':{'/refresh-mv':{'post':{'parameters':[{'in':'query','name':'name','required':True,'schema':{'type':'string'}}]}}}}
    value=scope['refresh_mv_with_contract'](unresolved,True)
    assert value['probe_blocked']=='required_query_parameter_unresolved'
    with_enum={'paths':{'/refresh-mv':{'post':{'parameters':[{'in':'query','name':'name','required':True,'schema':{'type':'string','enum':['city_sales']}}]}}}}
    assert 'name=city_sales' in scope['refresh_mv_with_contract'](with_enum,True)['path']

def test_p59_focus_never_probes_prior_passing_endpoints():
    src=restricted_probe_source()
    ast.parse(src)
    body=src.split('result = {"server_ready": False, "scope":')[1]
    assert '/refresh-mv?name=city_sales' in body
    assert '/indexes' not in body and '/queries' not in body and '/jobs' not in body


def test_p59_read_frozen_literal_mv_names_instead_of_guess(tmp_path):
    import os
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        'MV_NAMES = ["city_sales", "daily_sales"]\\n', encoding="utf-8"
    )
    tree = ast.parse(_probe_python())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in {"discover_refresh_view_name", "refresh_mv_with_contract"}]
    def request(method, path, body, timeout):
        return {"status": 200, "ok": True, "path": path}
    scope = {"os": os, "urllib": urllib, "request": request,
             "names_from": lambda *args: [],
             "resolve_schema": lambda _, x: x}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "probe", "exec"), scope)
    found = scope["discover_refresh_view_name"]({"paths": {}}, str(tmp_path))
    assert found == "city_sales"
    scope["discover_refresh_view_name"] = lambda _: found
    openapi = {"paths": {"/refresh-mv": {"post": {"parameters": [
        {"name": "name", "in": "query", "required": True, "schema": {"type": "string"}}
    ]}}}}
    got = scope["refresh_mv_with_contract"](openapi, False)
    assert got["ok"] is True
    assert "name=city_sales" in got["path"]
