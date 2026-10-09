import pytest
from grader.spark_recovery_overlay import spark_recovery_overlay


def fake_original():
    return {
        "project_id":"P05", "commit_sha":"frozen-sha",
        "runtime":{"assertions":{
            "batch_pipeline.command":{"verdict":"PASS"},
            "spark_pipeline.command":{"verdict":"INCONCLUSIVE"},
            "spark_pipeline.engine":{"verdict":"INCONCLUSIVE"},
            "spark.raw_count":{"verdict":"INCONCLUSIVE","expected":100000},
            "spark.validated_count":{"verdict":"INCONCLUSIVE","expected":100000},
            "spark.quarantine_count":{"verdict":"INCONCLUSIVE","expected":0},
            "spark.duplicates":{"verdict":"INCONCLUSIVE","expected":0},
        }}
    }


def fake_proof():
    return {
        "project_id":"P05", "source_run":37874152827,
        "frozen_commit":"frozen-sha",
        "passed_tests_reexecuted":0,"other_tests_reexecuted":0,
        "official_grade_changed":False,
        "only_test":"spark_pipeline.command",
        "verdict":"PASS", "run":{"returncode":0,"timed_out":False},
        "engine":"pyspark",
        "after":{"raw":100000,"validated":100000,"quarantine":0,
                 "duplicate_business_keys":0}
    }


def test_p05_six_frozen_assertions_become_pass_and_old_passes_remain():
    old=fake_original()
    overlay=spark_recovery_overlay(old,fake_proof(),proof_run_id=38003977105)
    assert overlay["recovery_success"] is True
    assert set(overlay["overrides"]) == {
        "spark_pipeline.command","spark_pipeline.engine","spark.raw_count",
        "spark.validated_count","spark.quarantine_count","spark.duplicates",
    }
    assert overlay["untouched_passes"] == ["batch_pipeline.command"]
    assert old["runtime"]["assertions"]["spark_pipeline.command"]["verdict"]=="INCONCLUSIVE"
    assert overlay["other_tests_reexecuted"]==0


def test_fail_or_nonmatching_count_never_promoted():
    x=fake_proof()
    x["after"]["validated"]=1000
    overlay=spark_recovery_overlay(fake_original(),x,proof_run_id=1)
    assert overlay["overrides"]["spark.validated_count"]["to"] == "FAIL"
    x["run"]["returncode"]=1
    assert not spark_recovery_overlay(fake_original(),x,proof_run_id=1)["overrides"]


def test_unrelated_or_replayed_success_rejected():
    original=fake_original()
    proof=fake_proof()
    proof["other_tests_reexecuted"]=1
    with pytest.raises(ValueError):
        spark_recovery_overlay(original,proof,proof_run_id=1)
    proof=fake_proof()
    proof["frozen_commit"]="not-frozen"
    with pytest.raises(ValueError):
        spark_recovery_overlay(original,proof,proof_run_id=1)
    original["runtime"]["assertions"]["spark_pipeline.command"]["verdict"]="PASS"
    with pytest.raises(ValueError):
        spark_recovery_overlay(original,fake_proof(),proof_run_id=1)

def test_clean_spark_input_all_quarantined_is_real_functional_failure():
    old=fake_original()
    proof=fake_proof()
    proof["after"]["validated"]=0
    proof["after"]["quarantine"]=100000
    result=spark_recovery_overlay(old,proof,proof_run_id=38004329576)
    assert result["overrides"]["spark_pipeline.command"]["to"]=="PASS"
    assert result["overrides"]["spark.raw_count"]["to"]=="PASS"
    assert result["overrides"]["spark.validated_count"]["to"]=="FAIL"
    assert result["overrides"]["spark.quarantine_count"]["to"]=="FAIL"
    assert result["overrides"]["spark.duplicates"]["to"]=="PASS"
    assert old["runtime"]["assertions"]["spark.validated_count"]["verdict"]=="INCONCLUSIVE"
