from grader.spark_dependency_audit import check_submission


def make_repo(tmp_path, requirements, source, jars=False):
    (tmp_path / "requirements.txt").write_text(requirements, encoding="utf-8")
    (tmp_path / "spark_loader.py").write_text(source, encoding="utf-8")
    if jars:
        (tmp_path / "jars").mkdir()
        (tmp_path / "jars" / "mongo-spark-connector_2.12-10.3.0-all.jar").write_bytes(b"sample")
    return tmp_path


BLOCKED = "org.mongodb.spark#mongo-spark-connector_2.12;10.3.0: not found; unresolved dependencies; repo1.maven.org not found"


def test_student_declared_correct_coordinate_maven_block_is_grader(tmp_path):
    repo=make_repo(tmp_path, "pyspark==3.5.1", """
PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:10.3.0"
df.write.format("mongodb").save()
""")
    result=check_submission(repo, runtime_error=BLOCKED)
    assert result["status"] == "GRADER_NETWORK_DEPENDENCY_PRECONDITION"
    assert result["owner"] == "GRADER_ENVIRONMENT"
    assert result["runtime_tests_executed"] == 0


def test_spark4_cannot_use_old_spark3_connector(tmp_path):
    repo=make_repo(tmp_path, "pyspark>=4.0.0", """
PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.13:10.4.0"
df.write.format("mongodb").save()
""")
    result=check_submission(repo, runtime_error=BLOCKED)
    assert result["owner"] == "STUDENT_CODE"
    assert "Spark 4+" in result["source_errors"][0]


def test_legacy_format_mismatch_is_student(tmp_path):
    repo=make_repo(tmp_path, "pyspark==3.4.1", """
PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1"
df.write.format("mongodb").save()
""")
    assert check_submission(repo, runtime_error=BLOCKED)["owner"]=="STUDENT_CODE"


def test_legacy_connector_and_mongo_format_not_auto_failed(tmp_path):
    repo=make_repo(tmp_path, "pyspark==3.4.1", """
PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1"
df.write.format("mongo").save()
""")
    assert check_submission(repo, runtime_error=BLOCKED)["owner"]=="GRADER_ENVIRONMENT"


def test_undeclared_connector_not_assumed_student_from_maven_error(tmp_path):
    repo=make_repo(tmp_path, "pyspark>=3.5.0", 'df.write.format("mongodb").save()')
    assert check_submission(repo, runtime_error=BLOCKED)["owner"]=="UNPROVEN"


def test_checked_in_jar_needs_path_verification(tmp_path):
    repo=make_repo(tmp_path, "pyspark==3.5.1", "from pyspark.sql import SparkSession", jars=True)
    assert check_submission(repo, runtime_error=BLOCKED)["status"]=="MAVEN_REQUEST_DESPITE_BUNDLED_JAR"


def test_connector_11_is_not_published_for_scala_212(tmp_path):
    repo=make_repo(tmp_path, "pyspark>=3.5.0", """
PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:11.1.0"
df.write.format("mongodb").save()
""")
    result=check_submission(repo, runtime_error=BLOCKED)
    assert result["owner"]=="STUDENT_CODE"
    assert any("Scala 2.13" in reason for reason in result["source_errors"])


def test_pinned_spark3_rejects_connector11(tmp_path):
    repo=make_repo(tmp_path, "pyspark==3.5.1", """
PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.13:11.1.0"
df.write.format("mongodb").save()
""")
    assert check_submission(repo, runtime_error=BLOCKED)["owner"]=="STUDENT_CODE"
