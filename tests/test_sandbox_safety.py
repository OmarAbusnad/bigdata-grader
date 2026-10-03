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
