from __future__ import annotations
import os
import shlex
import subprocess
import time
from pathlib import Path
from .models import CommandResult


def _quote(value: object) -> str:
    s = str(value)
    if os.name == 'nt':
        return subprocess.list2cmdline([s])
    return shlex.quote(s)


def render_command(template: str, **values) -> str:
    safe = {k: _quote(v) for k, v in values.items()}
    return template.format(**safe)


def _venv_bin(venv: Path) -> Path:
    return venv / ('Scripts' if os.name == 'nt' else 'bin')


def build_env(extra: dict | None = None, venv: str | Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if venv:
        vb = _venv_bin(Path(venv))
        env['VIRTUAL_ENV'] = str(Path(venv))
        env['PATH'] = str(vb) + os.pathsep + env.get('PATH', '')
    if extra:
        env.update({k: str(v) for k, v in extra.items() if v is not None})
    return env


def run_command(command: str, cwd: str | Path, timeout: int = 600, env: dict | None = None,
                venv: str | Path | None = None) -> CommandResult:
    started = time.perf_counter()
    merged_env = build_env(env, venv=venv)
    try:
        p = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=merged_env,
        )
        return CommandResult(command, p.returncode, p.stdout or '', p.stderr or '', time.perf_counter() - started)
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
        stderr = e.stderr.decode(errors='replace') if isinstance(e.stderr, bytes) else (e.stderr or '')
        return CommandResult(command, 124, stdout, stderr, time.perf_counter() - started, True)


def prepare_virtualenv(repo: str | Path, install_command: str, venv_dir: str | Path | None = None,
                       timeout: int = 900) -> dict:
    repo = Path(repo)
    venv = Path(venv_dir) if venv_dir else repo / '.grader_venv'
    create = run_command(f'"{os.sys.executable}" -m venv "{venv}"', repo, timeout=180)
    if not create.ok:
        return {'ok': False, 'stage': 'create_venv', 'venv': str(venv), 'result': create.to_dict()}
    pip_upgrade = run_command('python -m pip install --upgrade pip', repo, timeout=300, venv=venv)
    install = None
    if install_command:
        install = run_command(install_command, repo, timeout=timeout, venv=venv)
        if not install.ok:
            return {
                'ok': False, 'stage': 'install', 'venv': str(venv),
                'pip_upgrade': pip_upgrade.to_dict(), 'result': install.to_dict(),
            }
    return {
        'ok': True, 'stage': 'ready', 'venv': str(venv),
        'pip_upgrade': pip_upgrade.to_dict(),
        'install': install.to_dict() if install else None,
    }
