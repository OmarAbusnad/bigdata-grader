from __future__ import annotations
from pathlib import Path

from .agent_analyzer import analyze_repository_with_llm
from .discovery import discover_execution_plan
from .overrides import apply_instructor_override, load_instructor_override


def resolve_execution_plan(
    repo: Path,
    *,
    use_ai: bool = True,
    confidence_threshold: float = 0.80,
    override_path: str | Path | None = None,
):
    heuristic = discover_execution_plan(repo)
    override = load_instructor_override(override_path)

    if not use_ai:
        plan, override_evidence = apply_instructor_override(heuristic, override)
        conf = 0.99 if override else (0.55 if heuristic.ingest_command else 0.20)
        return plan, {
            "status": "INSTRUCTOR_OVERRIDE" if override else "HEURISTIC_ONLY",
            "confidence": conf,
            "requires_manual_review": conf < confidence_threshold or not bool(plan.ingest_command),
            "heuristic_plan": heuristic.to_dict(),
            "override_path": str(override_path) if override else None,
            "evidence": override_evidence,
        }

    plan, agent = analyze_repository_with_llm(repo, heuristic)
    conf = float(agent.get("confidence", 0.0) or 0.0)
    if agent.get("status") != "OK":
        conf = 0.70 if heuristic.ingest_command else 0.20

    plan, override_evidence = apply_instructor_override(plan, override)
    if override:
        conf = max(conf, 0.99)

    meta = {
        **agent,
        "confidence": conf,
        "requires_manual_review": conf < confidence_threshold or not bool(plan.ingest_command),
        "confidence_threshold": confidence_threshold,
        "heuristic_plan": heuristic.to_dict(),
        "resolved_plan": plan.to_dict(),
        "override_path": str(override_path) if override else None,
    }
    if override_evidence:
        meta["evidence"] = list(meta.get("evidence") or []) + override_evidence
    return plan, meta
