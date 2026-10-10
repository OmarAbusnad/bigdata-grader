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
