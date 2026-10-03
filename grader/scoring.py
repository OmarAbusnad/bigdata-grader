from __future__ import annotations
import json
from pathlib import Path


def load_rubric(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def score_boolean_checks(rubric: dict, checks: dict[str, bool | float | None]) -> dict:
    if rubric.get('status') != 'ACTIVE':
        raise RuntimeError(f"Rubric is not active for scoring: {rubric.get('status', 'UNKNOWN')}")
    total = 0.0
    evaluated_max = 0.0
    details = []
    for item in rubric.get('items', []):
        key = item['key']
        max_points = float(item['points'])
        value = checks.get(key, None)
        if value is None:
            details.append({'key': key, 'label': item.get('label', key), 'awarded': None, 'max': max_points, 'status': 'NOT_EVALUATED'})
            continue
        evaluated_max += max_points
        if isinstance(value, bool):
            awarded = max_points if value else 0.0
        else:
            awarded = max(0.0, min(max_points, max_points * float(value)))
        total += awarded
        details.append({'key': key, 'label': item.get('label', key), 'awarded': round(awarded, 2), 'max': max_points, 'status': 'EVALUATED'})
    return {
        'score': round(total, 2),
        'rubric_max': float(rubric.get('total', evaluated_max)),
        'evaluated_max': round(evaluated_max, 2),
        'complete': abs(evaluated_max - float(rubric.get('total', evaluated_max))) < 1e-9,
        'details': details,
    }


def _v(assertions: dict, keys: list[str]) -> float | None:
    vals = []
    for k in keys:
        a = assertions.get(k)
        if not a:
            continue
        verdict = a.get('verdict')
        if verdict == 'PASS':
            vals.append(1.0)
        elif verdict == 'FAIL':
            vals.append(0.0)
        # INCONCLUSIVE / ERROR are not silently converted into zero.
    if not vals:
        return None
    return sum(vals) / len(vals)


def _v_strict(assertions: dict, keys: list[str]) -> float | None:
    vals = []
    for k in keys:
        a = assertions.get(k)
        if not a:
            return None
        verdict = a.get('verdict')
        if verdict == 'PASS':
            vals.append(1.0)
        elif verdict == 'FAIL':
            vals.append(0.0)
        else:
            return None
    return sum(vals) / len(vals) if vals else None

def derive_midterm_capabilities(runtime: dict | None, static: dict | None = None) -> dict[str, float | None]:
    if not runtime or not isinstance(runtime.get('assertions'), dict):
        return {}
    a = runtime['assertions']
    static = static or {}
    docs_vals = [bool(static.get('has_readme')), bool(static.get('has_requirements')), bool(static.get('has_tests'))]
    code_docs = sum(docs_vals) / len(docs_vals) if docs_vals else None
    return {
        'architecture_router': _v_strict(a, ['batch_pipeline.engine', 'spark_pipeline.engine']),
        'python_batch': _v_strict(a, ['batch_pipeline.command', 'batch.raw_count', 'batch.validated_count', 'batch.quarantine_count', 'batch_pipeline.engine']),
        'pyspark': _v_strict(a, ['spark_pipeline.command', 'spark.raw_count', 'spark.validated_count', 'spark.quarantine_count', 'spark_pipeline.engine']),
        'raw_elt': _v_strict(a, ['batch.raw_count', 'batch.validated_count', 'batch.quarantine_count']),
        'cleaning_audit': _v_strict(a, ['batch.cleaning_samples', 'batch.audit_trail']),
        'quarantine': _v_strict(a, ['batch.quarantine_count', 'batch.quarantine_errors']),
        'upsert_idempotency': _v_strict(a, [
            'upsert.final_validated', 'upsert.insert_samples', 'upsert.update_samples', 'upsert.unchanged_samples',
            'idempotency.validated_stable', 'idempotency.duplicates'
        ]),
        'metrics_consistency': _v_strict(a, ['batch.metrics_present', 'batch.metric_input', 'batch.metric_quarantine']),
        'code_tests_docs': code_docs,
        'advanced_track': _v_strict(a, ['incremental.final_validated', 'incremental.rerun_validated_stable', 'incremental.rerun_duplicates']),
    }
