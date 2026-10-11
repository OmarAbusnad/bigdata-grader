"""Regression: frozen PySpark version pins must survive requirements encodings."""
from grader.spark_dependency_audit import check_submission, scala_compat_constraint, _read_requirement_manifest

PACKAGE = 'PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"\n'


def test_utf16_le_frozen_pyspark_pin_is_detected(tmp_path):
    (tmp_path / "requirements.txt").write_bytes(
        "pyspark==4.2.0\npymongo==4.17.0\n".encode("utf-16"))
    (tmp_path / "spark_loader.py").write_text(PACKAGE)
    assert "pyspark==4.2.0" in _read_requirement_manifest(tmp_path/"requirements.txt")
    diagnosis = check_submission(tmp_path, runtime_error="unresolved dependencies")
    assert diagnosis["pyspark_constraints"][0]["major"] == 4
    assert diagnosis["pyspark_constraints"][0]["operator"] == "=="
    assert diagnosis["owner"] == "STUDENT_CODE"
    assert scala_compat_constraint(diagnosis) is None


def test_utf16_be_and_utf8_bom_manifest_pins_preserved(tmp_path):
    manifest=tmp_path/"requirements.txt"
    manifest.write_bytes(b"\xfe\xff" + "pyspark==3.5.1\n".encode("utf-16-be"))
    assert "pyspark==3.5.1" in _read_requirement_manifest(manifest)
    manifest.write_bytes(b"\xef\xbb\xbf" + b"pyspark==4.2.0\n")
    assert "pyspark==4.2.0" in _read_requirement_manifest(manifest)


def test_unbounded_utf16_spark3_still_gets_compatibility_constraint(tmp_path):
    (tmp_path/"requirements.txt").write_bytes("pyspark>=3.5\n".encode("utf-16"))
    (tmp_path/"spark_loader.py").write_text(PACKAGE)
    result=check_submission(tmp_path)
    assert result["owner"] == "UNDETERMINED"
    assert scala_compat_constraint(result) == "pyspark<4"
