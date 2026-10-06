from types import SimpleNamespace
from pathlib import Path
from grader.sandbox import SandboxConfig, DockerSandbox


def test_sandbox_defaults_are_restricted(tmp_path: Path):
    repo=tmp_path/'repo'; repo.mkdir()
    hidden=tmp_path/'hidden'; hidden.mkdir()
    sb=DockerSandbox(tmp_path,'P01',repo,hidden,SandboxConfig())
    assert sb.config.network_profile == 'isolated'
    assert sb.config.no_new_privileges is True
    assert sb.config.pids_limit <= 512
    assert sb.config.cpus <= 2.0


def test_run_student_preserves_project_virtualenv_path(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    hidden = tmp_path / "hidden"; hidden.mkdir()
    sb = DockerSandbox(tmp_path, "P01", repo, hidden, SandboxConfig())
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    sb._run = fake_run
    result = sb.run_student("python -c 'print(1)'")
    assert result["returncode"] == 0
    args = captured["args"]
    idx = args.index(sb.image_name)
    assert args[idx + 1: idx + 3] == ["bash", "-c"]
    assert "-lc" not in args
