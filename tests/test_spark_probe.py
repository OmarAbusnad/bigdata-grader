import csv
from pathlib import Path
from grader.spark_probe import ensure_large_clean_probe


def test_dynamic_spark_probe_crosses_threshold_and_keeps_unique_ids(tmp_path):
    base=tmp_path/'base.csv'
    with base.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['order_id','customer_id','x']); w.writeheader()
        for i in range(100): w.writerow({'order_id':f'طلب-{i+1}','customer_id':f'عميل-{i+1}','x':'x'*100})
    probe, rows, reason=ensure_large_clean_probe(base,tmp_path/'gen',threshold_mb=.03,margin_mb=.01,max_mb=5)
    assert probe.stat().st_size/(1024*1024) > .03
    assert rows > 100
    ids=[]
    with probe.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f): ids.append(r['order_id'])
    assert len(ids)==len(set(ids))
