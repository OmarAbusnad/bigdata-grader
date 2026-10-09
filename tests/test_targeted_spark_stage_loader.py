def test_targeted_spark_runner_imports_without_execution():
    import targeted_spark_only
    assert callable(targeted_spark_only.main)
