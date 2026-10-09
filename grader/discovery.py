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


def _python_invocation(repo: Path, script_path: str) -> str:
    """Choose script vs module execution deterministically.

    Nested scripts such as src/main.py often import sibling top-level packages
    (for example config.settings). Running them as a file sets sys.path[0] to
    /workspace/src and can hide the repository root. In that case module mode
    keeps the repository root importable without changing student code.
    """
    normalized = script_path.replace("\\", "/")
    if "/" not in normalized or not normalized.endswith(".py"):
        return f"python {normalized}"

    script = repo / normalized
    text = _read(script)
    script_dir = script.parent

    imported_roots = set(re.findall(
        r"^\s*(?:from|import)\s+([A-Za-z_]\w*)",
        text,
        re.M,
    ))

    # Bare sibling imports such as "from file_router import ..." require
    # script execution so the script directory remains on sys.path.
    for root in imported_roots:
        if (script_dir / root).exists() or (script_dir / f"{root}.py").exists():
            if root not in {"src", "config"}:
                return f"python {normalized}"

    # Package/root imports such as "from src..." or "from config..." are safer
    # in module mode when the script itself does not explicitly add repo root.
    explicitly_adds_root = "sys.path.insert" in text or "sys.path.append" in text
    if not explicitly_adds_root:
        for root in imported_roots:
            root_at_repo = (repo / root).exists() or (repo / f"{root}.py").exists()
            root_beside_script = (script_dir / root).exists() or (script_dir / f"{root}.py").exists()
            if root_at_repo and not root_beside_script:
                module = normalized[:-3].replace("/", ".")
                return f"python -m {module}"

    return f"python {normalized}"


def _safe_repo_relative(candidate: str) -> str | None:
    normalized = re.sub(r"/+", "/", candidate.replace("\\", "/")).strip()
    p = Path(normalized)
    if not normalized or p.is_absolute() or ".." in p.parts:
        return None
    return normalized


def _looks_like_wrapper(repo: Path, candidate: str) -> str | None:
    """Resolve thin root wrappers that forward to another main module."""
    text = _read(repo / candidate)
    m = re.search(
        r"^\s*from\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import\s+main\b",
        text,
        re.M,
    )
    if not m:
        return None
    target = m.group(1).replace(".", "/") + ".py"
    target = _safe_repo_relative(target)
    if target and (repo / target).exists():
        target_text = _read(repo / target)
        if "argparse" in target_text or "add_argument" in target_text:
            return target
    return None


def _read_readme_case_insensitive(repo: Path) -> str:
    for path in sorted(repo.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file() and path.name.lower() == "readme.md":
            return _read(path)
    return ""


def _documented_ingest_command(repo: Path, readme: str) -> tuple[str | None, str | None]:
    """Extract a runnable data-pipeline command from README without inventing flags.

    Commands are validated against the referenced Python file/module. Unsupported
    documented flags are rejected, allowing a later valid README example to win.
    """
    import shlex

    candidates: list[tuple[int, str, str | None]] = []
    for raw_line in readme.splitlines():
        line = raw_line.strip().strip("`").strip()
        if not line or any(x in line for x in ["│", "├", "└", "─", "|--", "+--"]):
            continue
        line = re.sub(r"^\$\s*", "", line)
        # Documentation comments are not executable command arguments.
        line = re.sub(r"\s+#.*$", "", line).strip()
        if not re.match(r"^(?:python(?:3)?|py)\s+", line, re.I):
            continue
        if re.search(r"\b(?:pip|venv|pytest|unittest|compileall)\b", line, re.I):
            continue
        if re.search(r"\buvicorn\b", line, re.I):
            continue
        try:
            toks = shlex.split(line, posix=False)
        except Exception:
            continue
        if len(toks) < 2:
            continue

        target_file: Path | None = None
        entrypoint: str | None = None
        arg_start = 2
        if len(toks) >= 3 and toks[1] == "-m":
            module = toks[2].strip("\"'")
            target_file = repo / (module.replace(".", "/") + ".py")
            if not target_file.is_file():
                package_main = repo / module.replace(".", "/") / "__main__.py"
                if package_main.is_file():
                    target_file = package_main
                else:
                    continue
            entrypoint = str(target_file.relative_to(repo)).replace("\\", "/")
            arg_start = 3
        else:
            target = toks[1].strip("\"'").replace("\\", "/")
            if not target.endswith(".py"):
                continue
            target_file = repo / target
            if not target_file.is_file():
                continue
            entrypoint = target

        # A dataset generator is not an ingestion pipeline, even if its README
        # advertises an --input flag. Do not attribute empty MongoDB to students.
        helper_name = target_file.stem.lower()
        if re.match(r"^(?:create|generate|make|prepare|download|seed|mock)[_-].*(?:sample|data|dataset|fixture|csv)", helper_name):
            continue

        code = _read(target_file)
        supported_flags = _argument_flags(code)
        command_flags = [t for t in toks[arg_start:] if t.startswith("-")]
        unsupported = [f for f in command_flags if f not in supported_flags]
        if unsupported:
            continue

        normalized = list(toks)
        # The Windows `py` launcher is unavailable in Linux grading containers.
        if normalized[0].lower() == "py":
            normalized[0] = "python"
        # README examples may use Windows separators even though grading runs on Linux.
        # Use the validated repository-relative path in the executable command too.
        if toks[1] != "-m" and entrypoint is not None:
            normalized[1] = shlex.quote(entrypoint)
        replaced_file = False
        file_flags = {"--input", "--file", "--file-path", "--file_path", "--csv", "-f", "-i"}
        for i in range(arg_start, len(normalized)):
            tok = normalized[i].strip("\"'")
            if tok in file_flags and i + 1 < len(normalized):
                normalized[i + 1] = "{file}"
                replaced_file = True
            elif (
                "<csv" in tok.lower()
                or "csv_path" in tok.lower()
                or tok.lower().endswith(".csv")
                or tok.lower().endswith(".jsonl")
            ):
                normalized[i] = "{file}"
                replaced_file = True

        positional_args = re.findall(r"add_argument\(\s*[\"']([A-Za-z_]\w*)[\"']", code)
        if not replaced_file and positional_args:
            normalized.append("{file}")
            replaced_file = True

        if not replaced_file:
            continue

        for i, tok in enumerate(normalized[:-1]):
            clean = tok.strip("\"'")
            if clean in {"--threshold", "--threshold-mb", "-t"}:
                normalized[i + 1] = "{threshold_mb}"
            if clean in {"--database", "--db-name"}:
                normalized[i + 1] = "{db_name}"

        # Remove destructive reset flags from repeated ingest invocations.
        normalized = [t for t in normalized if t not in ("--reset-db", "--reset")]
        cmd = " ".join(normalized)
        score = 0
        low = cmd.lower()
        if "main" in low or "pipeline_entry" in low:
            score += 4
        if "--action run" in low or " run " in low:
            score += 2
        if "--write" in low:
            score += 2
        if "{file}" in cmd:
            score += 3
        candidates.append((score, cmd, entrypoint))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1], candidates[0][2]


def _detect_entrypoint(repo: Path, readme: str) -> str | None:
    commands = re.findall(r"(?:python|py)\s+(?:-m\s+)?([\w./\\-]*main\.py)", readme, re.I)
    for raw in commands:
        candidate = _safe_repo_relative(raw)
        if not candidate or not (repo / candidate).exists():
            continue
        wrapper = _looks_like_wrapper(repo, candidate)
        return wrapper or candidate

    for candidate in PYTHON_ENTRY_CANDIDATES:
        if not (repo / candidate).exists():
            continue
        wrapper = _looks_like_wrapper(repo, candidate)
        if wrapper:
            return wrapper
        text = _read(repo / candidate)
        if "argparse" in text or "add_argument" in text:
            return candidate

    for candidate in PYTHON_ENTRY_CANDIDATES:
        if (repo / candidate).exists():
            return candidate

    for p in sorted(repo.rglob("*.py")):
        txt = _read(p)
        if "argparse" in txt and "__main__" in txt:
            rel = _safe_repo_relative(str(p.relative_to(repo)))
            if rel:
                return rel
    return None


def _argument_flags(text: str) -> set[str]:
    flags: set[str] = set()
    for call in re.findall(r"add_argument\((.*?)\)", text, re.S):
        for flag in re.findall(r"[\"'](-{1,2}[A-Za-z0-9_-]+)[\"']", call):
            flags.add(flag)
    return flags


def _command_from_entry(repo: Path, entrypoint: str | None) -> tuple[str | None, str | None, bool, bool]:
    if not entrypoint:
        return None, None, False, False
    text = _read(repo / entrypoint)
    flags = _argument_flags(text)
    base_cmd = _python_invocation(repo, entrypoint)

    run_prefix = ""
    if re.search(r"add_subparsers\([^\)]*required\s*=\s*True", text, re.S) and re.search(
        r"add_parser\(\s*[\"']run[\"']", text
    ):
        run_prefix = " run"

    file_flag = next(
        (flag for flag in ("--input", "--file", "--csv", "--file-path", "--file_path", "-f", "-i") if flag in flags),
        None,
    )
    if file_flag:
        cmd = f"{base_cmd}{run_prefix} {file_flag} {{file}}"
    elif re.search(r"add_argument\(\s*[\"'][A-Za-z_]\w*[\"']", text):
        cmd = f"{base_cmd}{run_prefix} {{file}}"
    elif "argparse" in text or "add_argument" in text:
        cmd = None
    else:
        cmd = f"{base_cmd} {{file}}"

    threshold_flag = next((f for f in ("--threshold-mb", "--threshold", "-t") if f in flags), None)
    db_name_flag = next((f for f in ("--db-name", "--database") if f in flags), None)
    threshold_configurable = bool(threshold_flag)
    database_configurable = bool(db_name_flag)

    if cmd and threshold_flag:
        cmd += f" {threshold_flag} {{threshold_mb}}"
    if cmd and db_name_flag:
        cmd += f" {db_name_flag} {{db_name}}"

    if cmd and "--no-server" in flags and "--no-server" not in cmd:
        cmd += " --no-server"
    if cmd and "--no-browser" in flags and "--no-browser" not in cmd:
        cmd += " --no-browser"

    reset_cmd = None
    if cmd:
        if "--reset-db" in flags:
            reset_cmd = cmd + " --reset-db"
        elif "--reset" in flags:
            reset_cmd = cmd + " --reset"
    return cmd, reset_cmd, threshold_configurable, database_configurable

def _detect_setup_command(repo: Path, readme: str) -> str | None:
    # Prefer an explicitly documented executable command. Never treat README
    # directory trees or prose containing a filename ending in ".py " as "py".
    command_lines = []
    for line in readme.splitlines():
        text = line.strip().strip('`').strip()
        if any(x in text for x in ["│", "├", "└", "─", "|--", "+--"]):
            continue
        text = re.sub(r"^\$\s*", "", text)
        # The interpreter must start the line; substring matches inside ".py"
        # are forbidden.
        if not re.match(r"^(?:python(?:3)?|py)\s+", text, re.I):
            continue
        if not re.search(r"mongo_setup|setup_mongo|init_db|init_project|setup\.py", text, re.I):
            continue
        text = re.sub(r"\s+#.*$", "", text).strip()
        m = re.match(r"^(?:python(?:3)?|py)\s+(?:-m\s+)?([^\s]+)", text, re.I)
        if not m:
            continue
        target = m.group(1).replace("\\", "/")
        if target.endswith(".py") and not (repo / target).is_file():
            continue
        command_lines.append(text)
    if command_lines:
        return command_lines[0]
    candidates = [
        "src/mongo_setup.py", "mongo_setup.py", "scripts/mongo_setup.py",
        "init_project.py", "scripts/init_db.py", "src/init_db.py",
    ]
    for c in candidates:
        if (repo / c).exists():
            return _python_invocation(repo, c)
    return None


def _parse_settings(text: str) -> dict:
    out: dict[str, object] = {}
    out["db"] = _first_match([
        r"MONGO_DB_NAME\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"DB_NAME\s*=\s*os\.getenv\(\s*['\"]DB_NAME['\"],\s*['\"]([^'\"]+)",
        r"DATABASE_NAME\s*=\s*os\.getenv\(\s*['\"]DATABASE_NAME['\"],\s*['\"]([^'\"]+)",
        r"MONGO_DATABASE\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGODB_DATABASE\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGO_DATABASE\s*=\s*[\"']([^\"']+)",
        r"MONGO_DB_NAME\s*=\s*[\"']([^\"']+)",
        r"MONGODB_DATABASE\s*=\s*[\"']([^\"']+)",
        r"(?m)^\s*MONGODB_DATABASE\s*=\s*[\"']?([A-Za-z0-9_-]+)[\"']?\s*(?:#.*)?$",
        r"(?m)^\s*MONGO_DATABASE\s*=\s*[\"']?([A-Za-z0-9_-]+)[\"']?\s*(?:#.*)?$",
        r"(?m)^\s*MONGO_DB_NAME\s*=\s*[\"']?([A-Za-z0-9_-]+)[\"']?\s*(?:#.*)?$",
    ], text)
    # An explicit variable without a hard-coded default is still configurable.
    out["db_env"] = bool(re.search(
        r"(?:MONGO_(?:DB_NAME|DATABASE)|MONGODB_DATABASE|DB_NAME|DATABASE_NAME)\s*=\s*(?:os\.)?getenv",
        text, re.I,
    )) or bool(re.search(r"(?m)^\s*MONGODB_DATABASE\s*=", text))
    out["uri"] = _first_match([
        r"MONGO_URI\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGODB_URI\s*=\s*os\.getenv\([^,]+,\s*[\"']([^\"']+)",
        r"MONGO_URI\s*=\s*[\"']([^\"']+)",
        r"MONGODB_URI\s*=\s*[\"']([^\"']+)",
        r"(?m)^\s*MONGODB_URI\s*=\s*[\"']?((?:mongodb(?:\+srv)?://)[^\s#\"']+)[\"']?\s*(?:#.*)?$",
        r"(?m)^\s*MONGO_URI\s*=\s*[\"']?((?:mongodb(?:\+srv)?://)[^\s#\"']+)[\"']?\s*(?:#.*)?$",
    ], text)
    out["uri_env"] = bool(re.search(
        r"(?:MONGO_URI|MONGODB_URI)\s*=\s*(?:os\.)?getenv",
        text, re.I,
    )) or bool(re.search(r"(?m)^\s*MONGODB_URI\s*=", text))
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

    readme = _read_readme_case_insensitive(repo)
    req_exists = (repo / "requirements.txt").exists()
    settings_paths = [repo / "config/settings.py", repo / "settings.py", repo / "src/settings.py"]
    settings_text = "\n".join(_read(p) for p in settings_paths if p.exists())
    env_paths = [repo / ".env.example", repo / "env.example", repo / "example.env"]
    env_text = "\n".join(_read(p) for p in env_paths if p.exists())
    repo_text = _all_text(repo)

    documented_cmd, documented_entrypoint = _documented_ingest_command(repo, readme)
    entrypoint = documented_entrypoint or _detect_entrypoint(repo, readme)
    ingest_cmd, reset_cmd, threshold_flag, db_flag = _command_from_entry(repo, entrypoint)
    if documented_cmd:
        ingest_cmd = documented_cmd
        threshold_flag = any(x in documented_cmd for x in ("--threshold", "--threshold-mb", " -t "))
        db_flag = any(x in documented_cmd for x in ("--database", "--db-name"))
    settings = _parse_settings(settings_text + "\n" + env_text + "\n" + repo_text)
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
        if documented_cmd:
            evidence.append("Ingest command source: validated README command")
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
