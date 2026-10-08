from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "project_execution_contract.v1"


def _read(path: Path, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")[:limit]
    except Exception:
        return ""


def _readmes(repo: Path) -> list[Path]:
    return [
        p for p in sorted(repo.rglob("*"))
        if p.is_file()
        and p.name.lower() == "readme.md"
        and not any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in p.parts)
    ]


def _safe_command(line: str) -> str | None:
    line = re.sub(r"^\$\s*", "", line.strip().strip("`").strip())
    if not re.match(r"^(?:python(?:3)?|py)\s+", line, re.I):
        return None
    if any(x in line for x in ("&&", "||", ";", "|", "`", "$(")):
        return None
    if re.search(r"\b(?:pip|curl|wget|npm|apt|yum|dnf)\b", line, re.I):
        return None
    try:
        shlex.split(line, posix=False)
    except Exception:
        return None
    return line


def _classify_command(command: str) -> str | None:
    low = command.lower()
    if re.search(r"\b(?:indexes?|create[-_]?indexes?)\b", low):
        return "indexes"
    if re.search(r"\bexplain\b", low):
        return "explain"
    if re.search(r"refresh[-_ ]?full|full[-_ ]?refresh|--bootstrap|\bbootstrap\b|materialized_views\.py\s+build", low):
        return "mv_init"
    if re.search(r"refresh[-_ ]?incremental|materialized_views\.py\s+refresh", low):
        return "mv_incremental"
    if re.search(r"mongo_setup|setup_mongo|init_db|init_project|setup\.py", low):
        return "setup"
    if re.search(r"scheduler\.py.*--run|\bjobs?\b.*\brun\b", low):
        return "job_direct"
    if re.search(r"--(?:file|csv|input)(?:\s|=)|\b(?:huge|sample|demo|example)\b", low):
        return "ingest_or_dataset"
    return None


def _nearest_cwd(repo: Path, readme: Path) -> str:
    parent = readme.parent
    try:
        rel = parent.resolve().relative_to(repo.resolve()).as_posix()
    except Exception:
        return "."
    return rel if rel and rel != "." else "."


def build_project_execution_contract(
    repo: Path,
    execution_plan,
    final_plan: dict[str, Any],
) -> dict[str, Any]:
    """Build one immutable, project-specific adapter without changing grader core rules.

    The contract records how this repository should be invoked. It never changes
    rubric requirements and never substitutes a different dataset.
    """
    commands: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for readme in _readmes(repo):
        cwd = _nearest_cwd(repo, readme)
        for raw in _read(readme).splitlines():
            cmd = _safe_command(raw)
            if not cmd:
                continue
            kind = _classify_command(cmd)
            if not kind:
                continue
            key = (kind, cmd, cwd)
            if key in seen:
                continue
            seen.add(key)
            commands.append({
                "kind": kind,
                "command": cmd,
                "working_directory": cwd,
                "source": readme.relative_to(repo).as_posix(),
                "evidence": f"Exact documented command in {readme.relative_to(repo).as_posix()}",
            })

    return {
        "version": CONTRACT_VERSION,
        "source": "deterministic_repository_adapter",
        "midterm": {
            "setup_command": getattr(execution_plan, "setup_command", None),
            "ingest_command": getattr(execution_plan, "ingest_command", None),
            "ingest_stdin": getattr(execution_plan, "ingest_stdin", None),
            "entrypoint": getattr(execution_plan, "entrypoint", None),
            "database_name": getattr(execution_plan, "database_name", None),
            "collections": dict(getattr(execution_plan, "collections", {}) or {}),
        },
        "final": {
            "api_target": final_plan.get("api_target"),
            "api_file": final_plan.get("api_file"),
            "readme_start_command": final_plan.get("readme_start_command"),
        },
        "documented_commands": commands,
        "safety": {
            "frozen_dataset_only": True,
            "allow_alternate_dataset": False,
            "allow_endpoint_bypass": False,
            "allow_student_code_changes": False,
            "allow_package_install_repair": False,
        },
    }


def deterministic_repair_commands(
    contract: dict[str, Any],
    unresolved_assertions: list[dict[str, Any]],
    *,
    max_commands: int = 3,
) -> list[dict[str, Any]]:
    """Return only exact documented precondition commands relevant to unresolved checks.

    Direct job execution and ingest/data commands are intentionally forbidden:
    required API behavior must be tested through the API, and the frozen dataset
    must never be replaced.
    """
    keys = {
        str(a.get("key") or "")
        for a in unresolved_assertions
        if isinstance(a, dict) and a.get("verdict") in {"FAIL", "INCONCLUSIVE", "ERROR"}
    }
    wanted: set[str] = set()
    if any(k.startswith("final.indexes.") for k in keys):
        wanted.update({"indexes", "explain"})
    if any(k.startswith("final.mv.") for k in keys):
        wanted.add("mv_init")

    out: list[dict[str, Any]] = []
    for item in contract.get("documented_commands") or []:
        if item.get("kind") not in wanted:
            continue
        out.append({
            "stage": "before_phase2_retry",
            "command": item.get("command"),
            "working_directory": item.get("working_directory") or ".",
            "confidence": 1.0,
            "evidence": [item.get("evidence") or "Exact documented command"],
            "reason": f"Deterministic project adapter precondition: {item.get('kind')}",
            "source": "execution_contract",
        })
        if len(out) >= max_commands:
            break
    return out
