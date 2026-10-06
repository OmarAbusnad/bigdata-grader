from __future__ import annotations

import json
import os
from typing import Any

import requests


CONTAINER_KEYS = {
    "queries": ("queries", "items", "data", "results", "available_queries", "practical_queries"),
    "aggregations": ("aggregations", "items", "data", "results", "reports", "aggregation_reports"),
    "jobs": ("jobs", "items", "data", "results", "scheduled_jobs", "tasks"),
}


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        v = str(value).strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _declared_count(value: Any, kind: str) -> int | None:
    if not isinstance(value, dict):
        return None
    keys = [
        f"{kind}_count", "count", "total", "total_count", "number",
    ]
    if kind == "aggregations":
        keys += ["reports_count", "aggregation_count"]
    if kind == "jobs":
        keys += ["jobs_count", "scheduled_jobs_count"]
    if kind == "queries":
        keys += ["queries_count", "query_count"]
    for key in keys:
        got = value.get(key)
        if isinstance(got, int) and got >= 0:
            return got
    return None


def _names_from(value: Any, kind: str, *, depth: int = 0) -> list[str]:
    if depth > 6:
        return []

    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("name", "id", "key", "job", "query", "report", "aggregation"):
                    got = item.get(key)
                    if isinstance(got, (str, int)):
                        out.append(str(got))
                        break
                else:
                    out.extend(_names_from(item, kind, depth=depth + 1))
        return _dedupe(out)

    if not isinstance(value, dict):
        return []

    # First honor known semantic containers.
    for key in CONTAINER_KEYS.get(kind, ()):
        if key in value:
            child = value[key]
            if isinstance(child, dict):
                # A response like {"queries": {"q1": {...}, "q2": {...}}}
                # uses object keys as the canonical names.
                keys = [
                    str(k) for k, v in child.items()
                    if not str(k).lower().endswith("_count")
                    and str(k).lower() not in {"count", "total", "meta", "metadata", "status", "message"}
                    and isinstance(v, (dict, list, str, int, float, bool, type(None)))
                ]
                if keys:
                    return _dedupe(keys)
            got = _names_from(child, kind, depth=depth + 1)
            if got:
                return got

    # Common object-map fallback: only when values look like definitions.
    meta = {"count", "total", "status", "message", "detail", "success", "meta", "metadata"}
    candidates = [
        str(k) for k, v in value.items()
        if str(k).lower() not in meta
        and not str(k).lower().endswith("_count")
        and isinstance(v, dict)
    ]
    if len(candidates) >= 2:
        return _dedupe(candidates)

    # Search nested objects as a final deterministic fallback.
    for child in value.values():
        got = _names_from(child, kind, depth=depth + 1)
        if got:
            return got
    return []


def deterministic_normalize(kind: str, body: Any) -> dict[str, Any]:
    names = _names_from(body, kind)
    declared = _declared_count(body, kind)
    return {
        "kind": kind,
        "names": names,
        "detected_count": len(names),
        "declared_count": declared,
        "source": "deterministic",
        "confidence": 1.0 if names else (0.8 if declared is not None else 0.0),
        "response_shape": type(body).__name__,
        "evidence_paths": [],
    }


def _validate_agent_names(body: Any, names: list[Any]) -> list[str]:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).lower()
    out: list[str] = []
    for value in names:
        name = str(value).strip()
        if name and name.lower() in raw:
            out.append(name)
    return _dedupe(out)


def agent_normalize(kind: str, body: Any, *, timeout: int = 45) -> dict[str, Any] | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("GRADER_LLM_MODEL", "gemini-3.1-pro-preview").strip()
    base = os.getenv("GRADER_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model_path = model if model.startswith("models/") else f"models/{model}"

    system = (
        "You normalize heterogeneous JSON API responses for an academic grader. "
        "Do not grade, infer missing functionality, or invent names. "
        "Return only facts directly supported by the supplied JSON. "
        "For object maps, the object keys may be item names. Return JSON only."
    )
    user = {
        "kind": kind,
        "raw_response": body,
        "schema": {
            "names": ["string"],
            "declared_count": "integer|null",
            "detected_count": "integer",
            "response_shape": "short string",
            "evidence_paths": ["JSON path"],
            "confidence": "0..1",
        },
    }
    req = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(user, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0},
    }
    try:
        r = requests.post(
            f"{base}/{model_path}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=req,
            timeout=timeout,
        )
        r.raise_for_status()
        parts: list[str] = []
        for candidate in r.json().get("candidates", []):
            for part in (candidate.get("content") or {}).get("parts", []):
                if isinstance(part.get("text"), str):
                    parts.append(part["text"])
        data = json.loads("".join(parts).strip() or "{}")
        names = _validate_agent_names(body, data.get("names") or [])
        declared = data.get("declared_count")
        if not isinstance(declared, int) or declared < 0:
            declared = None
        confidence = float(data.get("confidence", 0.0) or 0.0)
        confidence = min(max(confidence, 0.0), 1.0)
        return {
            "kind": kind,
            "names": names,
            "detected_count": len(names),
            "declared_count": declared,
            "source": "agent",
            "model": model,
            "confidence": confidence,
            "response_shape": str(data.get("response_shape") or type(body).__name__),
            "evidence_paths": data.get("evidence_paths") if isinstance(data.get("evidence_paths"), list) else [],
        }
    except Exception as exc:
        return {
            "kind": kind,
            "names": [],
            "detected_count": 0,
            "declared_count": None,
            "source": "agent_error",
            "confidence": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
            "response_shape": type(body).__name__,
            "evidence_paths": [],
        }


def normalize_named_response(kind: str, body: Any) -> dict[str, Any]:
    """Deterministic first; semantic agent only when the shape is not understood."""
    deterministic = deterministic_normalize(kind, body)
    if deterministic["names"]:
        return deterministic
    agent = agent_normalize(kind, body)
    if agent and (agent.get("names") or agent.get("declared_count") is not None):
        return agent
    return deterministic


def normalize_probe(probe: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind in ("queries", "aggregations", "jobs"):
        wrapper = probe.get(kind) or {}
        body = wrapper.get("body") if isinstance(wrapper, dict) else None
        out[kind] = normalize_named_response(kind, body)
    return out
