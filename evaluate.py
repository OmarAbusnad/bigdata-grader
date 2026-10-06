from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from grader.plan_resolution import resolve_execution_plan, resolve_execution_plan_after_failure
from grader.repository import clone_repository, current_commit
from grader.report import write_report
from grader.static_checks import static_checks
from grader.oracle import HiddenOracle
from grader.sandbox import SandboxConfig, docker_available
from grader.sandbox_runtime import run_behavioral_suite


def find_submission(csv_path: Path, project_id: str) -> dict:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("project_id") == project_id:
                return row
    raise KeyError(project_id)


def _runtime_command_failure_context(runtime: dict | None) -> str:
    """Return failure evidence only when the first documented execution attempt failed."""
    if not isinstance(runtime, dict):
        return ""
    if runtime.get("status") in {"DEPENDENCY_BUILD_ERROR", "INFRA_ERROR", "INFRA_OR_RUNTIME_ERROR"}:
        return ""
    root_cause = str(runtime.get("root_cause") or "")
    if root_cause and root_cause not in {"GRADER_DISCOVERY_FAILURE", "AMBIGUOUS", "EXECUTION_INCONCLUSIVE"}:
        return ""
    cases = runtime.get("cases") or []
    if not cases:
        return ""
    first = cases[0] if isinstance(cases[0], dict) else {}
    run = first.get("run") or {}
    rc = run.get("returncode")
    timed_out = bool(run.get("timed_out"))
    if rc in (None, 0) and not timed_out:
        return ""
    return "\n".join([
        f"case={first.get('name')}",
        f"command={first.get('command')}",
        f"returncode={rc}",
        f"timed_out={timed_out}",
        "stdout_tail:",
        str(run.get("stdout_tail") or "")[-6000:],
        "stderr_tail:",
        str(run.get("stderr_tail") or "")[-6000:],
    ])


def main() -> int:
    p = argparse.ArgumentParser(description="Big Data Grader V4 — AI-assisted, behavior-first, sandboxed")
    p.add_argument("--project", help="Project ID from submission_groups.csv")
    p.add_argument("--workspace", help="Use an already-local repository")
    p.add_argument("--repo-url")
    p.add_argument("--project-id", default="LOCAL")
    p.add_argument("--submissions", default="submission_groups.csv")
    p.add_argument("--reports", default="reports")
    p.add_argument("--ref", help="Commit/tag/branch to evaluate")
    p.add_argument("--no-ai", action="store_true", help="Disable LLM repository analysis")
    p.add_argument("--confidence-threshold", type=float, default=0.80)
    p.add_argument("--runtime", action="store_true", help="Execute behavioral tests inside Docker sandbox")
    p.add_argument("--plan-b", action="store_true")
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--network-profile", choices=["isolated", "compat"], default="isolated")
    p.add_argument("--cpus", type=float, default=2.0)
    p.add_argument("--memory", default="6g")
    p.add_argument("--keep-sandbox", action="store_true")
    p.add_argument("--allow-low-confidence", action="store_true",
                   help="Run even if the execution plan requires manual review")
    p.add_argument("--override", help="Instructor-owned YAML execution override outside the student repository")
    p.add_argument("--overrides-dir", default="overrides", help="Directory containing <project_id>.yaml instructor overrides")
    args = p.parse_args()

    base = Path(__file__).resolve().parent
    project_id = args.project_id
    repo_url = args.repo_url or ""
    selected_ref = args.ref
    submission_row = None

    if args.project:
        row = find_submission(base / args.submissions, args.project)
        submission_row = row
        project_id = row["project_id"]
        repo_url = row["repo_url"]
        selected_ref = selected_ref or row.get("commit_sha") or row.get("ref") or None

    if args.workspace:
        repo = Path(args.workspace).resolve()
        if submission_row:
            subdir = (submission_row.get("workspace_subdir") or "").strip().replace("\\", "/")
            if subdir:
                subpath = Path(subdir)
                if subpath.is_absolute() or ".." in subpath.parts:
                    p.error(f"Unsafe workspace_subdir for {project_id}: {subdir}")
                candidate = (repo / subpath).resolve()
                if repo not in candidate.parents and candidate != repo:
                    p.error(f"workspace_subdir escapes frozen repository for {project_id}: {subdir}")
                if not candidate.exists() or not candidate.is_dir():
                    p.error(f"workspace_subdir not found for {project_id}: {subdir}")
                repo = candidate
    else:
        if not repo_url:
            p.error("Provide --project, --repo-url, or --workspace")
        repo = base / "workspaces" / project_id / "repo"
        clone_repository(repo_url, repo, ref=selected_ref)

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

    student_names = (submission_row or {}).get("students", "") if submission_row else ""
    student_nos = (submission_row or {}).get("student_nos", "") if submission_row else ""

    payload = {
        "grader_version": "4.2.0",
        "project_id": project_id,
        "students": student_names,
        "student_nos": student_nos,
        "repo_url": repo_url,
        "commit_sha": current_commit(repo) or selected_ref or "",
        "repository_path": str(repo),
        "plan_resolution": resolution,
        "execution_plan": plan.to_dict(),
        "static_checks": static_checks(repo),
        "runtime": None,
    }

    if args.runtime:
        if resolution.get("requires_manual_review") and not args.allow_low_confidence:
            payload["runtime"] = {
                "status": "MANUAL_REVIEW_REQUIRED",
                "reason": "Execution-plan confidence is below threshold. No student code was executed.",
                "confidence": resolution.get("confidence"),
                "threshold": args.confidence_threshold,
            }
        else:
            ok, detail = docker_available()
            if not ok:
                payload["runtime"] = {"status": "INFRA_ERROR", "reason": f"Docker is unavailable: {detail}"}
            else:
                from datasets.prepare_hidden_tests import ensure_prepared
                hidden = ensure_prepared()
                oracle = HiddenOracle(hidden / "teacher_key.json", hidden / "teacher_manifest.csv")
                sandbox_cfg = SandboxConfig(
                    cpus=args.cpus,
                    memory=args.memory,
                    timeout_seconds=args.timeout,
                    network_profile=args.network_profile,
                )
                payload["runtime"] = run_behavioral_suite(
                    base=base,
                    project_id=project_id,
                    repo=repo,
                    hidden_dir=hidden,
                    oracle=oracle,
                    plan=plan,
                    sandbox_config=sandbox_cfg,
                    timeout=args.timeout,
                    plan_b=args.plan_b,
                    keep_sandbox=args.keep_sandbox,
                )

                # Level 2 is deliberately lazy: inspect source only after the
                # README-derived execution command actually failed.
                failure_context = _runtime_command_failure_context(payload["runtime"])
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
                        or recovered_plan.ingest_stdin != plan.ingest_stdin
                        or recovered_plan.setup_command != plan.setup_command
                    )
                    payload["execution_recovery"] = {
                        **recovery,
                        "original_command": plan.ingest_command,
                        "recovered_command": recovered_plan.ingest_command,
                        "command_changed": changed,
                    }
                    if changed and recovered_plan.ingest_command:
                        payload["runtime_first_attempt"] = payload["runtime"]
                        plan = recovered_plan
                        payload["execution_plan"] = plan.to_dict()
                        payload["runtime"] = run_behavioral_suite(
                            base=base,
                            project_id=project_id,
                            repo=repo,
                            hidden_dir=hidden,
                            oracle=oracle,
                            plan=plan,
                            sandbox_config=sandbox_cfg,
                            timeout=args.timeout,
                            plan_b=args.plan_b,
                            keep_sandbox=args.keep_sandbox,
                        )

    result_json, result_md = write_report(base / args.reports, project_id, payload)
    summary = {
        "project_id": project_id,
        "students": student_names,
        "student_nos": student_nos,
        "commit_sha": payload["commit_sha"],
        "plan_confidence": resolution.get("confidence"),
        "manual_review": resolution.get("requires_manual_review"),
        "runtime_status": (payload.get("runtime") or {}).get("status"),
        "report": str(result_md),
        "result_json": str(result_json),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
