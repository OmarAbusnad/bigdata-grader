import ast
import urllib.parse
from grader.final_runtime import _probe_python
from targeted_final_refresh import restricted_probe_source

def test_required_refresh_query_cannot_be_silently_omitted():
    tree=ast.parse(_probe_python())
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='refresh_mv_with_contract')
    scope={'resolve_schema':lambda _,s:s,'request':lambda method,path,body,timeout: {'status':200,'ok':True,'path':path}, 'urllib':urllib}
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
