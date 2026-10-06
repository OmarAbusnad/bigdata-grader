from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _read(path: Path, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")[:limit]
    except Exception:
        return ""


def _iter_python(repo: Path):
    for path in sorted(repo.rglob("*.py")):
        if any(part in {".git", ".venv", "venv", "__pycache__", "node_modules"} for part in path.parts):
            continue
        yield path


def _module_target(repo: Path, path: Path, app_name: str) -> str:
    rel = path.relative_to(repo).as_posix()
    module = rel[:-3].replace("/", ".") if rel.endswith(".py") else rel.replace("/", ".")
    if module.endswith(".__init__"):
        module = module[:-9]
    return f"{module}:{app_name}"


def discover_final_plan(repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path).resolve()
    candidates: list[tuple[int, Path, str]] = []
    all_text: list[str] = []

    for path in _iter_python(repo):
        text = _read(path)
        all_text.append(f"\n# FILE: {path.relative_to(repo).as_posix()}\n{text}")
        if "FastAPI" not in text:
            continue
        m = re.search(r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*FastAPI\s*\(", text)
        if not m:
            continue
        score = 0
        rel = path.relative_to(repo).as_posix().lower()
        if rel in {"api.py", "src/api.py"}:
            score += 100
        if rel.endswith("/api.py") or rel == "api.py":
            score += 60
        if "@app.get" in text or "@app.post" in text:
            score += 20
        candidates.append((score, path, m.group(1)))

    candidates.sort(key=lambda x: (-x[0], x[1].as_posix()))
    api_file = ""
    api_target = ""
    if candidates:
        _, chosen, app_name = candidates[0]
        api_file = chosen.relative_to(repo).as_posix()
        api_target = _module_target(repo, chosen, app_name)

    corpus = "\n".join(all_text)
    readme = _read(repo / "README.md", 250_000)
    requirements = _read(repo / "requirements.txt", 100_000)
    lower_req = requirements.lower()
    lower_readme = readme.lower()

    evidence: list[str] = []
    warnings: list[str] = []
    if api_target:
        evidence.append(f"FastAPI app: {api_target} ({api_file})")
    else:
        warnings.append("لم يتم اكتشاف FastAPI app بصورة حتمية.")

    static = {
        "has_readme": bool(readme.strip()),
        "has_requirements": bool(requirements.strip()),
        "fastapi_declared": "fastapi" in lower_req,
        "uvicorn_declared": "uvicorn" in lower_req,
        "has_explain_code": bool(re.search(r"\.explain\s*\(|explain\s*\(", corpus, re.I)),
        "has_execution_stats": "executionstats" in corpus.lower(),
        "has_aggregation_code": bool(re.search(r"\.aggregate\s*\(", corpus, re.I)),
        "has_materialized_view_code": bool(re.search(r"materialized|refresh[_\s-]*mv|mv_", corpus, re.I)),
        "has_scheduled_job_code": bool(re.search(r"apscheduler|add_job\s*\(|crontrigger|intervaltrigger|schedule", corpus, re.I)),
        "readme_mentions_indexes": "index" in lower_readme or "فهرس" in readme,
        "readme_mentions_explain": "explain" in lower_readme,
        "readme_mentions_aggregations": "aggregation" in lower_readme or "تجميع" in readme,
        "readme_mentions_materialized_views": "materialized" in lower_readme or "mv_" in lower_readme,
        "readme_mentions_jobs": "job" in lower_readme or "scheduler" in lower_readme or "جدول" in readme,
        "readme_mentions_api": "fastapi" in lower_readme or "/health" in lower_readme or "/docs" in lower_readme,
    }

    confidence = 0.25
    if api_target:
        confidence += 0.45
    if static["has_readme"]:
        confidence += 0.10
    if static["fastapi_declared"] and static["uvicorn_declared"]:
        confidence += 0.10
    if static["has_aggregation_code"] or static["has_materialized_view_code"] or static["has_scheduled_job_code"]:
        confidence += 0.10

    return {
        "api_target": api_target,
        "api_file": api_file,
        "confidence": round(min(confidence, 0.99), 2),
        "static": static,
        "evidence": evidence,
        "warnings": warnings,
    }
