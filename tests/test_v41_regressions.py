from __future__ import annotations

import json
from pathlib import Path

import pytest

from grader.discovery import discover_execution_plan
from grader.overrides import apply_instructor_override
from grader.models import ExecutionPlan
from grader.scoring import score_boolean_checks
from grader.sandbox_runtime import _copy_input_view
from grader.oracle import HiddenOracle


def test_student_grader_yaml_is_not_required_or_trusted(tmp_path: Path):
    (tmp_path / 'grader.yaml').write_text('commands:\n  ingest: "python evil.py"\n', encoding='utf-8')
    (tmp_path / 'main.py').write_text('''import argparse\np=argparse.ArgumentParser()\np.add_argument("--input")\nif __name__ == "__main__": p.parse_args()\n''', encoding='utf-8')
    plan = discover_execution_plan(tmp_path)
    assert plan.ingest_command == 'python main.py --input {file}'
    assert plan.source == 'heuristic'


def test_instructor_override_is_external_and_high_confidence():
    plan = ExecutionPlan(repo_path='/tmp/x', ingest_command='python main.py --input {file}', confidence=.5)
    updated, evidence = apply_instructor_override(plan, {
        'ingest_command': 'python src/main.py --input {file} --db-name {db_name}',
        'database_name': 'grader_db',
        'database_configurable': True,
    })
    assert updated.ingest_command.startswith('python src/main.py')
    assert updated.database_name == 'grader_db'
    assert updated.confidence >= .99
    assert evidence


def test_draft_midterm_rubric_cannot_score():
    rubric = json.loads((Path(__file__).parents[1] / 'rubrics' / 'midterm_18.json').read_text(encoding='utf-8'))
    with pytest.raises(RuntimeError):
        score_boolean_checks(rubric, {'python_batch': True})


def test_final_rubric_exact_total():
    rubric = json.loads((Path(__file__).parents[1] / 'rubrics' / 'final_7.json').read_text(encoding='utf-8'))
    assert rubric['status'] == 'ACTIVE'
    assert sum(float(x['points']) for x in rubric['items']) == pytest.approx(7.0)
    assert {x['key']: x['points'] for x in rubric['items']} == {
        'queries_indexes_explain': 1.5,
        'aggregations': 1.5,
        'materialized_views': 1.5,
        'scheduled_jobs': 1.0,
        'unified_api': 0.75,
        'github_readme': 0.50,
        'discussion_understanding': 0.25,
    }


def test_input_view_excludes_teacher_oracle(tmp_path: Path):
    hidden = tmp_path / 'hidden'; hidden.mkdir()
    specs = {}
    for i in range(1, 5):
        name = f't{i}.csv'
        (hidden / name).write_text('order_id\n1\n', encoding='utf-8')
        specs[f'test_0{i}'] = {'file': name}
    key = {'recommended_discussion_threshold_mb': 20, **specs}
    (hidden / 'teacher_key.json').write_text(json.dumps(key), encoding='utf-8')
    (hidden / 'teacher_manifest.csv').write_text('dataset\nSECRET\n', encoding='utf-8')
    oracle = HiddenOracle(hidden / 'teacher_key.json', hidden / 'teacher_manifest.csv')
    out = tmp_path / 'view'
    mapping = _copy_input_view(hidden, oracle, out)
    assert set(p.name for p in out.iterdir()) == {'t1.csv','t2.csv','t3.csv','t4.csv'}
    assert 'teacher_key.json' not in {p.name for p in out.iterdir()}
    assert mapping['test_01'] == 't1.csv'
