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


def _readme_api_target(repo: Path, readme: str) -> tuple[str, str]:
    """Parse an explicit README uvicorn command without LLM inference."""
    for line in readme.splitlines():
        text = line.strip().strip('`').strip()
        if any(x in text for x in ["│", "├", "└", "─", "|--", "+--"]):
            continue
        text = re.sub(r"^\$\s*", "", text)
        m = re.match(
            r"^(?:(?:python(?:3)?|py)\s+-m\s+)?uvicorn\s+"
            r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*)\b",
            text,
            re.I,
        )
        if not m:
            continue
        target = m.group(1)
        module, _obj = target.split(":", 1)
        module_file = repo / (module.replace(".", "/") + ".py")
        package_init = repo / module.replace(".", "/") / "__init__.py"
        if module_file.is_file() or package_init.is_file():
            return target, text
    return "", ""


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
    env_example_exists = (repo / ".env.example").is_file() or (repo / "example.env").is_file()
    lower_req = requirements.lower()
    lower_readme = readme.lower()
    readme_target, readme_start_command = _readme_api_target(repo, readme)

    evidence: list[str] = []
    warnings: list[str] = []
    code_api_target = api_target
    if readme_target:
        evidence.append(f"README startup target: {readme_target}")
        api_target = readme_target
        api_file = readme_target.split(":", 1)[0].replace(".", "/") + ".py"
    if code_api_target:
        evidence.append(f"FastAPI app: {code_api_target}")
    if not api_target:
        warnings.append("لم يتم اكتشاف FastAPI app بصورة حتمية.")
    if readme_target and code_api_target and readme_target != code_api_target:
        warnings.append(f"README target ({readme_target}) conflicts with source target ({code_api_target}).")

    static = {
        "has_readme": bool(readme.strip()),
        "has_requirements": bool(requirements.strip()),
        "has_env_example": env_example_exists,
        "fastapi_declared": "fastapi" in lower_req,
        "uvicorn_declared": "uvicorn" in lower_req,
        "has_explain_code": bool(re.search(r'\.explain\s*\(|explain\s*\(|command\s*\(\s*["\']explain["\']', corpus, re.I)),
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
        "readme_mentions_install": bool(re.search(r"install|installation|pip\s+install|تثبيت", readme, re.I)),
        "readme_mentions_run": bool(re.search(r"run|تشغيل|python\s+|uvicorn", readme, re.I)),
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

    requires_agent = bool(
        not api_target
        or (readme_target and code_api_target and readme_target != code_api_target)
    )

    return {
        "api_target": api_target,
        "api_file": api_file,
        "api_target_source": "readme" if readme_target else ("source" if code_api_target else "unresolved"),
        "readme_api_target": readme_target,
        "readme_start_command": readme_start_command,
        "source_api_target": code_api_target,
        "requires_agent": requires_agent,
        "confidence": round(min(confidence, 0.99), 2),
        "static": static,
        "evidence": evidence,
        "warnings": warnings,
    }
