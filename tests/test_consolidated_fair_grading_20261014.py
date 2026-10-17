from pathlib import Path

from grader.runtime_evidence import detect_engine
from grader.tests_midterm import _documented_incremental_command


def test_p54_structured_batch_engine_outvotes_arabic_spark_explanation():
    stdout = (
        "حجم الملف 8.53MB <= الحد الفاصل 20MB، "
        "فالقراءة التسلسلية بدفعات كافية وأسرع من كلفة إقلاع Spark."
    )
    engine, evidence = detect_engine(
        stdout, "", None, ["python_batch"]
    )
    assert engine == "python_batch"
    assert any(x == "mongodb:engine=python_batch" for x in evidence)


def test_conflicting_structured_engines_stay_unresolved_not_false_fail():
    engine, evidence = detect_engine("Spark was mentioned", "", None, ["python_batch", "pyspark"])
    assert engine is None
    assert any("conflicting" in x for x in evidence)


def _write_p39_contract(root: Path):
    (root / "src").mkdir()
    (root / "README.md").write_text(
        "For Idempotency and Upsert use python src/main.py --file-path sample.csv --no-reset",
        encoding="utf-8",
    )
    (root / "src" / "main.py").write_text(
        "import argparse\np = argparse.ArgumentParser()\np.add_argument('--no-reset', action='store_true')\n",
        encoding="utf-8",
    )


def test_p39_documented_no_reset_is_incremental_only(tmp_path):
    _write_p39_contract(tmp_path)
    command = "python src/main.py --file-path /grader-tests/test_03.csv"
    assert _documented_incremental_command(command, tmp_path, "upsert_first").endswith(" --no-reset")
    assert _documented_incremental_command(command, tmp_path, "upsert_rerun").endswith(" --no-reset")
    assert _documented_incremental_command(command, tmp_path, "incremental_first").endswith(" --no-reset")
    assert _documented_incremental_command(command, tmp_path, "incremental_rerun").endswith(" --no-reset")
    assert _documented_incremental_command(command, tmp_path, "upsert_baseline") == command
    assert _documented_incremental_command(command, tmp_path, "batch_pipeline") == command
    assert _documented_incremental_command(command + " --no-reset", tmp_path, "upsert_first") == command + " --no-reset"


def test_no_reset_not_invented_when_readme_does_not_document_flag(tmp_path):
    _write_p39_contract(tmp_path)
    (tmp_path / "README.md").write_text("Run python src/main.py", encoding="utf-8")
    command = "python src/main.py /tmp/input.csv"
    assert _documented_incremental_command(command, tmp_path, "upsert_first") == command


def test_no_reset_not_applied_to_command_chains(tmp_path):
    _write_p39_contract(tmp_path)
    command = "python src/main.py /tmp/input.csv && echo done"
    assert _documented_incremental_command(command, tmp_path, "upsert_first") == command
