from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from .models import ExecutionPlan
from .agent_analyzer import _sanitize_command


ALLOWED_FIELDS = {
    "entrypoint", "ingest_command", "setup_command", "reset_command",
    "database_name", "database_configurable", "mongo_uri", "mongo_uri_configurable",
    "business_key", "threshold_mb", "threshold_configurable", "spark_master",
    "spark_master_configurable", "advanced_track",
}


def load_instructor_override(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Override must be a YAML mapping: {p}")
    return data


def apply_instructor_override(plan: ExecutionPlan, data: dict[str, Any] | None) -> tuple[ExecutionPlan, list[str]]:
    if not data:
        return plan, []

    new = ExecutionPlan(**plan.to_dict())
    evidence: list[str] = []

    for key, value in data.items():
        if key == "collections" and isinstance(value, dict):
            for c in ("raw", "validated", "quarantine"):
                if value.get(c):
                    new.collections[c] = str(value[c])
            evidence.append("Instructor override: collections")
            continue
        if key not in ALLOWED_FIELDS:
            continue
        if key in {"ingest_command", "setup_command", "reset_command"}:
            sanitized = _sanitize_command(str(value)) if value else None
            if value and not sanitized:
                raise ValueError(f"Unsafe command in instructor override: {key}")
            setattr(new, key, sanitized)
        elif key in {"database_configurable", "mongo_uri_configurable", "threshold_configurable", "spark_master_configurable"}:
            setattr(new, key, bool(value))
        elif key == "threshold_mb":
            setattr(new, key, float(value) if value is not None else None)
        else:
            setattr(new, key, None if value is None else str(value))
        evidence.append(f"Instructor override: {key}")

    new.source = f"{plan.source}+instructor_override"
    new.confidence = max(float(plan.confidence or 0), 0.99)
    new.evidence = list(plan.evidence) + evidence
    return new, evidence
