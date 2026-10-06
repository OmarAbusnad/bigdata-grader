from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from grader.discovery import discover_execution_plan
from grader.final_discovery import discover_final_plan
from grader.final_runtime import run_final_suite
from grader.agent_analyzer import analyze_final_repository_with_llm
from grader.sandbox import SandboxConfig, docker_available


RUBRIC = {
    "queries_indexes_explain": 1.5,
    "aggregations": 1.5,
    "materialized_views": 1.5,
    "scheduled_jobs": 1.0,
    "unified_api": 0.75,
    "github_readme": 0.50,
    "discussion_understanding": 0.25,
}


def find_submission(csv_path: Path, project_id: str) -> dict:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("project_id") == project_id:
                return row
    raise KeyError(project_id)


def safe_workspace(root: Path, row: dict) -> Path:
    repo = root.resolve()
    subdir = (row.get("workspace_subdir") or "").strip().replace("\\", "/")
    if not subdir:
        return repo
    subpath = Path(subdir)
    if subpath.is_absolute() or ".." in subpath.parts:
        raise ValueError(f"Unsafe workspace_subdir: {subdir}")
    candidate = (repo / subpath).resolve()
    if repo not in candidate.parents and candidate != repo:
        raise ValueError(f"workspace_subdir escapes repository: {subdir}")
    if not candidate.exists() or not candidate.is_dir():
        raise FileNotFoundError(f"workspace_subdir not found: {subdir}")
    return candidate


def group_assertions(assertions: list[dict]) -> dict[str, list[dict]]:
    groups = {k: [] for k in RUBRIC}
    for a in assertions:
        key = str(a.get("key") or "")
        if key.startswith("final.queries.") or key.startswith("final.indexes."):
            groups["queries_indexes_explain"].append(a)
        elif key.startswith("final.aggregations."):
            groups["aggregations"].append(a)
        elif key.startswith("final.mv."):
            groups["materialized_views"].append(a)
        elif key.startswith("final.jobs."):
            groups["scheduled_jobs"].append(a)
        elif key.startswith("final.api."):
            groups["unified_api"].append(a)
        elif key in {"final.github_readme", "final.dependencies"}:
            groups["github_readme"].append(a)
        elif key == "final.discussion":
            groups["discussion_understanding"].append(a)
    return groups


def category_status(items: list[dict]) -> str:
    if not items:
        return "INCONCLUSIVE"
    verdicts = [x.get("verdict") for x in items]
    if "ERROR" in verdicts:
        return "ERROR"
    if all(v == "PASS" for v in verdicts):
        return "PASS"
    if all(v == "FAIL" for v in verdicts):
        return "FAIL"
    if any(v == "PASS" for v in verdicts):
        return "PARTIAL"
    if any(v == "INCONCLUSIVE" for v in verdicts):
        return "INCONCLUSIVE"
    return "FAIL"


def write_final_report(out_root: Path, payload: dict) -> tuple[Path, Path]:
    pid = payload["project_id"]
    out = out_root / pid
    out.mkdir(parents=True, exist_ok=True)
    js = out / "result.json"
    md = out / "evaluation.md"

    runtime = payload.get("runtime") or {}
    grouped = group_assertions(runtime.get("assertions") or [])
    categories = {
        key: {"weight": weight, "status": category_status(grouped.get(key) or [])}
        for key, weight in RUBRIC.items()
    }
    payload["category_summary"] = categories
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    students = payload.get("students") or "غير متوفر"
    nos = payload.get("student_nos") or "غير متوفر"
    lines = [
        f"# تقرير متطلبات النهائي — {pid} — {students}",
        "",
        f"- **رقم المشروع:** {pid}",
        f"- **اسم الطالب/الطلاب:** {students}",
        f"- **الرقم/الأرقام الجامعية:** {nos}",
        f"- **Commit المجمد:** {payload.get('commit_sha') or 'unknown'}",
        f"- **Runtime status:** {runtime.get('status', 'NOT_RUN')}",
        "",
        "## ملخص محاور النهائي",
        "",
        "| المحور | الوزن | الحالة |",
        "|---|---:|---|",
    ]
    labels = {
        "queries_indexes_explain": "Queries + Indexes + Explain",
        "aggregations": "Aggregations",
        "materialized_views": "Materialized Views",
        "scheduled_jobs": "Scheduled Jobs",
        "unified_api": "Unified API",
        "github_readme": "GitHub + README",
        "discussion_understanding": "Discussion / Understanding",
    }
    for key, meta in categories.items():
        lines.append(f"| {labels[key]} | {meta['weight']} | {meta['status']} |")

    lines += ["", "> هذا التقرير يعرض Evidence وحالة الاختبارات. لا يحوّل PARTIAL/INCONCLUSIVE إلى صفر آلي، ودرجة المناقشة 0.25 تبقى يدوية.", ""]
    lines += ["## تفاصيل الاختبارات", ""]
    for a in runtime.get("assertions") or []:
        icon = "✅" if a.get("verdict") == "PASS" else "❌" if a.get("verdict") == "FAIL" else "⚠️"
        lines.append(f"- {icon} **{a.get('label')}** — {a.get('verdict')}")
        lines.append(f"  - expected: {a.get('expected')}")
        lines.append(f"  - actual: {a.get('actual')}")
        for ev in (a.get("evidence") or [])[:3]:
            if ev:
                lines.append(f"  - evidence: {str(ev)[:1200]}")
        if a.get("note"):
            lines.append(f"  - note: {a['note']}")

    lines += ["", "## Final discovery", "", json.dumps(payload.get("final_plan") or {}, ensure_ascii=False, indent=2)]
    md.write_text("\n".join(lines), encoding="utf-8")
    return js, md


def final_runtime_failure_context(runtime: dict | None) -> str:
    if not isinstance(runtime, dict):
        return ""
    probe = runtime.get("probe") or {}
    if probe.get("server_ready"):
        return ""
    service = runtime.get("service_run") or {}
    parts = [
        f"status={runtime.get('status')}",
        f"returncode={service.get('returncode')}",
        f"timed_out={service.get('timed_out')}",
        "stdout_tail:",
        str(service.get("stdout_tail") or "")[-6000:],
        "stderr_tail:",
        str(service.get("stderr_tail") or "")[-6000:],
        "probe:",
        json.dumps(probe, ensure_ascii=False)[:5000],
    ]
    return "\n".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description="Behavioral grader for the 7-point final extension")
    p.add_argument("--project", required=True)
    p.add_argument("--submissions", default="frozen_submissions.csv")
    p.add_argument("--workspace", required=True)
    p.add_argument("--reports", default="reports_final")
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--network-profile", choices=["isolated", "compat"], default="isolated")
    p.add_argument("--cpus", type=float, default=2.0)
    p.add_argument("--memory", default="6g")
    p.add_argument("--keep-sandbox", action="store_true")
    args = p.parse_args()

    base = Path(__file__).resolve().parent
    row = find_submission(base / args.submissions, args.project)
    repo = safe_workspace(Path(args.workspace), row)
    execution_plan = discover_execution_plan(repo)
    deterministic_final_plan = discover_final_plan(repo)
    final_plan, final_agent = analyze_final_repository_with_llm(
        repo,
        deterministic_final_plan,
        mode="readme",
    )

    payload = {
        "grader_version": "final-v1.1-readme-first",
        "project_id": args.project,
        "students": row.get("students", ""),
        "student_nos": row.get("student_nos", ""),
        "repo_url": row.get("repo_url", ""),
        "commit_sha": row.get("commit_sha", ""),
        "repository_path": str(repo),
        "execution_plan": execution_plan.to_dict(),
        "final_plan": final_plan,
        "final_plan_resolution": final_agent,
        "rubric": RUBRIC,
        "runtime": None,
    }

    ok, detail = docker_available()
    if not ok:
        payload["runtime"] = {"status": "INFRA_ERROR", "error": f"Docker unavailable: {detail}", "assertions": []}
    else:
        from datasets.prepare_hidden_tests import ensure_prepared
        hidden = ensure_prepared()
        sandbox_cfg = SandboxConfig(
            cpus=args.cpus,
            memory=args.memory,
            timeout_seconds=args.timeout,
            network_profile=args.network_profile,
        )
        payload["runtime"] = run_final_suite(
            base=base,
            project_id=args.project,
            repo=repo,
            hidden_dir=hidden,
            execution_plan=execution_plan,
            final_plan=final_plan,
            sandbox_config=sandbox_cfg,
            timeout=args.timeout,
            keep_sandbox=args.keep_sandbox,
        )

        # Level 2: only after the README-derived startup target failed.
        failure_context = final_runtime_failure_context(payload["runtime"])
        if failure_context:
            recovered_plan, recovery = analyze_final_repository_with_llm(
                repo,
                deterministic_final_plan,
                mode="targeted",
                failure_context=failure_context,
            )
            changed = recovered_plan.get("api_target") != final_plan.get("api_target")
            payload["final_execution_recovery"] = {
                **recovery,
                "original_api_target": final_plan.get("api_target"),
                "recovered_api_target": recovered_plan.get("api_target"),
                "target_changed": changed,
            }
            if changed and recovered_plan.get("api_target"):
                payload["runtime_first_attempt"] = payload["runtime"]
                final_plan = recovered_plan
                payload["final_plan"] = final_plan
                payload["runtime"] = run_final_suite(
                    base=base,
                    project_id=args.project,
                    repo=repo,
                    hidden_dir=hidden,
                    execution_plan=execution_plan,
                    final_plan=final_plan,
                    sandbox_config=sandbox_cfg,
                    timeout=args.timeout,
                    keep_sandbox=args.keep_sandbox,
                )

    result_json, result_md = write_final_report(Path(args.reports), payload)
    print(json.dumps({
        "project_id": args.project,
        "students": row.get("students", ""),
        "commit_sha": row.get("commit_sha", ""),
        "runtime_status": (payload.get("runtime") or {}).get("status"),
        "assertion_counts": (payload.get("runtime") or {}).get("assertion_counts"),
        "report": str(result_md),
        "result_json": str(result_json),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
