from pathlib import Path
from types import SimpleNamespace

import grader.tests_midterm as tm
from grader.models import CommandResult


class FakeOracle:
    threshold_mb = 20
    specs = {
        'test_01': {'file':'t1.csv','input':20000,'validated_after_run':17000,'quarantine':3000},
        'test_02': {'file':'t2.csv','input':100000,'validated_after_run':100000,'quarantine':0},
        'test_03': {'file':'t3.csv','input':2000,'inserted':600,'updated':600,'unchanged':500,'quarantine':300,
                    'baseline_validated_before_test':17000,'validated_after_first_run':17600,'validated_after_rerun':17600},
        'test_04': {'file':'t4.csv','input':1000,'inserted':500,'updated':300,'unchanged':100,'quarantine':100,
                    'validated_after_first_run':18100,'validated_after_rerun':18100},
    }
    def test(self, k): return dict(self.specs[k])
    def sample(self, *a, **kw): return []


class Snap:
    def __init__(self, state): self.state = state
    def to_dict(self): return dict(self.state)


class FakeMongo:
    last = None
    def __init__(self, *a, **kw):
        self.state={'raw':0,'validated':0,'quarantine':0,'duplicate_business_keys':0,'business_key':'order_id'}
        FakeMongo.last=self
    def ping(self): return True
    def drop_database(self): self.state.update(raw=0,validated=0,quarantine=0,duplicate_business_keys=0)
    def clear_documents(self): self.drop_database()
    def snapshot(self): return Snap(self.state)
    def distinct_engine_values(self): return [getattr(self,'engine','python_batch')]
    def has_unique_business_index(self): return True,['uniq_order_id']
    def has_json_schema_validator(self): return True
    def sample_docs(self,*a,**kw): return [{'error_codes':['X']}] * 10
    def find_validated(self,*a,**kw): return None
    def _existing_business_key(self): return 'order_id'
    def close(self): pass


def test_orchestrator_executes_all_core_cases(monkeypatch, tmp_path):
    for name in ['t1.csv','t2.csv','t3.csv','t4.csv']:
        (tmp_path/name).write_text('x',encoding='utf-8')
    monkeypatch.setattr(tm, 'MongoChecker', FakeMongo)
    monkeypatch.setattr(tm, '_run_setup', lambda *a, **k: None)
    monkeypatch.setattr(tm, 'find_latest_metrics', lambda *a, **k: ({}, None))
    monkeypatch.setattr(tm, 'detect_engine', lambda out,err,metrics,mongo_values: (mongo_values[0], [mongo_values[0]]))

    def fake_run(plan, repo, file, threshold, timeout, venv, db_name=None):
        m=FakeMongo.last
        if file.name=='t1.csv':
            if m.state['validated']==0:
                m.state.update(raw=20000,validated=17000,quarantine=3000); m.engine='python_batch'
            else:
                m.state.update(raw=m.state['raw']+20000,validated=17000,quarantine=m.state['quarantine']+3000); m.engine='python_batch'
        elif file.name=='t2.csv':
            m.state.update(raw=100000,validated=100000,quarantine=0); m.engine='pyspark'
        elif file.name=='t3.csv':
            m.state.update(raw=m.state['raw']+2000,validated=17600,quarantine=m.state['quarantine']+300); m.engine='python_batch'
        return f'python main.py {file}', CommandResult('x',0,'','',.1), {}, None
    monkeypatch.setattr(tm, '_run_ingest', fake_run)

    plan=SimpleNamespace(ingest_command='python main.py {file}', database_name='db', mongo_uri='mongodb://x',
                         collections={'raw':'orders_raw','validated':'orders_validated','quarantine':'orders_quarantine'},
                         business_key='order_id', threshold_mb=20, threshold_configurable=True, setup_command=None,
                         spark_master=None)
    result=tm.run_midterm_runtime(plan,tmp_path,tmp_path,FakeOracle(),timeout=5)
    assert result['status'] in {'PASS','COMPLETED_WITH_REVIEW','COMPLETED_WITH_FAILURES'}
    names=[c['name'] for c in result['cases']]
    assert names==['batch_pipeline','spark_pipeline','upsert_baseline','upsert_first','upsert_rerun']
    assert result['assertions']['batch.raw_count']['verdict']=='PASS'
    assert result['assertions']['idempotency.validated_stable']['verdict']=='PASS'
