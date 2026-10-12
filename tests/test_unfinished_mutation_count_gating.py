from types import SimpleNamespace
from grader.sandbox_runtime import _guard_unfinished_mutation_case


def assertion(key, verdict):
    return SimpleNamespace(key=key, verdict=verdict, note=None, evidence=[])


def make_case(returncode, timed_out=False, stdout=""):
    a = [assertion("upsert_first.command","FAIL"),
         assertion("upsert.final_validated","FAIL"),
         assertion("upsert.insert_samples","FAIL")]
    return SimpleNamespace(
        runtime_log={"returncode":returncode, "timed_out":timed_out,
                     "stdout_tail":stdout,"stderr_tail":""},
        assertions=a)


def test_failed_upsert_keeps_root_command_fail_and_blocks_count_only():
    case=make_case(1)
    assert _guard_unfinished_mutation_case(case)==1
    assert [a.verdict for a in case.assertions]==["FAIL","INCONCLUSIVE","FAIL"]
    assert "partial" in case.assertions[1].note


def test_successful_upsert_still_graded_by_oracle():
    case=make_case(0)
    assert _guard_unfinished_mutation_case(case)==0
    assert case.assertions[1].verdict=="FAIL"


def test_confirmed_completion_before_timeout_preserves_count_proof():
    case=make_case(124, timed_out=True,
                   stdout="Pipeline completed successfully; server serving")
    assert _guard_unfinished_mutation_case(case)==0
    assert case.assertions[1].verdict=="FAIL"


def test_incomplete_incremental_rerun_count_is_not_independent_fail():
    case=make_case(124,timed_out=True)
    case.assertions=[assertion("incremental_rerun.command","FAIL"),
                     assertion("incremental.rerun_validated_stable","FAIL")]
    assert _guard_unfinished_mutation_case(case)==1
    assert [a.verdict for a in case.assertions]==["FAIL","INCONCLUSIVE"]
