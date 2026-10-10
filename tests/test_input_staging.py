from grader.input_staging import missing_csv_path, staged_command


def test_p51_style_file_not_found():
    err = "FileNotFoundError: [Errno 2] No such file or directory: 'data/orders_clean.csv'"
    assert missing_csv_path(err) == "data/orders_clean.csv"


def test_p11_style_spark_path_not_found():
    err = "AnalysisException: [PATH_NOT_FOUND] Path does not exist: file:/workspace/data/orders_huge_mixed_quality.csv. SQLSTATE: 42K03"
    assert missing_csv_path(err) == "data/orders_huge_mixed_quality.csv"


def test_rejects_traversal_system_paths_and_the_hidden_dir():
    assert missing_csv_path("No such file or directory: '../../etc/x.csv'") is None
    assert missing_csv_path("No such file or directory: '/etc/passwd.csv'") is None
    assert missing_csv_path("No such file or directory: '/grader-tests/test_01.csv'") is None
    assert missing_csv_path("nothing relevant") is None
    assert missing_csv_path("No such file or directory: 'notes.txt'") is None


def test_staged_command_copies_then_runs_and_quotes():
    cmd = staged_command("python src/main.py", "data/orders clean.csv", "test_01_small_batch_pipeline.csv")
    assert cmd.startswith("mkdir -p data && cp /grader-tests/test_01_small_batch_pipeline.csv 'data/orders clean.csv' && ")
    assert cmd.endswith("python src/main.py")


from grader.input_staging import plan_staging_retry

P11_ERR = "AnalysisException: [PATH_NOT_FOUND] Path does not exist: file:/workspace/data/orders_huge_mixed_quality.csv. SQLSTATE: 42K03"


def test_p11_loaded_raw_then_failed_is_retried_from_a_reset_database_when_fresh():
    snap = {"raw": 20000, "validated": 0, "quarantine": 0}
    assert plan_staging_retry(P11_ERR, "", snap, fresh=True, already_staged=False) == (
        "data/orders_huge_mixed_quality.csv", True)


def test_partial_write_in_a_stateful_stage_is_never_retried():
    snap = {"raw": 20000, "validated": 17000, "quarantine": 3000}
    assert plan_staging_retry(P11_ERR, "", snap, fresh=False, already_staged=False) is None


def test_nothing_written_retries_without_reset_and_only_once():
    snap = {"raw": 0, "validated": 0, "quarantine": 0}
    assert plan_staging_retry(P11_ERR, "", snap, fresh=False, already_staged=False)[1] is False
    assert plan_staging_retry(P11_ERR, "", snap, fresh=True, already_staged=True) is None
    assert plan_staging_retry("unrelated error", "", snap, fresh=True, already_staged=False) is None
