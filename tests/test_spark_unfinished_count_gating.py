"""A failed Spark command is one potential grade event, not many fabricated count failures."""
from grader.sandbox_runtime import _spark_stage_unfinished

def case(returncode=0, timed_out=False, stdout_tail="", stderr_tail=""):
    return {"returncode":returncode, "timed_out":timed_out,
            "stdout_tail":stdout_tail, "stderr_tail":stderr_tail}

def test_failed_spark_stage_makes_downstream_counts_unproven():
    assert _spark_stage_unfinished(case(returncode=1, stderr_tail="ValueError: data error"))
    assert _spark_stage_unfinished(case(returncode=1, stderr_tail="ClassNotFoundException"))
    assert _spark_stage_unfinished(case(returncode=124, timed_out=True))

def test_successful_spark_execution_is_still_graded_by_oracle_counts():
    assert not _spark_stage_unfinished(case(returncode=0))
    assert not _spark_stage_unfinished(None)

def test_pipeline_complete_before_server_timeout_remains_evaluable():
    assert not _spark_stage_unfinished(case(
        returncode=124, timed_out=True,
        stdout_tail="Pipeline completed successfully; API server still serving"))
