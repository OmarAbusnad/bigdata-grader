from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


class RepositoryError(RuntimeError):
    pass


def _git_base(repo_url: str) -> list[str]:
    """Return git command prefix without leaking a token in the clone URL."""
    token = os.getenv("STUDENT_REPOS_TOKEN", "").strip()
    host = (urlparse(repo_url).hostname or "").lower()
    if token and host == "github.com":
        return ["git", "-c", f"http.extraHeader=AUTHORIZATION: bearer {token}"]
    return ["git"]


def clone_repository(repo_url: str, destination: Path, ref: str | None = None, timeout: int = 180) -> Path:
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    base = _git_base(repo_url)
    try:
        subprocess.run(base + ["clone", "--depth", "1", repo_url, str(destination)], check=True, timeout=timeout)
        if ref:
            subprocess.run(base + ["fetch", "--depth", "1", "origin", ref], cwd=destination, check=True, timeout=timeout)
            subprocess.run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=destination, check=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RepositoryError(f"Failed to clone/fetch repository: {repo_url}: {type(exc).__name__}") from exc
    return destination


def current_commit(repo_path: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None
