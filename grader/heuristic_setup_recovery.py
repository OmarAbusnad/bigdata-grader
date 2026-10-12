"""A bounded recovery when inferred setup changes student runtime behavior.

Never repairs or modifies student source, never skips documented setup, and
never turns a failed student command into PASS without a successful rerun.
"""
from pathlib import Path
import re


def allow_clean_database_retry(
    repo: Path,
    *,
    plan_source: str,
    setup_command: str | None,
    setup_succeeded: bool,
    unique_index_exists: bool,
    failed_returncode: int,
    timed_out: bool,
    error_output: str,
    data_written: bool,
) -> bool:
    if (not setup_command or not setup_succeeded or not unique_index_exists
            or not failed_returncode or timed_out or data_written
            or plan_source.strip().lower() != "heuristic"):
        return False
    if not re.search(
        r"An existing index has the same name as the requested index|IndexKeySpecsConflict",
        error_output, re.I
    ):
        return False
    # Do not override an explicit, documented setup procedure.
    normalized = re.sub(r"\s+", " ", setup_command.strip()).lower()
    setup_rel = ""
    parts = normalized.split()
    for token in parts:
        if token.endswith(".py") or token.startswith("src."):
            setup_rel = token.strip("'\"")
            break
    for name in ("README.md", "readme.md", "README.rst", "README.txt"):
        doc = repo / name
        if not doc.is_file():
            continue
        try:
            text = doc.read_text(encoding="utf-8-sig", errors="replace").lower()
        except OSError:
            return False
        if normalized in re.sub(r"\s+", " ", text):
            return False
        if setup_rel and re.search(
            r"python(?:3)?\s+(?:-m\s+)?(?:\./)?" + re.escape(setup_rel) + r"(?:\s|$)",
            text,
        ):
            return False
    return True
