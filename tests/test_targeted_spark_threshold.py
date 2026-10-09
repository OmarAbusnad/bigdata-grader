from grader.sandbox_runtime import _format_threshold_env

def test_integer_threshold_does_not_break_student_int_env_parser():
    assert _format_threshold_env(20.0) == "20"
    assert int(_format_threshold_env(20.0)) == 20
    assert _format_threshold_env(200.0) == "200"
    assert _format_threshold_env(20.25) == "20.25"
