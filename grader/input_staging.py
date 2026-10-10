"""Evidence-based staging for projects that read a FIXED input path instead of the CLI argument.

Some submissions ignore the file handed to them and open e.g. ``data/orders_clean.csv``. When the
first run fails with a missing-CSV error and wrote nothing to MongoDB, the grader copies the hidden
test file to exactly that path (inside the student's own workspace) and re-runs once. Nothing is
guessed: the path comes from the student's own error message.
"""
from __future__ import annotations

import posixpath
import re
import shlex

_PATTERNS = (
    r"No such file or directory: '([^'\n]+\.csv)'",
    r'No such file or directory: "([^"\n]+\.csv)"',
    r"Path does not exist: file:(/[^\s]+\.csv)",
    r"FileNotFoundError[^\n]*?['\"]([^'\"\n]+\.csv)['\"]",
    r"(?:file|path)[^\n]{0,40}not (?:found|exist)[^\n]*?['\"]([^'\"\n]+\.csv)['\"]",
    r"(?:cannot|can't|could not) (?:find|open|read)[^\n]{0,60}?['\"]([^'\"\n]+\.csv)['\"]",
)


def missing_csv_path(text: str, *, hidden_prefix: str = "/grader-tests/") -> str | None:
    """Return a safe path (relative to the working directory) of the CSV the student tried to read."""
    for pattern in _PATTERNS:
        for m in re.finditer(pattern, text or "", flags=re.I):
            raw = m.group(1).strip().replace("\\", "/")
            if not raw or raw.startswith(hidden_prefix):
                continue
            if raw.startswith("/"):
                if not raw.startswith("/workspace/"):
                    continue
                raw = raw[len("/workspace/"):]
            norm = posixpath.normpath(raw)
            if norm.startswith("..") or norm == "." or norm.startswith("/") or "\x00" in norm:
                continue
            if not norm.lower().endswith(".csv"):
                continue
            return norm
    return None


def staged_command(cmd: str, target_rel: str, hidden_file_rel: str) -> str:
    target_dir = posixpath.dirname(target_rel)
    mkdir = f"mkdir -p {shlex.quote(target_dir)} && " if target_dir else ""
    src = shlex.quote(f"/grader-tests/{hidden_file_rel}")
    return f"{mkdir}cp {src} {shlex.quote(target_rel)} && {cmd}"


def plan_staging_retry(stderr: str, stdout: str, snapshot: dict, *, fresh: bool,
                       already_staged: bool) -> tuple[str, bool] | None:
    """Decide whether a failed first attempt may be retried with a staged input file.

    Returns (target_path, reset_database_first) or None. A retry is only allowed from a clean
    state: nothing was written, or the stage starts from a freshly reset database.
    """
    if already_staged:
        return None
    target = missing_csv_path(f"{stderr or ''}\n{stdout or ''}")
    if not target:
        return None
    wrote_nothing = not any(int((snapshot or {}).get(k) or 0) for k in ("raw", "validated", "quarantine"))
    if wrote_nothing:
        return target, False
    if fresh:
        return target, True
    return None
