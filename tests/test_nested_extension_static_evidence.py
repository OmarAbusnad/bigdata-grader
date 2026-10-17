"""Regression for nested Phase-2 documentation and declared Python dependencies."""
from grader.static_checks import static_checks


def test_nested_final_extension_counts_as_real_evidence(tmp_path):
    base = tmp_path
    (base / "src").mkdir()
    (base / "src" / "main.py").write_text("print('batch')", encoding="utf-8")
    ext = base / "final_extension"
    ext.mkdir()
    (ext / "README.md").write_text("# Actual final extension documentation", encoding="utf-8")
    (ext / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    tests = ext / "tests"
    tests.mkdir()
    (tests / "test_pipeline.py").write_text("def test_pipeline(): assert True\n", encoding="utf-8")
    result = static_checks(base)
    assert result["has_readme"] is True
    assert result["has_requirements"] is True
    assert result["has_tests"] is True
    assert "final_extension/README.md" in result["_evidence"]["has_readme"]
    assert "final_extension/requirements.txt" in result["_evidence"]["has_requirements"]


def test_unrelated_subdirectory_does_not_count_as_a_declared_manifest(tmp_path):
    unrelated = tmp_path / "misc"
    unrelated.mkdir()
    (unrelated / "README.md").write_text("Unrelated", encoding="utf-8")
    (unrelated / "requirements.txt").write_text("any", encoding="utf-8")
    result = static_checks(tmp_path)
    assert result["has_readme"] is False
    assert result["has_requirements"] is False
