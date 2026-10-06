from pathlib import Path

from grader.normalization import clean_payload, compare_clean_record, audit_entries
from grader.runtime_evidence import detect_engine
from grader.oracle import HiddenOracle
from grader.scoring import derive_midterm_capabilities
from datasets.prepare_hidden_tests import ensure_prepared

ROOT = Path(__file__).resolve().parents[1]


def test_normalizes_nested_and_aliases():
    doc = {
        'id_order': 'طلب-1',
        'record_clean': {
            'order_id': 'طلب-1',
            'total_amount': 1000.0,
            'items_json': '[{"sku":"A","name":"X","qty":1,"unit_price":1000,"total":1000}]',
        },
        'corrections': [{'rule_code': 'R1'}],
    }
    payload = clean_payload(doc)
    assert payload['order_id'] == 'طلب-1'
    assert payload['items'][0]['sku'] == 'A'
    assert audit_entries(doc)


def test_compare_clean_record_semantic_items():
    actual = {
        'order_id': 'طلب-1',
        'total_amount': 1000,
        'items': [{'sku':'A','name':'X','qty':1,'unit_price':1000.0,'total':1000.0}],
    }
    expected = {
        'order_id': 'طلب-1',
        'total_amount': 1000.0,
        'items_json': '[{"sku":"A","name":"X","qty":1,"unit_price":1000,"total":1000}]',
    }
    ok, notes = compare_clean_record(actual, expected)
    assert ok, notes


def test_engine_detection_prefers_structured_evidence():
    metrics = {'used_engine': 'pyspark'}
    engine, evidence = detect_engine('Selected engine: pyspark', '', metrics, ['pyspark'])
    assert engine == 'pyspark'
    assert evidence


def test_hidden_oracle_is_consistent():
    hidden = ensure_prepared()
    oracle = HiddenOracle(hidden / 'teacher_key.json', hidden / 'teacher_manifest.csv')
    assert oracle.test('test_01')['validated_after_run'] == 17000
    assert len(oracle.sample('test_03', actions=['update'], n=5)) == 5


def test_capabilities_do_not_turn_inconclusive_into_zero():
    runtime = {'assertions': {
        'batch_pipeline.command': {'verdict':'PASS'},
        'batch.raw_count': {'verdict':'PASS'},
        'batch.validated_count': {'verdict':'PASS'},
        'batch.quarantine_count': {'verdict':'PASS'},
        'batch_pipeline.engine': {'verdict':'INCONCLUSIVE'},
    }}
    caps = derive_midterm_capabilities(runtime, {'has_readme':True,'has_requirements':True,'has_tests':True})
    assert caps['python_batch'] is None


def test_engine_detection_explicit_router_beats_spark_trace():
    stdout = "القرار: استخدام محرك [Python Batch] لأن الملف صغير.\n"
    stderr = "SparkSession org.apache.spark unresolved dependency"
    engine, evidence = detect_engine(stdout, stderr, None, [])
    assert engine == "python_batch"
    assert any("console-explicit" in x for x in evidence)
