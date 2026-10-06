from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

from datasets.prepare_hidden_tests import ensure_prepared
from grader.agent_analyzer import analyze_final_repository_with_llm
from grader.final_discovery import discover_final_plan
from grader.final_runtime import run_final_suite
from grader.oracle import HiddenOracle
from grader.plan_resolution import resolve_execution_plan, resolve_execution_plan_after_failure
from grader.report import write_report
from grader.repository import current_commit
from grader.sandbox import DockerSandbox, SandboxConfig, docker_available
from grader.sandbox_runtime import _copy_input_view, run_behavioral_suite
from grader.static_checks import static_checks

from evaluate import _runtime_command_failure_context
from evaluate_final import (
    RUBRIC as FINAL_RUBRIC,
    final_runtime_failure_context,
    safe_workspace,
    write_final_report,
)


def find_submission(csv_path: Path, project_id: str) -> dict[str, str]:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("project_id") == project_id:
                return row
    raise KeyError(project_id)


def _counts(runtime: dict[str, Any] | None) -> dict[str, int]:
    runtime = runtime or {}
    counts = runtime.get("assertion_counts") or {}
    return {
        k: int(counts.get(k, 0) or 0)
        for k in ("PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIP")
    }


def _write_unified_report(out_root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    out = out_root / payload["project_id"]
    out.mkdir(parents=True, exist_ok=True)
    js = out / "result.json"
    md = out / "evaluation.md"
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    mid = payload.get("midterm") or {}
    fin = payload.get("final") or {}
    env = payload.get("environment") or {}
    lines = [
        f"# التقييم الموحد — {payload['project_id']} — {payload.get('students') or ''}",
        "",
        f"- Commit المجمد: {payload.get('commit_sha') or 'unknown'}",
        f"- Mode: {payload.get('mode')}",
        f"- Build count: {env.get('build_count')}",
        f"- Sandbox start count: {env.get('sandbox_start_count')}",
        f"- Shared image: {env.get('image') or 'n/a'}",
        f"- Shared Mongo: {env.get('mongo') or 'n/a'}",
        "",
        "## استقلال مراحل التقييم",
        "",
        "- بيئة Python ومتطلبات الطالب تُبنى مرة واحدة.",
        "- MongoDB/Sandbox يبدأ مرة واحدة.",
        "- اختبارات النصفي والنهائي منفصلة في النتائج.",
        "- يتم Reset لحالة قاعدة البيانات داخل الـsuite قبل الاختبارات المطلوبة.",
        "- Teacher oracle لا يُركب داخل حاوية الطالب.",
        "",
        "## النصفي — 18 درجة",
        "",
        f"- Runtime status: {(mid.get('runtime') or {}).get('status', 'NOT_RUN')}",
        f"- Assertion counts: {json.dumps(_counts(mid.get('runtime')), ensure_ascii=False)}",
        f"- Report: {mid.get('report_md') or 'not generated'}",
        "",
        "## النهائي — 7 درجات",
        "",
        f"- Runtime status: {(fin.get('runtime') or {}).get('status', 'NOT_RUN')}",
        f"- Assertion counts: {json.dumps(_counts(fin.get('runtime')), ensure_ascii=False)}",
        f"- Report: {fin.get('report_md') or 'not generated'}",
        "",
        "## ملاحظات العدالة",
        "",
        "- PASS/FAIL في النصفي والنهائي لا تختلط بين المرحلتين.",
        "- BLOCKED/INCONCLUSIVE لا يتحول إلى صفر تلقائيًا.",
        "- الوكيل لا يعطي درجة؛ يستخدم فقط عند غياب قاعدة حتمية أو وجود غموض موثق.",
        "- المناقشة في النهائي تبقى يدوية.",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    return js, md


def main() -> int:
    p = argparse.ArgumentParser(description="Unified Big Data grader: one environment, separate midterm/final suites")
    p.add_argument("--project", required=True)
    p.add_argument("--submissions", default="frozen_submissions.csv")
    p.add_argument("--workspace", required=True)
    p.add_argument("--mode", choices=["all", "midterm", "final"], default="all")
    p.add_argument("--reports", default="reports_unified")
    p.add_argument("--midterm-reports", default="reports")
    p.add_argument("--final-reports", default="reports_final")
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--network-profile", choices=["isolated", "compat"], default="isolated")
    p.add_argument("--cpus", type=float, default=2.0)
    p.add_argument("--memory", default="6g")
    p.add_argument("--confidence-threshold", type=float, default=0.80)
    p.add_argument("--no-ai", action="store_true")
    p.add_argument("--allow-low-confidence", action="store_true")
    p.add_argument("--plan-b", action="store_true", help="Enable incremental/lookback midterm extension")
    p.add_argument("--override")
    p.add_argument("--overrides-dir", default="overrides")
    p.add_argument("--keep-sandbox", action="store_true")
    args = p.parse_args()

    base = Path(__file__).resolve().parent
    row = find_submission(base / args.submissions, args.project)
    repo = safe_workspace(Path(args.workspace), row)
    project_id = row["project_id"]

    override_path = args.override
    if not override_path:
        candidate = base / args.overrides_dir / f"{project_id}.yaml"
        if candidate.exists():
            override_path = str(candidate)

    plan, resolution = resolve_execution_plan(
        repo,
        use_ai=not args.no_ai,
        confidence_threshold=args.confidence_threshold,
        override_path=override_path,
    )
    deterministic_final_plan = discover_final_plan(repo)
    if deterministic_final_plan.get("requires_agent") and not args.no_ai:
        final_plan, final_resolution = analyze_final_repository_with_llm(
            repo,
            deterministic_final_plan,
            mode="readme",
        )
    else:
        final_plan = deterministic_final_plan
        final_resolution = {
            "status": "NOT_NEEDED" if not deterministic_final_plan.get("requires_agent") else "AI_DISABLED",
            "provider": None,
            "analysis_level": "deterministic",
            "confidence": deterministic_final_plan.get("confidence"),
            "reason": (
                "README/source evidence resolved a valid FastAPI target deterministically."
                if not deterministic_final_plan.get("requires_agent")
                else "AI disabled; deterministic evidence remains unresolved/ambiguous."
            ),
            "files_sent": [],
        }

    static = static_checks(repo)
    commit_sha = row.get("commit_sha") or current_commit(repo) or ""
    hidden = ensure_prepared()
    oracle = HiddenOracle(hidden / "teacher_key.json", hidden / "teacher_manifest.csv")

    shared_mount = base / "sandboxes" / project_id / "unified_input"
    if shared_mount.exists():
        shutil.rmtree(shared_mount)
    _copy_input_view(hidden, oracle, shared_mount)

    sandbox_cfg = SandboxConfig(
        cpus=args.cpus,
        memory=args.memory,
        timeout_seconds=args.timeout,
        network_profile=args.network_profile,
    )
    sb = DockerSandbox(base, f"{project_id}-unified", repo, shared_mount, sandbox_cfg)

    environment: dict[str, Any] = {
        "build_count": 0,
        "sandbox_start_count": 0,
        "image": sb.image_name,
        "mongo": sb.mongo_name,
        "network": sb.network,
        "network_profile": args.network_profile,
        "shared": True,
    }
    midterm_runtime: dict[str, Any] | None = None
    final_runtime: dict[str, Any] | None = None
    midterm_recovery: dict[str, Any] | None = None
    final_recovery: dict[str, Any] | None = None

    ok, detail = docker_available()
    if not ok:
        environment["status"] = "INFRA_ERROR"
        environment["error"] = f"Docker unavailable: {detail}"
    else:
        try:
            build = sb.build()
            environment["build_count"] = 1
            environment["build"] = build
            if not build.get("ok"):
                environment["status"] = "DEPENDENCY_BUILD_ERROR"
            else:
                start = sb.start()
                environment["sandbox_start_count"] = 1
                environment["sandbox_start"] = start
                environment["status"] = "READY"

                if args.mode in {"all", "midterm"}:
                    if resolution.get("requires_manual_review") and not args.allow_low_confidence:
                        midterm_runtime = {
                            "status": "MANUAL_REVIEW_REQUIRED",
                            "reason": "Execution-plan confidence is below threshold. No midterm student command was executed.",
                            "confidence": resolution.get("confidence"),
                            "threshold": args.confidence_threshold,
                        }
                    else:
                        midterm_runtime = run_behavioral_suite(
                            base=base,
                            project_id=project_id,
                            repo=repo,
                            hidden_dir=hidden,
                            oracle=oracle,
                            plan=plan,
                            sandbox_config=sandbox_cfg,
                            timeout=args.timeout,
                            plan_b=args.plan_b,
                            keep_sandbox=True,
                            shared_sandbox=sb,
                            student_inputs_dir=shared_mount,
                            manage_sandbox=False,
                        )
                        failure_context = _runtime_command_failure_context(midterm_runtime)
                        if failure_context and not args.no_ai:
                            recovered_plan, recovery = resolve_execution_plan_after_failure(
                                repo,
                                plan,
                                failure_context,
                                confidence_threshold=args.confidence_threshold,
                                override_path=override_path,
                            )
                            changed = (
                                recovered_plan.ingest_command != plan.ingest_command
                                or recovered_plan.setup_command != plan.setup_command
                            )
                            midterm_recovery = {
                                **recovery,
                                "original_command": plan.ingest_command,
                                "recovered_command": recovered_plan.ingest_command,
                                "command_changed": changed,
                            }
                            if changed and recovered_plan.ingest_command:
                                plan = recovered_plan
                                midterm_runtime = run_behavioral_suite(
                                    base=base,
                                    project_id=project_id,
                                    repo=repo,
                                    hidden_dir=hidden,
                                    oracle=oracle,
                                    plan=plan,
                                    sandbox_config=sandbox_cfg,
                                    timeout=args.timeout,
                                    plan_b=args.plan_b,
                                    keep_sandbox=True,
                                    shared_sandbox=sb,
                                    student_inputs_dir=shared_mount,
                                    manage_sandbox=False,
                                )

                if args.mode in {"all", "final"}:
                    final_runtime = run_final_suite(
                        base=base,
                        project_id=project_id,
                        repo=repo,
                        hidden_dir=shared_mount,
                        execution_plan=plan,
                        final_plan=final_plan,
                        sandbox_config=sandbox_cfg,
                        timeout=args.timeout,
                        keep_sandbox=True,
                        shared_sandbox=sb,
                        manage_sandbox=False,
                    )
                    failure_context = final_runtime_failure_context(final_runtime)
                    if failure_context and not args.no_ai:
                        recovered_final_plan, recovery = analyze_final_repository_with_llm(
                            repo,
                            deterministic_final_plan,
                            mode="targeted",
                            failure_context=failure_context,
                        )
                        changed = recovered_final_plan.get("api_target") != final_plan.get("api_target")
                        final_recovery = {
                            **recovery,
                            "original_api_target": final_plan.get("api_target"),
                            "recovered_api_target": recovered_final_plan.get("api_target"),
                            "target_changed": changed,
                        }
                        if changed and recovered_final_plan.get("api_target"):
                            final_plan = recovered_final_plan
                            final_runtime = run_final_suite(
                                base=base,
                                project_id=project_id,
                                repo=repo,
                                hidden_dir=shared_mount,
                                execution_plan=plan,
                                final_plan=final_plan,
                                sandbox_config=sandbox_cfg,
                                timeout=args.timeout,
                                keep_sandbox=True,
                                shared_sandbox=sb,
                                manage_sandbox=False,
                            )
        except Exception as exc:
            environment["status"] = "INFRA_OR_ORCHESTRATION_ERROR"
            environment["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if not args.keep_sandbox:
                try:
                    sb.cleanup()
                except Exception as exc:
                    environment.setdefault("cleanup_warnings", []).append(str(exc))

    if args.mode in {"all", "midterm"}:
        if midterm_runtime is None:
            midterm_runtime = {
                "status": "BLOCKED_BY_ENVIRONMENT",
                "reason": environment.get("status"),
                "error": environment.get("error"),
            }
        midterm_payload = {
            "grader_version": "4.3-unified",
            "project_id": project_id,
            "students": row.get("students", ""),
            "student_nos": row.get("student_nos", ""),
            "repo_url": row.get("repo_url", ""),
            "commit_sha": commit_sha,
            "repository_path": str(repo),
            "plan_resolution": resolution,
            "execution_plan": plan.to_dict(),
            "execution_recovery": midterm_recovery,
            "static_checks": static,
            "runtime": midterm_runtime,
            "shared_environment": environment,
        }
        _, midterm_md = write_report(base / args.midterm_reports, project_id, midterm_payload)
    else:
        midterm_payload = {}
        midterm_md = None

    if args.mode in {"all", "final"}:
        if final_runtime is None:
            final_runtime = {
                "status": "BLOCKED_BY_ENVIRONMENT",
                "reason": environment.get("status"),
                "error": environment.get("error"),
                "assertions": [],
            }
        final_payload = {
            "grader_version": "final-v1.2-unified",
            "project_id": project_id,
            "students": row.get("students", ""),
            "student_nos": row.get("student_nos", ""),
            "repo_url": row.get("repo_url", ""),
            "commit_sha": commit_sha,
            "repository_path": str(repo),
            "execution_plan": plan.to_dict(),
            "final_plan": final_plan,
            "final_plan_resolution": final_resolution,
            "final_execution_recovery": final_recovery,
            "rubric": FINAL_RUBRIC,
            "runtime": final_runtime,
            "shared_environment": environment,
        }
        _, final_md = write_final_report(base / args.final_reports, final_payload)
    else:
        final_payload = {}
        final_md = None

    unified = {
        "grader_version": "4.3-unified",
        "project_id": project_id,
        "students": row.get("students", ""),
        "student_nos": row.get("student_nos", ""),
        "repo_url": row.get("repo_url", ""),
        "commit_sha": commit_sha,
        "mode": args.mode,
        "environment": environment,
        "repository_analysis": {
            "midterm_plan_resolution": resolution,
            "final_plan_resolution": final_resolution,
        },
        "midterm": {
            "max_points": 18.0,
            "scoring_status": "RUBRIC_DISABLED",
            "note": "Runtime evidence is produced, but midterm auto-scoring stays disabled until the official 18-point rubric is activated.",
            "runtime": midterm_runtime,
            "report_md": str(midterm_md) if midterm_md else None,
        } if args.mode in {"all", "midterm"} else None,
        "final": {
            "max_points": 7.0,
            "rubric_status": "ACTIVE",
            "runtime": final_runtime,
            "category_summary": final_payload.get("category_summary") if final_payload else None,
            "report_md": str(final_md) if final_md else None,
        } if args.mode in {"all", "final"} else None,
    }
    result_json, result_md = _write_unified_report(base / args.reports, unified)

    print(json.dumps({
        "project_id": project_id,
        "commit_sha": commit_sha,
        "mode": args.mode,
        "environment_status": environment.get("status"),
        "build_count": environment.get("build_count"),
        "sandbox_start_count": environment.get("sandbox_start_count"),
        "midterm_status": (midterm_runtime or {}).get("status") if args.mode in {"all", "midterm"} else None,
        "final_status": (final_runtime or {}).get("status") if args.mode in {"all", "final"} else None,
        "report": str(result_md),
        "result_json": str(result_json),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
