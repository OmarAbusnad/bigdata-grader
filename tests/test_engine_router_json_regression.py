from grader.runtime_evidence import normalize_engine,detect_engine


def test_json_router_python_batch_remains_batch_despite_spark_reason():
    stdout='{"file_size_mb": 8.528, "engine_used": "python_batch", "reason": "8.528MB <= 20MB threshold; streaming batches avoid Spark startup overhead"}'
    engine, evidence=detect_engine(stdout,"",None,["python_batch"])
    assert engine=="python_batch"
    assert any("mongodb:engine=python_batch" in x for x in evidence)


def test_normalize_engine_first_reported_token_wins():
    assert normalize_engine('"python_batch", "reason": "avoid Spark startup"')=="python_batch"
    assert normalize_engine('pyspark because 43MB')=="pyspark"
    assert normalize_engine('python_batch')=="python_batch"
    assert normalize_engine('random text') is None
