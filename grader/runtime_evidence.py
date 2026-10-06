from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

ENGINE_KEYS = {'engine', 'engine_used', 'used_engine', 'selected_engine', 'processing_engine'}
METRIC_FILES = ('results.json', 'result.json', 'metrics.json', 'run_metrics.json', 'pipeline_metrics.json')


def _walk(obj: Any, path: str = ''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{path}.{k}' if path else str(k)
            yield p, k, v
            yield from _walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f'{path}[{i}]')


def find_latest_metrics(repo: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    repo = Path(repo)
    candidates: list[Path] = []
    for name in METRIC_FILES:
        candidates.extend(repo.rglob(name))
    candidates = [p for p in candidates if '.git' not in p.parts and '.grader_venv' not in p.parts]
    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding='utf-8-sig', errors='replace'))
            if isinstance(data, dict):
                return data, str(p.relative_to(repo)).replace('\\', '/')
        except Exception:
            continue
    return None, None


def normalize_engine(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower().replace('-', '_').replace(' ', '_')
    if any(x in s for x in ('pyspark', 'spark_dataframe', 'spark')):
        return 'pyspark'
    if any(x in s for x in ('python_batch', 'python_stream', 'batch', 'python')):
        return 'python_batch'
    return None


def detect_engine(stdout: str, stderr: str, metrics: dict[str, Any] | None,
                  mongo_values: list[str] | None = None) -> tuple[str | None, list[str]]:
    evidence: list[str] = []
    votes: list[str] = []
    if metrics:
        for path, key, value in _walk(metrics):
            if key.lower() in ENGINE_KEYS:
                eng = normalize_engine(value)
                if eng:
                    votes.append(eng)
                    evidence.append(f'metrics:{path}={value}')
    for value in mongo_values or []:
        eng = normalize_engine(value)
        if eng:
            votes.append(eng)
            evidence.append(f'mongodb:engine={value}')
    text = f'{stdout}\n{stderr}'

    # A direct router/selection statement is stronger than generic Spark
    # signatures that may appear later in a secondary ELT stage or traceback.
    explicit_patterns = [
        r'(?:selected|used|chosen|decision|القرار|المحرك(?:\s+المستخدم|\s+المختار)?)[^\n:]{0,80}(?:[:=]|استخدام)\s*\[?([^\n\]]+)',
        r'(?:route|routing|توجيه)[^\n]{0,80}\b(pyspark|python[_ -]?batch)\b',
    ]
    for pat in explicit_patterns:
        for m in re.finditer(pat, stdout, re.I):
            eng = normalize_engine(m.group(1))
            if eng:
                evidence.append(f'console-explicit:{m.group(1).strip()[:120]}')
                return eng, evidence

    patterns = [
        (r'(?:selected|used|chosen|المحرك(?:\s+المستخدم|\s+المختار)?)[^\n:]{0,50}[:=]\s*([^\n]+)', 'console'),
        (r'\b(pyspark|python[_ -]?batch)\b', 'console'),
    ]
    for pat, src in patterns:
        for m in re.finditer(pat, text, re.I):
            raw = m.group(1)
            eng = normalize_engine(raw)
            if eng:
                votes.append(eng)
                evidence.append(f'{src}:{raw.strip()[:120]}')
                if len(evidence) >= 8:
                    break
        if len(evidence) >= 8:
            break
    if re.search(r'SparkContext|SparkSession|DAGScheduler|TaskSetManager|org\.apache\.spark|SparkUI', text, re.I):
        votes.append('pyspark')
        evidence.append('console:Apache Spark runtime log signature detected')
    if not votes:
        return None, evidence
    # Majority vote, preferring structured evidence order (metrics -> Mongo -> console).
    py = votes.count('python_batch')
    sp = votes.count('pyspark')
    return ('pyspark' if sp > py else 'python_batch'), evidence


def find_metric_value(metrics: dict[str, Any] | None, aliases: tuple[str, ...]) -> Any:
    if not metrics:
        return None
    aliases_l = {a.lower() for a in aliases}
    for _, key, value in _walk(metrics):
        if key.lower() in aliases_l and not isinstance(value, (dict, list)):
            return value
    return None
