"""Regression checks for runtime/classpath blockers; no student code is executed."""
from grader.sandbox_runtime import _unproven_spark_execution_precondition


def repo_with(tmp_path, *, requirements="pyspark==4.2.0", source='df.write.format("mongodb").save()'):
    (tmp_path / "requirements.txt").write_text(requirements, encoding="utf-8")
    (tmp_path / "spark_loader.py").write_text(source, encoding="utf-8")
    return tmp_path


def log(stderr, *, returncode=1, timed_out=False):
    return {"returncode": returncode, "timed_out": timed_out,
            "stdout_tail": "", "stderr_tail": stderr}


def test_explicit_windows_only_java_path_does_not_fail_unrun_spark_rows(tmp_path):
    repo = repo_with(tmp_path)
    code, evidence = _unproven_spark_execution_precondition(
        repo, log(r"RuntimeError: Configured Java was not found at C:\Program Files\jdk-21\bin\java.exe"))
    assert code == "SPARK_PLATFORM_JAVA_CONFIGURATION_UNPROVEN"
    assert evidence


def test_missing_mongodb_spark_provider_is_unproven_when_dependency_not_declared(tmp_path):
    repo = repo_with(tmp_path)
    code, evidence = _unproven_spark_execution_precondition(
        repo, log("Caused by: java.lang.ClassNotFoundException: mongodb.DefaultSource"))
    assert code == "SPARK_MONGODB_PROVIDER_UNPROVEN"
    assert evidence


def test_proven_source_incompatibility_is_not_excused_by_missing_provider(tmp_path):
    repo = repo_with(tmp_path, requirements="pyspark==3.4.1",
                     source='PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1"\ndf.write.format("mongodb").save()')
    code, evidence = _unproven_spark_execution_precondition(
        repo, log("java.lang.ClassNotFoundException: mongodb.DefaultSource"))
    assert code is None and evidence == []


def test_success_timeout_and_arbitrary_student_failure_not_reclassified(tmp_path):
    repo = repo_with(tmp_path)
    java = r"Configured Java was not found at C:\Program Files\jdk-21\bin\java.exe"
    for runtime in [log(java, returncode=0), log(java, timed_out=True),
                    log("ValueError: invalid business record")]:
        assert _unproven_spark_execution_precondition(repo, runtime) == (None, [])
