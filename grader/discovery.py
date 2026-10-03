from __future__ import annotations
import re
from pathlib import Path
from typing import Iterable

from .models import ExecutionPlan

PYTHON_ENTRY_CANDIDATES = [
    "main.py", "src/main.py", "pipeline.py", "src/pipeline.py", "run.py", "src/run.py"
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return ""


def _all_text(repo: Path, patterns: Iterable[str] = ("*.py", "*.md", "*.yaml", "*.yml", "*.txt"), max_files: int = 240) -> str:
    chunks: list[str] = []
    seen = 0
    for pattern in patterns:
        for path in sorted(repo.rglob(pattern)):
            if any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
                continue
            chunks.append(f"\n# FILE: {path.relative_to(repo)}\n" + _read(path)[:50000])
            seen += 1
            if seen >= max_files:
                return "\n".join(chunks)
    return "\n".join(chunks)


def _first_match(patterns: list[str], text: str, flags: int = re.I | re.M) -> str | None:
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(1)
    return None


def _detect_entrypoint(repo: Path, readme: str) -> str | None:
    commands = re.findall(r"(?:python|py)\s+(?:-m\s+)?([\w./\\-]*main\.py)", readme, re.I)
    for candidate in commands:
        candidate = re.sub(r"/+", "/", candidate.replace("\\", "/"))
        if (repo / candidate).exists():
            return candidate
    for candidate in PYTHON_ENTRY_CANDIDATES:
        if (repo / candidate).exists():
            return candidate
    for p in sorted(repo.rglob("*.py")):
        txt = _read(p)
        if "argparse" in txt and "__main__" in txt:
            return str(p.relative_to(repo)).replace("\\", "/")
    return None


def _command_from_entry(repo: Path, entrypoint: str | None) -> tuple[str | None, str | None, bool, bool]:
    if not entrypoint:
        return None, None, False, False
    text = _read(repo / entrypoint)
    flags = set(re.findall(r"add_argument\(\s*[\"'](--[\w-]+)", text))
    if "--input" in flags:
        cmd = f"python {entrypoint} --input {{file}}"
    elif "--file" in flags:
        cmd = f"python {entrypoint} --file {{file}}"
    elif "-i" in text and "add_argument" in text:
        cmd = f"python {entrypoint} -i {{file}}"
    else:
        cmd = f"python {entrypoint} {{file}}"

    threshold_configurable = "--threshold-mb" in flags
    database_configurable = "--db-name" in flags or "--database" in flags
    if "--threshold-mb" in flags:
        cmd += " --threshold-mb {threshold_mb}"
    if "--db-name" in flags:
        cmd += " --db-name {db_name}"
    elif "--database" in flags:
        cmd += " --database {db_name}"

    reset_cmd = None
    if "--reset-db" in flags:
        reset_cmd = cmd + " --reset-db"
    elif "--reset" in flags:
        reset_cmd = cmd + " --reset"
    return cmd, reset_cmd, threshold_configurable, database_configurable


def _detect_setup_command(repo: Path, readme: str) -> str | None:
    # Prefer an explicitly documented Mongo/init command.
    command_lines = []
    for line in readme.splitlines():
        s = line.strip().strip('`')
        if re.search(r"(?:python|py)\s+", s, re.I) and re.search(r"mongo_setup|setup_mongo|init_db|init_project|setup\.py", s, re.I):
            command_lines.append(s)
    if command_lines:
        return command_lines[0]
    candidates = [
        "src/mongo_setup.py", "mongo_setup.py", "scripts/mongo_setup.py",
        "init_project.py", "scripts/init_db.py", "src/init_db.py",
    ]
    for c in candidates:
        if (repo / c).exists():
            return f"python {c}"
    return None


def _parse_settings(text: str) -> dict:
    out: dict[str, object] = {}
    out["db"] = _first_match([
        r"MONGO_DB_NAME\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGO_DATABASE\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGO_DATABASE\s*=\s*[\"']([^\"']+)",
        r"MONGO_DB_NAME\s*=\s*[\"']([^\"']+)",
    ], text)
    out["db_env"] = bool(re.search(r"MONGO_(?:DB_NAME|DATABASE)\s*=\s*(?:os\.)?getenv", text, re.I))
    out["uri"] = _first_match([
        r"MONGO_URI\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGO_URI\s*=\s*[\"']([^\"']+)",
    ], text)
    out["uri_env"] = bool(re.search(r"MONGO_URI\s*=\s*(?:os\.)?getenv", text, re.I))
    threshold = _first_match([
        r"SMALL_FILE_THRESHOLD_MB\s*=\s*float\(os\.getenv\([^,]+,\s*[\"']?([0-9.]+)",
        r"(?:SMALL_FILE_THRESHOLD_MB|FILE_SIZE_THRESHOLD_MB|THRESHOLD_MB)\s*=\s*([0-9.]+)",
    ], text)
    out["threshold"] = float(threshold) if threshold else None
    out["threshold_env"] = bool(re.search(r"(?:SMALL_FILE_THRESHOLD_MB|FILE_SIZE_THRESHOLD_MB|THRESHOLD_MB).*getenv", text, re.I))
    out["spark_master"] = _first_match([
        r"SPARK_MASTER_URL\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"SPARK_MASTER\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"SPARK_MASTER_URL\s*=\s*[\"']([^\"']+)",
        r"SPARK_MASTER\s*=\s*[\"']([^\"']+)",
    ], text)
    out["spark_master_env"] = bool(re.search(r"SPARK_MASTER(?:_URL)?.*getenv", text, re.I))
    out["business_key"] = _first_match([
        r"STABLE_BUSINESS_KEY\s*=\s*[\"']([^\"']+)",
        r"BUSINESS_KEY\s*=\s*[\"']([^\"']+)",
    ], text) or ("id_order" if re.search(r"unique=True[^\n]{0,200}id_order|create_index\([^\)]*id_order", text, re.I | re.S) else "order_id")
    collection_patterns = {
        "raw": [r"(?:RAW_COLLECTION|COLLECTION_RAW)\s*=\s*[\"']([^\"']+)"],
        "validated": [r"(?:VALIDATED_COLLECTION|COLLECTION_VALIDATED)\s*=\s*[\"']([^\"']+)"],
        "quarantine": [r"(?:QUARANTINE_COLLECTION|COLLECTION_QUARANTINE)\s*=\s*[\"']([^\"']+)"],
    }
    for key, pats in collection_patterns.items():
        val = _first_match(pats, text)
        if val:
            out[key] = val
    return out


def _portability_warnings(repo_text: str) -> list[str]:
    warnings = []
    if re.search(r"Path\(r?[\"'][A-Za-z]:\\", repo_text):
        warnings.append("يوجد مسار Windows مطلق hard-coded؛ قد يفشل على جهاز المصحح أو Linux.")
    if re.search(r"JAVA_HOME|jdk-[0-9]", repo_text, re.I) and re.search(r"[A-Za-z]:\\", repo_text):
        warnings.append("يوجد مسار Java محلي hard-coded؛ قد تحتاج بيئة التقييم إلى ضبط JAVA_HOME.")
    return warnings


def discover_execution_plan(repo_path: str | Path) -> ExecutionPlan:
    repo = Path(repo_path).resolve()
    if not repo.exists():
        raise FileNotFoundError(repo)

    # Student repositories are evaluated as submitted.
    # No grader-specific file is required or trusted from inside the student repository.

    readme = _read(repo / "README.md")
    req_exists = (repo / "requirements.txt").exists()
    settings_paths = [repo / "config/settings.py", repo / "settings.py", repo / "src/settings.py"]
    settings_text = "\n".join(_read(p) for p in settings_paths if p.exists())
    repo_text = _all_text(repo)

    entrypoint = _detect_entrypoint(repo, readme)
    ingest_cmd, reset_cmd, threshold_flag, db_flag = _command_from_entry(repo, entrypoint)
    settings = _parse_settings(settings_text + "\n" + repo_text)
    setup_cmd = _detect_setup_command(repo, readme)

    collections = {
        "raw": str(settings.get("raw") or "orders_raw"),
        "validated": str(settings.get("validated") or "orders_validated"),
        "quarantine": str(settings.get("quarantine") or "orders_quarantine"),
    }
    evidence = []
    score = 0.10
    if entrypoint:
        evidence.append(f"Entrypoint: {entrypoint}")
        score += 0.25
    if ingest_cmd:
        evidence.append(f"Ingest command: {ingest_cmd}")
        score += 0.25
    if setup_cmd:
        evidence.append(f"Setup command: {setup_cmd}")
    if settings.get("db"):
        evidence.append(f"MongoDB database: {settings['db']}")
        score += 0.10
    if req_exists:
        evidence.append("requirements.txt موجود")
        score += 0.10
    if all(c in repo_text for c in ["orders_raw", "orders_validated", "orders_quarantine"]):
        evidence.append("Collections الأساسية ظاهرة في المشروع")
        score += 0.10
    if settings.get("business_key"):
        evidence.append(f"Business key: {settings['business_key']}")
        score += 0.05

    warnings = _portability_warnings(repo_text)
    if not reset_cmd:
        warnings.append("لا يوجد Reset CLI واضح؛ سيقوم المصحح بتنظيف بيانات Collections مباشرة عبر MongoDB بين الاختبارات.")
    if not ingest_cmd:
        warnings.append("لم يتم اكتشاف أمر تشغيل موثوق؛ يحتاج المشروع إلى AI analysis أو Instructor Override خارجي.")

    return ExecutionPlan(
        repo_path=str(repo),
        install_command="pip install -r requirements.txt" if req_exists else "",
        setup_command=setup_cmd,
        entrypoint=entrypoint,
        ingest_command=ingest_cmd,
        reset_command=reset_cmd,
        database_name=str(settings.get("db")) if settings.get("db") else None,
        database_configurable=db_flag or bool(settings.get("db_env")),
        mongo_uri=str(settings.get("uri") or "mongodb://localhost:27017"),
        mongo_uri_configurable=bool(settings.get("uri_env")),
        collections=collections,
        business_key=str(settings.get("business_key") or "order_id"),
        threshold_mb=settings.get("threshold") if isinstance(settings.get("threshold"), float) else None,
        threshold_configurable=threshold_flag or bool(settings.get("threshold_env")),
        spark_master=str(settings.get("spark_master")) if settings.get("spark_master") else None,
        spark_master_configurable=bool(settings.get("spark_master_env")),
        confidence=round(min(score, 0.97), 2),
        source="heuristic",
        warnings=warnings,
        evidence=evidence,
    )
