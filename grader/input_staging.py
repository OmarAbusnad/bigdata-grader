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


_PROCESSED_PATTERNS = (
    r"(?:input|file|source|csv|dataset)[ _-]*(?:file|path|name)?\s*[:=]\s*['\"]?([^\s'\"]+\.csv)\b",
    r"(?:reading|loading|processing|read|loaded|processed)\s+(?:file\s+)?['\"]?([^\s'\"]+\.csv)\b",
)


def processed_csv_path(stdout: str, hidden_file_rel: str) -> str | None:
    """Repo-relative CSV the program says it processed, when it is not the supplied test file."""
    hidden_name = posixpath.basename(hidden_file_rel or "").lower()
    for pattern in _PROCESSED_PATTERNS:
        for m in re.finditer(pattern, stdout or "", flags=re.I):
            raw = m.group(1).strip().replace("\\", "/")
            if raw.startswith("/grader-tests/") or posixpath.basename(raw).lower() == hidden_name:
                continue
            if raw.startswith("/"):
                if not raw.startswith("/workspace/"):
                    continue
                raw = raw[len("/workspace/"):]
            norm = posixpath.normpath(raw)
            if norm.startswith("..") or norm == "." or norm.startswith("/") or "\x00" in norm:
                continue
            if not norm.lower().endswith(".csv") or any(part.startswith(".") for part in norm.split("/")):
                continue
            return norm
    return None


def plan_processed_input_retry(stdout: str, snapshot: dict, *, expected_rows: int, hidden_file_rel: str,
                               fresh: bool, already_staged: bool) -> str | None:
    """A run that succeeded but processed a different CSV than the supplied one.

    Evidence required: the program itself printed the CSV path it processed, that file is not the
    supplied test file, and the raw collection does not hold the supplied file's row count.
    """
    if already_staged or not fresh or expected_rows <= 0:
        return None
    raw = int((snapshot or {}).get("raw") or 0)
    if raw <= 0 or raw == expected_rows:
        return None
    return processed_csv_path(stdout, hidden_file_rel)


_HINT_FLAG = re.compile(
    r"(?:use|add|pass|run with|rerun with|re-run with|specify)\s+(?:the\s+)?(--[a-z][a-z0-9-]*)\b[^\n]{0,60}"
    r"(?:to|for)\s+(?:actually\s+)?(?:run|execute|write|load|apply|perform|start|process)",
    re.I,
)


def plan_flag_retry(stdout: str, cmd: str, snapshot: dict, *, fresh: bool) -> str | None:
    """A check-only run (nothing written) that tells the user which flag really runs the pipeline."""
    if not fresh or any(int((snapshot or {}).get(k) or 0) for k in ("raw", "validated", "quarantine")):
        return None
    m = _HINT_FLAG.search(stdout or "")
    if not m:
        return None
    flag = m.group(1)
    if flag in (cmd or "").split():
        return None
    return f"{cmd} {flag}"
