from pathlib import Path

from grader.agent_analyzer import collect_relevant_files, _normalize_response
from grader.models import ExecutionPlan
from grader.plan_resolution import resolve_execution_plan
from grader.sandbox_runtime import _render_command


def test_collect_relevant_files_prefers_execution_files(tmp_path: Path):
    (tmp_path/'README.md').write_text('Run: python src/main.py --input x.csv', encoding='utf-8')
    (tmp_path/'src').mkdir()
    (tmp_path/'src'/'main.py').write_text('import argparse\nif __name__ == "__main__": pass', encoding='utf-8')
    (tmp_path/'src'/'quality_rules.py').write_text('x=1', encoding='utf-8')
    got=collect_relevant_files(tmp_path)
    paths=[x['path'] for x in got]
    assert 'README.md' in paths
    assert 'src/main.py' in paths


def test_llm_plan_normalization_rejects_shell_chaining(tmp_path: Path):
    fallback=ExecutionPlan(repo_path=str(tmp_path), ingest_command='python src/main.py --input {file}')
    data={
      'ingest_command':'python src/main.py --input {file} && rm -rf /',
      'database':'x', 'collections':{'raw':'r','validated':'v','quarantine':'q'},
      'confidence':0.99
    }
    plan, meta=_normalize_response(data,fallback)
    assert plan.ingest_command == fallback.ingest_command
    assert plan.database_name == 'x'
    assert plan.collections['validated']=='v'


def test_render_command_uses_sandbox_dataset_path(tmp_path: Path):
    plan=ExecutionPlan(repo_path=str(tmp_path), ingest_command='python src/main.py --input {file} --db-name {db_name} --threshold-mb {threshold_mb}')
    cmd=_render_command(plan,'test.csv','grader_p01',20)
    assert '/grader-tests/test.csv' in cmd
    assert 'grader_p01' in cmd
    assert '20' in cmd


def test_heuristic_resolution_without_ai(tmp_path: Path):
    (tmp_path/'src').mkdir()
    (tmp_path/'src'/'main.py').write_text('''import argparse\np=argparse.ArgumentParser()\np.add_argument("--input")\nif __name__=="__main__": pass''',encoding='utf-8')
    plan, meta=resolve_execution_plan(tmp_path,use_ai=False)
    assert plan.ingest_command
    assert '{file}' in plan.ingest_command
    assert meta['status']=='HEURISTIC_ONLY'
