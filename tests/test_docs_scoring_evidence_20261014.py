from grader.scoring import derive_midterm_capabilities, load_rubric, score_boolean_checks


def test_docs_without_grader_static_evidence_are_unscored_not_student_fail():
    runtime = {"assertions": {"batch_pipeline.engine": {"verdict": "PASS"}}}
    assert derive_midterm_capabilities(runtime)["code_tests_docs"] is None
    assert derive_midterm_capabilities(runtime, {"has_readme": True})["code_tests_docs"] is None


def test_docs_supported_absence_is_distinct_from_missing_evidence():
    runtime = {"assertions": {"batch_pipeline.engine": {"verdict": "PASS"}}}
    vals = {"has_readme": True, "has_requirements": True, "has_tests": False}
    assert derive_midterm_capabilities(runtime, vals)["code_tests_docs"] == 2 / 3


def test_current_official_rubrics_active_and_missing_values_not_zero():
    midterm = load_rubric("rubrics/midterm_18.json")
    final = load_rubric("rubrics/final_7.json")
    assert midterm["status"] == "ACTIVE" and midterm["total"] == 18
    assert final["status"] == "ACTIVE" and final["total"] == 7
    result = score_boolean_checks(midterm, {"code_tests_docs": None})
    row = next(x for x in result["details"] if x["key"] == "code_tests_docs")
    assert row["awarded"] is None and row["status"] == "NOT_EVALUATED"
    assert result["complete"] is False
