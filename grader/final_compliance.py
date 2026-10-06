from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests


META_KEYS = {
    "status", "success", "message", "detail", "count", "total", "meta", "metadata",
    "name", "id", "key", "type", "elapsed", "duration", "timestamp",
}


def _read(path: Path, limit: int = 250_000) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")[:limit]
    except Exception:
        return ""


def _gemini_json(system: str, payload: dict[str, Any], *, timeout: int = 45) -> dict[str, Any] | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    model = os.getenv("GRADER_LLM_MODEL", "gemini-3.1-pro-preview").strip()
    base = os.getenv("GRADER_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model_path = model if model.startswith("models/") else f"models/{model}"
    req = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
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
        out = json.loads("".join(parts).strip() or "{}")
        if isinstance(out, dict):
            out["_model"] = model
            return out
    except Exception:
        return None
    return None


def meaningful_payload(body: Any) -> dict[str, Any]:
    """Prove an API result contains actual data; ask the agent only when deterministic rules cannot decide."""
    evidence: list[str] = []

    def walk(value: Any, path: str = "$", depth: int = 0) -> bool | None:
        if depth > 8:
            return None
        if value is None:
            return False
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            # A zero can still be a real aggregation result, but alone is ambiguous.
            return True if value != 0 else None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return False
            if stripped.lower() in {"ok", "success", "done", "completed", "true", "false"}:
                return None
            evidence.append(f"{path}={stripped[:120]}")
            return True
        if isinstance(value, list):
            if not value:
                return False
            child = [walk(v, f"{path}[{i}]", depth + 1) for i, v in enumerate(value[:20])]
            if any(v is True for v in child):
                return True
            if all(v is False for v in child):
                return False
            return None
        if isinstance(value, dict):
            if not value:
                return False
            decisions = []
            for k, v in value.items():
                if str(k).lower() in META_KEYS or str(k).lower().endswith("_count"):
                    continue
                decisions.append(walk(v, f"{path}.{k}", depth + 1))
            if any(v is True for v in decisions):
                return True
            if decisions and all(v is False for v in decisions):
                return False
            return None
        return None

    deterministic = walk(body)
    if deterministic is not None:
        return {
            "supported": deterministic,
            "source": "deterministic",
            "confidence": 1.0,
            "evidence": evidence[:8],
        }

    agent = _gemini_json(
        "You are an evidence normalizer. Decide only whether this JSON contains an actual business/data result, "
        "not merely metadata/status. Do not grade and do not infer missing data. Return JSON only.",
        {
            "raw_response": body,
            "schema": {"supported": "true|false|null", "evidence_paths": ["json path"], "confidence": "0..1"},
        },
    )
    supported = agent.get("supported") if isinstance(agent, dict) else None
    if supported not in (True, False):
        supported = None
    return {
        "supported": supported,
        "source": "agent" if agent else "undetermined",
        "confidence": float((agent or {}).get("confidence", 0.0) or 0.0),
        "evidence": (agent or {}).get("evidence_paths") or [],
        "model": (agent or {}).get("_model"),
    }


def readme_contract(repo: Path) -> dict[str, Any]:
    readme = _read(repo / "README.md")
    lower = readme.lower()
    deterministic = {
        "installation": bool(re.search(r"install|installation|pip\s+install|تثبيت", lower, re.I)),
        "run": bool(re.search(r"run|تشغيل|python\s+|uvicorn", lower, re.I)),
        "api": bool(re.search(r"fastapi|/health|/docs|uvicorn", lower, re.I)),
        "queries": bool(re.search(r"queries|query|استعلام", lower, re.I)),
        "indexes": bool(re.search(r"indexes?|فهرس|فهارس", lower, re.I)),
        "explain": bool(re.search(r"explain|executionstats", lower, re.I)),
        "aggregations": bool(re.search(r"aggregat|تجميع|تقارير", lower, re.I)),
        "materialized_views": bool(re.search(r"materialized|refresh[-_ ]?mv|عرض مادي|العروض المادية", lower, re.I)),
        "jobs": bool(re.search(r"scheduled|scheduler|cron|job|مهمات|مهام مجدول", lower, re.I)),
    }
    missing = [k for k, v in deterministic.items() if not v]
    source = "deterministic"
    agent_meta: dict[str, Any] | None = None

    if readme.strip() and missing:
        agent_meta = _gemini_json(
            "You inspect README documentation for an academic project. Mark a topic true only if the README "
            "actually documents it. Do not infer from project type. Return JSON only.",
            {
                "readme": readme,
                "topics_to_check": missing,
                "schema": {k: "boolean" for k in missing} | {"evidence": {k: "short exact-supported excerpt" for k in missing}},
            },
        )
        if agent_meta:
            for key in missing:
                if agent_meta.get(key) is True:
                    deterministic[key] = True
            source = "deterministic+agent_fallback"

    env_exists = (repo / ".env.example").is_file() or (repo / "example.env").is_file()
    requirements_exists = (repo / "requirements.txt").is_file()
    covered = sum(1 for v in deterministic.values() if v)
    return {
        "topics": deterministic,
        "covered_topics": covered,
        "required_topics": len(deterministic),
        "env_example": env_exists,
        "requirements": requirements_exists,
        "source": source,
        "agent": agent_meta,
    }


def explain_compliance(repo: Path) -> dict[str, Any]:
    """Check the explicit final requirement: 3 explained queries, before/after indexes, rationale/effect."""
    readme = _read(repo / "README.md")
    py_chunks: list[str] = []
    for path in sorted(repo.rglob("*.py")):
        if any(part in {".git", ".venv", "venv", "__pycache__", "node_modules"} for part in path.parts):
            continue
        py_chunks.append(_read(path, 50_000))
    corpus = "\n".join(py_chunks)
    lower_readme = readme.lower()
    lower_code = corpus.lower()

    explain_occurrences = len(re.findall(r"explain\s*\(|[\"']explain[\"']|\.explain\s*\(", corpus, re.I))
    has_exec_stats = "executionstats" in lower_code or "executionstats" in lower_readme
    before_after = (
        (("before" in lower_readme and "after" in lower_readme) or ("قبل" in readme and "بعد" in readme))
        and ("index" in lower_readme or "فهرس" in readme or "فهارس" in readme)
    )
    rationale = bool(re.search(r"reason|because|impact|effect|سبب|أثر|تأثير|اختيار", readme, re.I))

    deterministic_complete = explain_occurrences >= 3 and has_exec_stats and before_after and rationale
    if deterministic_complete:
        return {
            "supported": True,
            "source": "deterministic",
            "query_count": max(3, explain_occurrences),
            "execution_stats": True,
            "before_after": True,
            "rationale": True,
            "confidence": 1.0,
        }

    # Only unresolved dimensions go to the agent. It may interpret documentation,
    # but every claimed query label must literally occur in the supplied README/code.
    agent = _gemini_json(
        "You extract evidence for a fixed academic requirement. Do not grade. Determine whether the supplied "
        "README/code documents or implements explain('executionStats') for at least three distinct practical "
        "queries before and after indexes, and explains index rationale/effect. Do not invent query names. Return JSON only.",
        {
            "readme": readme,
            "code_excerpt": corpus[:120_000],
            "deterministic": {
                "explain_occurrences": explain_occurrences,
                "execution_stats": has_exec_stats,
                "before_after": before_after,
                "rationale": rationale,
            },
            "schema": {
                "query_names": ["string"],
                "query_count": "integer",
                "execution_stats": "boolean",
                "before_after": "boolean",
                "rationale": "boolean",
                "evidence": ["short supported fact"],
                "confidence": "0..1",
            },
        },
    )
    if not agent:
        return {
            "supported": False,
            "source": "deterministic",
            "query_count": explain_occurrences,
            "execution_stats": has_exec_stats,
            "before_after": before_after,
            "rationale": rationale,
            "confidence": 0.6,
        }

    raw = (readme + "\n" + corpus).lower()
    names = [str(x).strip() for x in (agent.get("query_names") or []) if str(x).strip()]
    grounded_names = [x for x in names if x.lower() in raw]
    count = max(explain_occurrences, len(set(grounded_names)), int(agent.get("query_count") or 0))
    # Cap an ungrounded numeric claim unless names/evidence support it.
    if int(agent.get("query_count") or 0) > max(explain_occurrences, len(set(grounded_names))) and len(grounded_names) < 3:
        count = max(explain_occurrences, len(set(grounded_names)))
    result = {
        "query_count": count,
        "execution_stats": bool(agent.get("execution_stats") or has_exec_stats),
        "before_after": bool(agent.get("before_after") or before_after),
        "rationale": bool(agent.get("rationale") or rationale),
    }
    result["supported"] = all([
        result["query_count"] >= 3,
        result["execution_stats"],
        result["before_after"],
        result["rationale"],
    ])
    result.update({
        "source": "deterministic+agent_fallback",
        "confidence": float(agent.get("confidence", 0.0) or 0.0),
        "query_names": grounded_names,
        "evidence": agent.get("evidence") or [],
        "model": agent.get("_model"),
    })
    return result


START_KEYS = {"start", "started", "started_at", "start_time", "started_time", "run_started_at"}
END_KEYS = {"end", "ended", "ended_at", "end_time", "finished_at", "completed_at", "run_ended_at"}
STATUS_KEYS = {"status", "state", "success", "result_status", "execution_status"}
RESULT_KEYS = {"result", "output", "message", "details", "summary", "records", "processed"}


def job_log_compliance(values: list[Any]) -> dict[str, Any]:
    """Check start/end/status/result fields using deterministic aliases, then semantic fallback if ambiguous."""
    def keys_recursive(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for k, v in value.items():
                found.add(str(k).lower())
                found |= keys_recursive(v)
        elif isinstance(value, list):
            for item in value[:20]:
                found |= keys_recursive(item)
        return found

    keys = set()
    for value in values:
        keys |= keys_recursive(value)

    deterministic = {
        "start_time": bool(keys & START_KEYS),
        "end_time": bool(keys & END_KEYS),
        "status": bool(keys & STATUS_KEYS),
        "result": bool(keys & RESULT_KEYS),
    }
    if all(deterministic.values()):
        return {**deterministic, "supported": True, "source": "deterministic", "confidence": 1.0}

    agent = _gemini_json(
        "You normalize job execution evidence. Determine only whether the supplied JSON/documents contain "
        "equivalent fields for execution start time, end time, success/failure status, and result/output. "
        "Do not infer missing values. Return JSON only.",
        {
            "values": values[:20],
            "already_detected": deterministic,
            "schema": {
                "start_time": "boolean", "end_time": "boolean", "status": "boolean", "result": "boolean",
                "evidence_paths": ["json path"], "confidence": "0..1",
            },
        },
    )
    if agent:
        for k in deterministic:
            if agent.get(k) is True:
                deterministic[k] = True
    return {
        **deterministic,
        "supported": all(deterministic.values()),
        "source": "deterministic+agent_fallback" if agent else "deterministic",
        "confidence": float((agent or {}).get("confidence", 0.7) or 0.0),
        "evidence": (agent or {}).get("evidence_paths") or [],
        "model": (agent or {}).get("_model"),
    }
