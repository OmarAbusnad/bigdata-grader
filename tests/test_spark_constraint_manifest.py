"""The grader must not override a pinned PySpark requirement in the actual pip manifest."""
from grader.spark_dependency_audit import check_submission, scala_compat_constraint
from grader.sandbox import _guard_spark_constraint


def test_frozen_style_pyspark4_pin_is_never_downgraded(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "dnspython==2.8.0\npy4j==0.10.9.9\npymongo==4.17.0\npyspark==4.2.0\n",
        encoding="utf-8",
    )
    (tmp_path / "spark_writer.py").write_text(
        'PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"\n'
        'df.write.format("mongodb").save()\n',
        encoding="utf-8",
    )
    audit = check_submission(tmp_path)
    assert audit["pyspark_constraints"]
    assert scala_compat_constraint(audit) is None
    assert _guard_spark_constraint("pyspark<4", tmp_path / "requirements.txt") is None


def test_open_ended_spark3_can_still_receive_scala212_guard(tmp_path):
    (tmp_path / "requirements.txt").write_text("pyspark>=3.5.1\n", encoding="utf-8")
    (tmp_path / "spark_writer.py").write_text(
        'PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"\n',
        encoding="utf-8",
    )
    candidate = scala_compat_constraint(check_submission(tmp_path))
    assert candidate == "pyspark<4"
    assert _guard_spark_constraint(candidate, tmp_path / "requirements.txt") == "pyspark<4"


def test_missing_or_pyspark4_only_specs_never_force_spark3():
    declared = ["org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"]
    assert scala_compat_constraint({"declared_coordinates": declared,
                                    "pyspark_constraints": []}) is None
    assert scala_compat_constraint({"declared_coordinates": declared,
                                    "pyspark_constraints": [{"operator": ">=", "major": 4}]}) is None


def test_utf8_bom_manifest_and_unreadable_manifest_do_not_override_pin(tmp_path):
    manifest = tmp_path / "requirements.txt"
    manifest.write_bytes(b"\xef\xbb\xbf" + "pytest==9.1.1\r\npyspark==4.2.0\r\n".encode())
    assert _guard_spark_constraint("pyspark<4", manifest) is None
    assert _guard_spark_constraint("pyspark<4", tmp_path / "missing.txt") == "pyspark<4"
