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
    for runtime in [log(java, returncode=0), log("ValueError: invalid business record")]:
        assert _unproven_spark_execution_precondition(repo, runtime) == (None, [])


def test_timeout_blocks_downstream_counts_without_proving_student_error(tmp_path):
    repo = repo_with(tmp_path)
    code, evidence = _unproven_spark_execution_precondition(
        repo, log("Spark stage in progress", returncode=124, timed_out=True))
    assert code == "SPARK_TIMEOUT_UNPROVEN" and evidence


def test_cross_platform_launcher_signatures_trigger_review(tmp_path):
    repo = repo_with(tmp_path)
    inputs = [
        ("Project Java 17 was not found at /opt/student-venv/Library/bin/java.exe",
         "SPARK_PLATFORM_JAVA_CONFIGURATION_UNPROVEN"),
        (r"JAVA_HOME does not contain bin\java.exe: /usr/lib/jvm/java-17-openjdk-amd64",
         "SPARK_PLATFORM_JAVA_CONFIGURATION_UNPROVEN"),
        ("Permission denied: '/opt/student-venv/bin/spark-submit.cmd'",
         "SPARK_PLATFORM_WINDOWS_EXECUTABLE_UNPROVEN"),
        ('java.io.IOException: Cannot run program "python.exe": error=2',
         "SPARK_PLATFORM_WINDOWS_EXECUTABLE_UNPROVEN"),
        ("RuntimeError: Ivy jar cache not found: /tmp/student-home/.ivy2.5.2/jars",
         "SPARK_CONNECTOR_CACHE_PATH_UNPROVEN"),
    ]
    for message, expected in inputs:
        found, evidence = _unproven_spark_execution_precondition(repo, log(message))
        assert found == expected and evidence


def test_actual_python_logic_failure_remains_student_candidate(tmp_path):
    repo = repo_with(tmp_path)
    code, evidence = _unproven_spark_execution_precondition(
        repo, log("TypeError: 'NoneType' object is not iterable"))
    assert code is None and evidence == []
