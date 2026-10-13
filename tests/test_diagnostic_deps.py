from pathlib import Path

import pytest

from grader.sandbox import DockerSandbox, SandboxError, _diagnostic_packages


@pytest.mark.parametrize("project_id,package", [
    ("P01", "psutil==6.1.1"),
    ("P02", "psutil==6.1.1"),
    ("P67", "tqdm==4.67.1"),
])
def test_grader_only_diagnostic_dependency(project_id, package, monkeypatch, tmp_path):
    monkeypatch.setenv("GRADER_DIAGNOSTIC_PROJECT_ID", project_id)
    monkeypatch.setenv("GRADER_DIAGNOSTIC_EXTRAS", package)
    repo = tmp_path / "student"
    repo.mkdir()
    (repo / "requirements.txt").write_text("pymongo>=4.6\n", encoding="utf-8")
    sandbox = DockerSandbox(tmp_path, project_id, repo, tmp_path / "hidden")
    sandbox.prepare_build_context()
    dockerfile = (sandbox.build_context / ".grader.Dockerfile").read_text()
    assert f"RUN /opt/student-venv/bin/pip install --no-cache-dir {package}" in dockerfile
    assert package not in (repo / "requirements.txt").read_text()
    assert package not in (sandbox.build_context / "requirements.txt").read_text()


def test_diagnostic_dependency_disallowed_for_other_student(monkeypatch):
    monkeypatch.setenv("GRADER_DIAGNOSTIC_PROJECT_ID", "P68")
    monkeypatch.setenv("GRADER_DIAGNOSTIC_EXTRAS", "psutil==6.1.1")
    with pytest.raises(SandboxError, match="not explicitly approved"):
        _diagnostic_packages("P68")


def test_diagnostic_dependency_project_mismatch_rejected(monkeypatch):
    monkeypatch.setenv("GRADER_DIAGNOSTIC_PROJECT_ID", "P02")
    monkeypatch.setenv("GRADER_DIAGNOSTIC_EXTRAS", "psutil==6.1.1")
    with pytest.raises(SandboxError, match="not explicitly approved"):
        _diagnostic_packages("P01")


def test_diagnostic_dependency_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GRADER_DIAGNOSTIC_EXTRAS", raising=False)
    monkeypatch.delenv("GRADER_DIAGNOSTIC_PROJECT_ID", raising=False)
    assert _diagnostic_packages("P01") == ()


@pytest.mark.parametrize("project_id,package", [
    ("P01", "psutil==6.1.1"),
    ("P02", "psutil==6.1.1"),
    ("P67", "tqdm==4.67.1"),
])
def test_unified_sandbox_receives_diagnostic_dependency(project_id, package, monkeypatch, tmp_path):
    monkeypatch.setenv("GRADER_DIAGNOSTIC_PROJECT_ID", project_id)
    monkeypatch.setenv("GRADER_DIAGNOSTIC_EXTRAS", package)
    repo = tmp_path / "student"
    repo.mkdir()
    (repo / "requirements.txt").write_text("pymongo>=4.6\n")
    sandbox = DockerSandbox(tmp_path, project_id + "-unified", repo, tmp_path / "hidden")
    sandbox.prepare_build_context()
    dockerfile = (sandbox.build_context / ".grader.Dockerfile").read_text()
    assert f"RUN /opt/student-venv/bin/pip install --no-cache-dir {package}" in dockerfile


def test_suffixed_fake_project_does_not_bypass_allowlist(monkeypatch):
    monkeypatch.setenv("GRADER_DIAGNOSTIC_PROJECT_ID", "P01")
    monkeypatch.setenv("GRADER_DIAGNOSTIC_EXTRAS", "psutil==6.1.1")
    with pytest.raises(SandboxError, match="not explicitly approved"):
        _diagnostic_packages("P01-extra-unified")
