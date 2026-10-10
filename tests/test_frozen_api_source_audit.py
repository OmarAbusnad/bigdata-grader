from grader.frozen_api_source_audit import inspect_fastapi


def test_frozen_midterm_without_fastapi_is_missing_api(tmp_path):
    (tmp_path/"src").mkdir()
    (tmp_path/"src"/"main.py").write_text("def run():\n    print('midterm')\n")
    proof=inspect_fastapi(tmp_path)
    assert proof["status"]=="FASTAPI_ABSENT_IN_SUBMITTED_PYTHON_SOURCE"
    assert proof["student_code_executed"] is False


def test_real_fastapi_entrypoint_is_detected(tmp_path):
    (tmp_path/"src").mkdir()
    (tmp_path/"src"/"api.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n")
    proof=inspect_fastapi(tmp_path)
    assert proof["status"]=="FASTAPI_SOURCE_EXISTS_REVIEW_GRADER_DISCOVERY"
    assert proof["matches"][0]["path"]=="src/api.py"


def test_unparseable_files_cannot_prove_missing_api(tmp_path):
    (tmp_path/"main.py").write_text("def broken(:\n")
    proof=inspect_fastapi(tmp_path)
    assert proof["status"]=="INCONCLUSIVE_PARSE_ERRORS"
