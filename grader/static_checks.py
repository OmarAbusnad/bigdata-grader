from __future__ import annotations
from pathlib import Path
import re

_EXCLUDED_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache'}


def _iter_py(repo: Path):
    for p in sorted(repo.rglob('*.py')):
        if any(part in _EXCLUDED_DIRS for part in p.parts):
            continue
        yield p


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8-sig', errors='replace')
    except Exception:
        return ''


def static_checks(repo_path: str | Path) -> dict:
    """Static capability scan over the *full local repository clone*.

    Important: this function is evidence-only. Runtime grading must verify behaviour
    against hidden datasets and MongoDB state; a static PASS is not itself a grade.
    """
    repo = Path(repo_path)
    py_files = list(_iter_py(repo))
    texts = {p: _read(p) for p in py_files}

    def rel(p: Path) -> str:
        return str(p.relative_to(repo)).replace('\\', '/')

    batch_files = [p for p in py_files if 'batch' in p.name.lower()]
    spark_files = [p for p in py_files if 'spark' in p.name.lower()]

    if not batch_files:
        batch_files = [
            p for p, t in texts.items()
            if re.search(r'insert_many\s*\(|batch_size|python[_ -]?batch|streaming\s+csv', t, re.I)
        ]
    if not spark_files:
        spark_files = [
            p for p, t in texts.items()
            if re.search(r'\bPySpark\b|SparkSession|spark\.read|spark-submit', t, re.I)
        ]

    upsert_files = [
        p for p, t in texts.items()
        if re.search(r'upsert\s*=\s*True', t, re.I)
        or re.search(r'bulk_write\s*\(', t, re.I) and re.search(r'UpdateOne\s*\(', t)
    ]

    unique_index_files = [
        p for p, t in texts.items()
        if re.search(r'create_index\s*\([\s\S]{0,700}?unique\s*=\s*True', t, re.I)
        or re.search(r'IndexModel\s*\([\s\S]{0,700}?unique\s*=\s*True', t, re.I)
    ]

    collection_evidence = {}
    for name in ('orders_raw', 'orders_validated', 'orders_quarantine'):
        collection_evidence[name] = [rel(p) for p, t in texts.items() if name in t][:8]

    test_files = [
        p for p in py_files
        if 'tests' in p.parts and (p.name.startswith('test_') or p.name.endswith('_test.py'))
    ]

    # Student repositories may have the Phase-2 extension in its own supported
    # subdirectory. A root-only scan makes real documentation/dependencies vanish.
    allowed_extension_dirs = ("final_extension", "final", "phase2", "phase_2", "phase-2", "pro")
    candidate_roots = [repo] + [repo / name for name in allowed_extension_dirs if (repo / name).is_dir()]
    readme_candidates = [
        p for root in candidate_roots for p in root.iterdir()
        if p.is_file() and p.name.lower() == "readme.md"
    ]
    requirements_candidates = [
        p for root in candidate_roots for p in root.iterdir()
        if p.is_file() and (p.name.lower() == "requirements.txt" or p.name.lower() == "requirements-final.txt")
    ]
    readme_name = rel(readme_candidates[0]) if readme_candidates else None

    checks = {
        'has_readme': bool(readme_candidates),
        'has_requirements': bool(requirements_candidates),
        'has_batch_loader': bool(batch_files),
        'has_spark_loader': bool(spark_files),
        'mentions_orders_raw': bool(collection_evidence['orders_raw']),
        'mentions_orders_validated': bool(collection_evidence['orders_validated']),
        'mentions_orders_quarantine': bool(collection_evidence['orders_quarantine']),
        'uses_upsert': bool(upsert_files),
        'uses_unique_index': bool(unique_index_files),
        'has_tests': bool(test_files),
    }

    evidence = {
        'has_readme': [readme_name] if readme_name else [],
        'has_requirements': [rel(p) for p in requirements_candidates],
        'has_batch_loader': [rel(p) for p in batch_files[:8]],
        'has_spark_loader': [rel(p) for p in spark_files[:8]],
        'mentions_orders_raw': collection_evidence['orders_raw'],
        'mentions_orders_validated': collection_evidence['orders_validated'],
        'mentions_orders_quarantine': collection_evidence['orders_quarantine'],
        'uses_upsert': [rel(p) for p in upsert_files[:8]],
        'uses_unique_index': [rel(p) for p in unique_index_files[:8]],
        'has_tests': [rel(p) for p in test_files[:12]],
    }

    return {
        **checks,
        '_files_scanned': len(py_files),
        '_evidence': evidence,
        '_note': 'Static scan only; runtime hidden-data tests remain authoritative.',
    }
