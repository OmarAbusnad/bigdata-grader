from __future__ import annotations

import shutil
import re
import json
from pathlib import Path
from typing import Any

from .input_staging import plan_flag_retry, plan_processed_input_retry, plan_staging_retry, processed_csv_path, staged_command
from .models import ExecutionPlan, RuntimeCaseResult
from .mongo_checker import MongoChecker
from .count_policy import compare_count, compare_new_inserts, compare_stability, compare_baseline_replay
from .oracle import HiddenOracle
from .runtime_evidence import detect_engine
from .sandbox import DockerSandbox, SandboxConfig, SandboxError
from .spark_probe import ensure_large_clean_probe
from .heuristic_setup_recovery import allow_clean_database_retry
from .spark_dependency_audit import check_submission
from .tests_midterm import (
    A,
    assert_equal,
    assert_zero,
    _execution_assertion,
    _engine_assertion,
    _verify_clean_samples,
    _verify_quarantine_evidence,
    _capture_docs,
    _verify_upsert_actions,
)


def _live(message: str) -> None:
    """Emit an immediately visible progress marker in GitHub Actions logs."""
    print(f"[GRADER] {message}", flush=True)


def _pipeline_completed_before_timeout(runtime_log: dict[str, Any] | None) -> bool:
    runtime_log = runtime_log or {}
    if not runtime_log.get("timed_out"):
        return False
    text = (str(runtime_log.get("stdout_tail") or "") + "\n" + str(runtime_log.get("stderr_tail") or "")).lower()
    markers = [
        "pipeline completed successfully",
        "all phase 1 & phase 2 pipeline stages completed successfully",
        "all phases completed successfully",
        "etl completed successfully",
        "ingestion completed successfully",
    ]
    return any(marker in text for marker in markers)


def _classify_midterm_start_failure(repo: Path, runtime_log: dict[str, Any] | None) -> dict[str, Any]:
    runtime_log = runtime_log or {}
    stdout = str(runtime_log.get("stdout_tail") or "")
    stderr = str(runtime_log.get("stderr_tail") or "")
    text = stdout + "\n" + stderr

    if runtime_log.get("timed_out") and not _pipeline_completed_before_timeout(runtime_log):
        return {"code": "TIMEOUT", "evidence": ["initial pipeline command timed out before an explicit success marker"]}

    if "EOFError: EOF when reading a line" in text or re.search(r"\binput\s*\(", text):
        return {
            "code": "GRADER_DISCOVERY_FAILURE",
            "evidence": ["interactive CLI requires structured stdin; execution plan did not provide it"],
        }

    if re.search(r"unrecognized arguments?:", text, re.I) or re.search(r"error:\s+argument\s+.+invalid choice", text, re.I):
        return {
            "code": "GRADER_DISCOVERY_FAILURE",
            "evidence": ["selected CLI arguments were rejected by the project's own argparse contract"],
        }

    m = re.search(r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]", text)
    if m:
        module = m.group(1)
        top = module.split(".", 1)[0]
        local = (repo / f"{top}.py").is_file() or (repo / top / "__init__.py").is_file()
        requirements = ""
        try:
            requirements = (repo / "requirements.txt").read_text(encoding="utf-8-sig", errors="replace").lower()
        except Exception:
            pass
        declared = bool(re.search(rf"(?m)^\s*{re.escape(top.lower())}(?:\s|[<>=!~\[]|$)", requirements))
        local_hints = {"config", "src", "app", "core", "common", "utils", "services", "database", "db", "pipeline", "etl"}
        if not local and not declared and top.lower() in local_hints:
            return {
                "code": "STUDENT_CONFIGURATION_FAILURE",
                "evidence": [f"missing local-style module: {module}"],
            }
        if not local and not declared:
            return {
                "code": "STUDENT_DEPENDENCY_FAILURE",
                "evidence": [f"missing undeclared module: {module}"],
            }
        return {"code": "STUDENT_CONFIGURATION_FAILURE", "evidence": [f"module import failed: {module}"]}

    if re.search(r"SyntaxError|IndentationError", text):
        return {"code": "STUDENT_CODE_FAILURE", "evidence": ["Python syntax/import-time error"]}
    if re.search(r"No such file or directory|can't open file", text, re.I):
        return {"code": "GRADER_DISCOVERY_FAILURE", "evidence": ["resolved command references a missing executable path"]}
    return {
        "code": "STUDENT_CODE_OR_CONFIGURATION_FAILURE",
        "evidence": ["initial pipeline command failed before runtime behavior could be verified"],
    }


def _midterm_blocked_assertions(reason: str, *, plan_b: bool) -> list[Any]:
    specs = [
        ("batch.raw_count", "orders_raw = عدد صفوف الإدخال"),
        ("batch.validated_count", "orders_validated = النتيجة المتوقعة"),
        ("batch.quarantine_count", "orders_quarantine = النتيجة المتوقعة"),
        ("batch.duplicates", "لا توجد Business Keys مكررة"),
        ("batch.unique_index_runtime", "Unique Index فعلي على Business Key"),
        ("batch.schema_validator_runtime", "$jsonSchema Validator فعلي على validated"),
        ("batch.cleaning_samples", "قواعد التنظيف تعمل على العينات المخفية"),
        ("batch.audit_trail", "سجل أثر التعديل موجود"),
        ("batch.quarantine_errors", "العزل يحتوي سبب الخطأ"),
        ("spark_pipeline.command", "Spark pipeline execution"),
        ("spark_pipeline.engine", "Spark engine selection"),
        ("spark.raw_count", "Spark raw count"),
        ("spark.validated_count", "Spark validated count"),
        ("spark.quarantine_count", "Spark quarantine count"),
        ("spark.duplicates", "Spark duplicate business keys"),
        ("upsert.baseline_validated", "Upsert baseline"),
        ("upsert.final_validated", "Upsert final validated"),
        ("upsert.insert_samples", "Upsert insert samples"),
        ("upsert.update_samples", "Upsert update samples"),
        ("upsert.unchanged_samples", "Upsert unchanged samples"),
        ("idempotency.validated_stable", "Idempotency validated stable"),
        ("idempotency.duplicates", "Idempotency duplicates"),
    ]
    if plan_b:
        specs += [
            ("incremental.final_validated", "Incremental validated"),
            ("incremental.duplicates_first", "Incremental duplicates"),
            ("incremental.rerun_validated_stable", "Incremental rerun stable"),
            ("incremental.rerun_duplicates", "Incremental rerun duplicates"),
        ]
    return [
        A(key, label, "INCONCLUSIVE", "runtime ready", "BLOCKED",
          note=f"Blocked by root cause: {reason}")
        for key, label in specs
    ]


def _spark_dependency_resolution_blocked(runtime_log: dict[str, Any] | None) -> tuple[bool, list[str]]:
    runtime_log = runtime_log or {}
    text = (str(runtime_log.get("stdout_tail") or "") + "\n" + str(runtime_log.get("stderr_tail") or "")).lower()
    markers = [
        "unresolved dependencies",
        "module not found: org.mongodb.spark",
        "host repo1.maven.org not found",
        "host repos.spark-packages.org not found",
        "unknownhostexception",
        "could not resolve dependencies",
    ]
    hits = [m for m in markers if m in text]
    return bool(hits), hits


def _guard_unfinished_mutation_case(case: Any) -> int:
    """Never double-penalize a failed Upsert/Incremental command via final counts.

    The command verdict remains intact. We mark only dependent numeric FAILs
    as INCONCLUSIVE when the stage never finished; completed executions are
    still fully evaluated against the teacher Oracle.
    """
    log = getattr(case, "runtime_log", None) or {}
    if not log or _pipeline_completed_before_timeout(log):
        return 0
    if int(log.get("returncode") or 0) == 0 and not log.get("timed_out"):
        return 0
    dependent = {
        "upsert.final_validated", "incremental.final_validated",
        "idempotency.validated_stable", "incremental.rerun_validated_stable",
    }
    changed = 0
    for assertion in getattr(case, "assertions", []):
        if assertion.key in dependent and assertion.verdict == "FAIL":
            assertion.verdict = "INCONCLUSIVE"
            assertion.note = ("The upstream command did not complete; "
                              "the observed count is partial and is not an independent failure.")
            assertion.evidence.append(
                f"failed stage returncode={log.get('returncode')}; "
                f"timed_out={bool(log.get('timed_out'))}"
            )
            changed += 1
    return changed


def _spark_stage_unfinished(runtime_log: dict[str, Any] | None) -> bool:
    """A failed command proves execution failure, not independent final counts."""
    log = runtime_log or {}
    if not log:
        return False
    return bool(
        int(log.get("returncode") or 0) != 0 or log.get("timed_out")
    ) and not _pipeline_completed_before_timeout(log)


def _unproven_spark_execution_precondition(
    repo: Path, runtime_log: dict[str, Any] | None
) -> tuple[str | None, list[str]]:
    """Identify unproved Spark execution preconditions without awarding PASS.

    Only a failed execution with one of the narrowly evidenced signatures is
    affected. Generic application errors remain evaluable student evidence.
    """
    log = runtime_log or {}
    if log.get("timed_out"):
        return "SPARK_TIMEOUT_UNPROVEN", [
            "The Spark stage exceeded the grader timeout before completion; "
            "inspect progress and the assignment's time limits before attributing its missing output."
        ]
    if int(log.get("returncode") or 0) == 0:
        return None, []
    text = str(log.get("stderr_tail") or "") + "\n" + str(log.get("stdout_tail") or "")
    if re.search(
        r"(?:Configured|Project)\s+Java(?:\s+\d+)?\s+was not found at|"
        r"JAVA_HOME does not contain bin\\java\.exe", text, re.I
    ):
        return "SPARK_PLATFORM_JAVA_CONFIGURATION_UNPROVEN", [
            "The Spark launcher could not find the Java executable at the program's configured path; "
            "check cross-platform launch contract before penalizing downstream data checks."
        ]
    if re.search(r"spark-submit\.cmd|Cannot run program [\"']python\.exe[\"']", text, re.I):
        return "SPARK_PLATFORM_WINDOWS_EXECUTABLE_UNPROVEN", [
            "A Windows-only Spark/Python executable was invoked in the Linux grading container."
        ]
    if re.search(r"Ivy jar cache not found", text, re.I):
        return "SPARK_CONNECTOR_CACHE_PATH_UNPROVEN", [
            "The Spark launcher expects an Ivy cache directory that is absent in this environment."
        ]
    if re.search(r"ClassNotFoundException:\s*mongodb\.DefaultSource", text, re.I):
        audit = check_submission(repo, runtime_error=text)
        if audit.get("owner") == "STUDENT_CODE":
            return None, []  # Independently proven source-level mismatch is not excused.
        return "SPARK_MONGODB_PROVIDER_UNPROVEN", [
            "Spark cannot load the MongoDB data source provider; audit declared JARs, "
            "Scala/Spark compatibility, and the sandbox classpath before assigning responsibility."
        ]
    return None, []


def _format_threshold_env(value: float | int) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def _render_command(plan: ExecutionPlan, file_rel: str, db_name: str, threshold_mb: float | None) -> str:
    if not plan.ingest_command:
        raise SandboxError("No ingest command was resolved")
    cmd = plan.ingest_command
    cmd = cmd.replace("{file}", f"/grader-tests/{file_rel}")
    cmd = cmd.replace("{db_name}", db_name)
    cmd = cmd.replace("{threshold_mb}", _format_threshold_env(threshold_mb if threshold_mb is not None else 200))
    if any(x in cmd for x in ["&&", "||", ";", "|", ">", "<", "`", "$("]):
        raise SandboxError("Unsafe shell metacharacters detected in resolved command")
    return cmd


def _render_stdin(plan: ExecutionPlan, file_rel: str, db_name: str, threshold_mb: float | None) -> str | None:
    if not plan.ingest_stdin:
        return None
    value = str(plan.ingest_stdin)
    if "\x00" in value or len(value) > 4000:
        raise SandboxError("Unsafe or oversized structured stdin in execution plan")
    value = value.replace("{file}", f"/grader-tests/{file_rel}")
    value = value.replace("{db_name}", db_name)
    value = value.replace("{threshold_mb}", _format_threshold_env(threshold_mb if threshold_mb is not None else 200))
    return value


def _copy_input_view(hidden_dir: Path, oracle: HiddenOracle, inputs_dir: Path) -> dict[str, str]:
    """Copy only student-visible input datasets. Teacher oracle files are never mounted."""
    if inputs_dir.exists():
        shutil.rmtree(inputs_dir)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for test_name in ("test_01", "test_02", "test_03", "test_04"):
        spec = oracle.test(test_name)
        name = str(spec.get("file") or "").strip()
        if not name:
            continue
        src = (hidden_dir / name).resolve()
        if hidden_dir.resolve() not in src.parents:
            raise SandboxError(f"Unsafe dataset path in oracle: {name}")
        if not src.exists() or not src.is_file():
            raise SandboxError(f"Hidden input file missing: {src}")
        dst = inputs_dir / src.name
        _copy_without_bom(src, dst)
        mapping[test_name] = dst.name
    return mapping


def _copy_without_bom(src: Path, dst: Path) -> None:
    """Copy a dataset, dropping a leading UTF-8 BOM from CSV files.

    The BOM is only an encoding marker. Programs that open the file as plain ``utf-8`` see it
    glued to the first header (``\\ufefforder_id``) and then reject every row as having no
    business key, which says nothing about their pipeline logic. Content is otherwise identical.
    """
    if src.suffix.lower() != ".csv":
        shutil.copy2(src, dst)
        return
    with src.open("rb") as fin:
        head = fin.read(3)
        with dst.open("wb") as fout:
            if head != b"\xef\xbb\xbf":
                fout.write(head)
            shutil.copyfileobj(fin, fout, 1024 * 1024)
    shutil.copystat(src, dst)


def _count_assertion(key: str, label: str, decision):
    evidence = ([f"relative_error={decision.error_ratio:.6f}"] if decision.error_ratio is not None else [])
    return A(key, label, decision.verdict, decision.expected, decision.actual, evidence, note=decision.reason)


def run_behavioral_suite(
    *,
    base: Path,
    project_id: str,
    repo: Path,
    hidden_dir: Path,
    oracle: HiddenOracle,
    plan: ExecutionPlan,
    sandbox_config: SandboxConfig,
    timeout: int = 1200,
    plan_b: bool = False,
    keep_sandbox: bool = False,
    shared_sandbox: DockerSandbox | None = None,
    student_inputs_dir: Path | None = None,
    manage_sandbox: bool = True,
) -> dict[str, Any]:
    """Behavior-first midterm suite in Docker with host-side independent Mongo verification."""
    if not plan.ingest_command:
        return {"status": "MANUAL_REVIEW_REQUIRED", "reason": "No ingest command resolved"}

    _live(f"{project_id}: preparing student-visible hidden inputs")
    inputs_dir = Path(student_inputs_dir) if student_inputs_dir is not None else (base / "sandboxes" / project_id / "input_view")
    input_names = _copy_input_view(hidden_dir, oracle, inputs_dir)

    safe_pid = "".join(c if c.isalnum() else "_" for c in project_id).lower()
    effective_db = f"grader_{safe_pid}" if plan.database_configurable else (plan.database_name or f"grader_{safe_pid}")
    # Hidden discussion datasets are calibrated around the instructor's
    # recommended threshold (currently 20 MB). If the student's threshold is
    # configurable, drive the project with that discussion threshold so Test 01
    # proves Batch and Test 02 proves Spark. Only fall back to the student's
    # hard-coded threshold when it is not configurable.
    threshold = float(oracle.threshold_mb if plan.threshold_configurable else (plan.threshold_mb or oracle.threshold_mb))

    sb = shared_sandbox or DockerSandbox(base, project_id, repo, inputs_dir, sandbox_config)
    if shared_sandbox is not None:
        sb.hidden_dir = inputs_dir
    report: dict[str, Any] = {
        "status": "STARTING",
        "grading_mode": "behavior_first_sandboxed",
        "sandbox": sb.metadata(),
        "database": effective_db,
        "database_original": plan.database_name,
        "database_isolated": bool(plan.database_configurable),
        "threshold_mb_used": threshold,
        "cases": [],
        "setup_runs": [],
    }
    mongo: MongoChecker | None = None

    try:
        if manage_sandbox:
            _live(f"{project_id}: building student dependency image")
            build = sb.build()
            report["build"] = build
            if not build["ok"]:
                if build.get("spark_dependency_precondition_failed"):
                    report["status"] = "GRADER_INFRA_FAILURE"
                    report["root_cause"] = "GRADER_SPARK_PREFETCH_FAILED"
                    report["root_cause_owner"] = "GRADER_ENVIRONMENT"
                    report["root_cause_evidence"] = [
                        "Exact declared Spark connector could not be prefetched/verified "
                        "before the student's network-isolated run.",
                        str(build.get("spark_prefetch_log_tail") or "")[-1200:],
                    ]
                    report["notes"] = [
                        "No student execution occurred. Do not assign student FAIL or "
                        "erase historical PASS on a grader-side Maven precondition.",
                    ]
                else:
                    report["status"] = "DEPENDENCY_BUILD_ERROR"
                return report

            _live(f"{project_id}: starting isolated Docker sandbox + MongoDB")
            report["sandbox_start"] = sb.start()
        else:
            report["build"] = {"ok": True, "shared": True, "image": sb.image_name}
            report["sandbox_start"] = {"shared": True, "network": sb.network, "mongo": sb.mongo_name}
        if not sb.mongo_host_uri:
            raise SandboxError("MongoDB grader-side host URI was not established")

        mongo = MongoChecker(sb.mongo_host_uri, effective_db, plan.collections, business_key=plan.business_key or "order_id")
        mongo.ping()
        _live(f"{project_id}: sandbox ready | database={effective_db} | threshold={threshold:.1f}MB")

        setup_mode = {"skip_auto": False}

        def run_setup() -> None:
            if not plan.setup_command or setup_mode["skip_auto"]:
                return
            env = {
                "MONGO_DB_NAME": effective_db,
                "MONGO_DATABASE": effective_db,
                "DATABASE_NAME": effective_db,
                "DB_NAME": effective_db,
                "MONGODB_DATABASE": effective_db,
                "SMALL_FILE_THRESHOLD_MB": _format_threshold_env(threshold),
                "FILE_SIZE_THRESHOLD_MB": _format_threshold_env(threshold),
                "THRESHOLD_MB": _format_threshold_env(threshold),
            }
            r = sb.run_student(plan.setup_command, env=env, timeout=min(timeout, 300))
            report["setup_runs"].append({**r, "stdout": r.get("stdout", "")[-8000:], "stderr": r.get("stderr", "")[-8000:]})

        def fresh_database() -> None:
            mongo.drop_database()
            run_setup()

        staged_target: dict[str, str | None] = {"path": None}

        def execute_case(
            case_name: str,
            test_key: str,
            *,
            fresh: bool,
            expected_engine: str | None = None,
            file_path: Path | None = None,
            spec_override: dict[str, Any] | None = None,
            threshold_override: float | None = None,
        ) -> tuple[RuntimeCaseResult, dict[str, Any]]:
            nonlocal effective_db
            if fresh:
                fresh_database()
            spec = dict(spec_override or oracle.test(test_key))
            source = file_path or (inputs_dir / input_names[test_key])
            if not source.exists():
                raise SandboxError(f"Student-visible test file not found: {source}")
            try:
                rel = source.relative_to(inputs_dir).as_posix()
            except ValueError:
                raise SandboxError("Runtime dataset is outside the student-visible input directory")

            before = mongo.snapshot().to_dict()
            effective_threshold = threshold if threshold_override is None else float(threshold_override)
            cmd = _render_command(plan, rel, effective_db, effective_threshold)
            env = {
                "MONGO_DB_NAME": effective_db,
                "MONGO_DATABASE": effective_db,
                "DATABASE_NAME": effective_db,
                "DB_NAME": effective_db,
                "MONGODB_DATABASE": effective_db,
                "SMALL_FILE_THRESHOLD_MB": _format_threshold_env(effective_threshold),
                "FILE_SIZE_THRESHOLD_MB": _format_threshold_env(effective_threshold),
                "THRESHOLD_MB": _format_threshold_env(effective_threshold),
                "GRADER_RUN": "1",
            }
            file_mb = source.stat().st_size / (1024 * 1024)
            _live(
                f"{project_id}: RUN {case_name} | file={source.name} | size={file_mb:.2f}MB "
                f"| expected_engine={expected_engine or 'n/a'} | threshold={effective_threshold:.1f}MB"
            )
            stdin_text = _render_stdin(plan, rel, effective_db, effective_threshold)
            input_staging: dict[str, Any] | None = None
            if staged_target["path"]:
                # A previous stage already proved this program reads a fixed CSV path.
                cmd = staged_command(cmd, staged_target["path"], rel)
                input_staging = {"target": staged_target["path"], "source": rel, "reason": "fixed input path discovered in an earlier stage"}
            run = sb.run_student(cmd, env=env, timeout=timeout, stdin_text=stdin_text)
            # Retry only a grader-inferred setup that created a conflicting
            # index before the student's normal command. This never changes
            # student code and does not award PASS without a successful run.
            first_after = mongo.snapshot().to_dict()
            setup_succeeded = bool(report["setup_runs"]) and int(
                report["setup_runs"][-1].get("returncode", 1)
            ) == 0
            if (not setup_mode["skip_auto"] and allow_clean_database_retry(
                repo, plan_source=str(plan.source or ""),
                setup_command=plan.setup_command,
                setup_succeeded=setup_succeeded,
                unique_index_exists=mongo.has_unique_business_index()[0],
                failed_returncode=int(run.get("returncode") or 0),
                timed_out=bool(run.get("timed_out")),
                error_output=str(run.get("stderr") or "") + "\n" + str(run.get("stdout") or ""),
                data_written=any(int(first_after.get(k) or 0) > 0
                                 for k in ("raw", "validated", "quarantine")),
            )):
                first_rc = int(run.get("returncode") or 0)
                target_db, target_evidence = mongo.find_unambiguous_empty_unique_index_database(
                    allow_partial_failed_attempt=True,
                )
                if not target_db:
                    report.setdefault("setup_recovery", []).append({
                        "case": case_name, "reason": "inferred_setup_index_spec_conflict",
                        "first_returncode": first_rc, "recovered": False,
                        "retry_skipped": "no_unique_empty_target_database",
                        "database_evidence": target_evidence,
                    })
                else:
                    if target_db != mongo.database_name:
                        mongo.switch_database(target_db)
                        effective_db = target_db
                        report["database"] = target_db
                        report["database_discovery"] = {
                            "source": "unique_empty_setup_index_database_in_isolated_runtime",
                            "evidence": target_evidence,
                        }
                    # All records belong to this isolated failed run, not to
                    # a student-owned database. Preserve exact counts and the
                    # first failure before resetting the one proven target DB.
                    failed_snapshot = mongo.snapshot().to_dict()
                    first_error = str(run.get("stderr") or "")[-3000:]
                    mongo.drop_database()
                    before = mongo.snapshot().to_dict()
                    _live(f"{project_id}: {case_name} inferred index setup blocked processing; "
                          "retrying original command once after a documented isolated DB reset")
                    retry = sb.run_student(cmd, env=env, timeout=timeout, stdin_text=stdin_text)
                    recovered = int(retry.get("returncode") or 0) == 0 and not retry.get("timed_out")
                    report.setdefault("setup_recovery", []).append({
                        "case": case_name, "reason": "inferred_setup_index_spec_conflict",
                        "database": target_db, "database_evidence": target_evidence,
                        "first_snapshot_after": failed_snapshot, "first_stderr_tail": first_error,
                        "first_returncode": first_rc, "retry_returncode": retry.get("returncode"),
                        "retry_timed_out": bool(retry.get("timed_out")), "recovered": recovered,
                        "retry_stderr_tail": str(retry.get("stderr") or "")[-3000:],
                    })
                    if recovered:
                        setup_mode["skip_auto"] = True
                        input_staging = {
                            "reason": "inferred setup conflicted with student index specification",
                            "first_returncode": first_rc, "retry_clean_db_without_setup": True,
                        }
                    run = retry
            if int(run.get("returncode") or 0) != 0 and not run.get("timed_out"):
                decision = plan_staging_retry(
                    str(run.get("stderr") or ""), str(run.get("stdout") or ""),
                    mongo.snapshot().to_dict(), fresh=fresh, already_staged=bool(staged_target["path"]))
                if decision:
                    target, needs_reset = decision
                    first_rc = run.get("returncode")
                    if needs_reset:
                        fresh_database()
                    cmd = staged_command(cmd, target, rel)
                    _live(f"{project_id}: {case_name} read a fixed input path ({target}); staging the test file there and retrying once")
                    run = sb.run_student(cmd, env=env, timeout=timeout, stdin_text=stdin_text)
                    staged_target["path"] = target
                    input_staging = {"target": target, "source": rel, "first_attempt_returncode": first_rc,
                                     "reason": "student program reads a fixed CSV path instead of the supplied argument"}
            if _pipeline_completed_before_timeout({
                "timed_out": run.get("timed_out"),
                "stdout_tail": str(run.get("stdout") or "")[-12000:],
                "stderr_tail": str(run.get("stderr") or "")[-12000:],
            }):
                run["post_pipeline_server_timeout"] = True
                run["returncode"] = 0
                run["timed_out"] = False
            after = mongo.snapshot().to_dict()
            if (
                case_name == "batch_pipeline"
                and not plan.database_name
                and not any(int(after.get(k) or 0) for k in ("raw", "validated", "quarantine"))
                and int(run.get("returncode") or 0) == 0
                and not run.get("timed_out")
            ):
                # Student code may have an immutable default DB name. Search only
                # this project's isolated MongoDB; never guess between candidates.
                found_db, candidate_evidence = mongo.locate_active_database()
                if found_db and found_db != effective_db:
                    mongo.switch_database(found_db)
                    effective_db = found_db
                    report["database"] = found_db
                    report["database_discovery"] = {
                        "source": "unique_populated_database_in_isolated_runtime",
                        "evidence": candidate_evidence,
                    }
                    after = mongo.snapshot().to_dict()
                elif not found_db:
                    report["database_discovery"] = {
                        "source": "unresolved",
                        "evidence": candidate_evidence,
                    }
            if int(run.get("returncode") or 0) == 0 and not run.get("timed_out") and not input_staging:
                run_stdout = str(run.get("stdout") or "")
                flag_cmd = plan_flag_retry(run_stdout, cmd, after, fresh=fresh)
                if flag_cmd:
                    _live(f"{project_id}: {case_name} was a check-only run that names the executing flag; re-running once with it")
                    first_cmd = cmd
                    cmd = flag_cmd
                    run = sb.run_student(cmd, env=env, timeout=timeout, stdin_text=stdin_text)
                    input_staging = {"first_command": first_cmd, "retry_command": flag_cmd,
                                     "reason": "program output asked for an explicit execute flag; nothing had been written"}
                    after = mongo.snapshot().to_dict()
                else:
                    _live(f"{project_id}: {case_name} input probe | fresh={fresh} raw={after.get('raw')} expected_rows={spec.get('input')} printed_csv={processed_csv_path(run_stdout, rel)}")
                    other_csv = plan_processed_input_retry(
                        run_stdout, after, expected_rows=int(spec.get("input") or 0),
                        hidden_file_rel=rel, fresh=fresh, already_staged=bool(staged_target["path"]))
                    if other_csv:
                        _live(f"{project_id}: {case_name} processed {other_csv} instead of the supplied file; staging the test file there and retrying once")
                        fresh_database()
                        cmd = staged_command(cmd, other_csv, rel)
                        run = sb.run_student(cmd, env=env, timeout=timeout, stdin_text=stdin_text)
                        staged_target["path"] = other_csv
                        input_staging = {"target": other_csv, "source": rel,
                                         "reason": "program printed a different CSV path than the supplied test file and raw count did not match"}
                        after = mongo.snapshot().to_dict()
            _live(
                f"{project_id}: DONE {case_name} | rc={run.get('returncode')} "
                f"| elapsed={float(run.get('elapsed_seconds', 0)):.2f}s "
                f"| raw={after.get('raw')} validated={after.get('validated')} quarantine={after.get('quarantine')}"
            )
            engine, engine_evidence = detect_engine(
                run.get("stdout", ""),
                run.get("stderr", ""),
                None,
                mongo.distinct_engine_values(),
            )
            case = RuntimeCaseResult(
                name=case_name,
                command=cmd,
                command_result=None,
                snapshot_before=before,
                snapshot_after=after,
                engine=engine,
                engine_evidence=engine_evidence,
                metrics=None,
            )
            # Adapt dict runtime result to the assertion helper's expected shape.
            class _R:
                returncode = int(run.get("returncode", 1))
                elapsed_seconds = float(run.get("elapsed_seconds", 0))
                timed_out = bool(run.get("timed_out", False))
                stdout = str(run.get("stdout", ""))
                stderr = str(run.get("stderr", ""))
                ok = returncode == 0 and not timed_out
            case.assertions.append(_execution_assertion(case_name, _R))
            if expected_engine:
                a = _engine_assertion(case_name, engine, expected_engine, engine_evidence, plan)
                file_mb = source.stat().st_size / (1024 * 1024)
                if expected_engine == "pyspark" and file_mb <= effective_threshold and not plan.threshold_configurable:
                    a.verdict = "INCONCLUSIVE"
                    a.note = f"ملف الاختبار {file_mb:.1f}MB لا يتجاوز Threshold المشروع {effective_threshold:.1f}MB."
                case.assertions.append(a)
            # Store sanitized runtime excerpt separately; do not expose secrets.
            case.runtime_log = {
                "returncode": run.get("returncode"),
                "elapsed_seconds": run.get("elapsed_seconds"),
                "timed_out": run.get("timed_out"),
                "stdout_tail": str(run.get("stdout", ""))[-12000:],
                "stderr_tail": str(run.get("stderr", ""))[-12000:],
                "stdin_used": bool(stdin_text),
                "input_staging": input_staging,
            }
            return case, spec

        # Test 01: Batch + full ELT behavior.
        _live(f"{project_id}: stage 1/5 — Batch + ELT")
        batch, t1 = execute_case("batch_pipeline", "test_01", fresh=True, expected_engine="python_batch")
        s1 = batch.snapshot_after or {}
        batch_run = getattr(batch, "runtime_log", None) or {}
        if report.get("database_discovery", {}).get("source") == "unresolved":
            report["status"] = "MANUAL_REVIEW_REQUIRED"
            report["root_cause"] = "GRADER_DATABASE_DISCOVERY_UNRESOLVED"
            report["root_cause_evidence"] = report["database_discovery"]["evidence"]
            report["cases"].append(_case_dict(batch))
            report["notes"] = [
                "The ingest command returned successfully but no pipeline data was found",
                "in a verifiable database. No Mongo assertions were graded as FAIL.",
            ]
            return report
        batch_effective_failure = (
            int(batch_run.get("returncode") or 0) != 0
            or bool(batch_run.get("timed_out"))
        ) and not _pipeline_completed_before_timeout(batch_run)
        if batch_effective_failure:
            root_cause = _classify_midterm_start_failure(repo, batch_run)
            for a in batch.assertions:
                if a.key == "batch_pipeline.engine":
                    a.verdict = "INCONCLUSIVE"
            batch.assertions += _midterm_blocked_assertions(str(root_cause.get("code")), plan_b=plan_b)
            report["cases"].append(_case_dict(batch))
            assertions = {}
            counts = {k: 0 for k in ["PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIP"]}
            for a in batch.assertions:
                assertions[a.key] = a.to_dict()
                counts[a.verdict] = counts.get(a.verdict, 0) + 1
            report["assertions"] = assertions
            report["assertion_counts"] = counts
            report["root_cause"] = root_cause.get("code")
            report["root_cause_evidence"] = root_cause.get("evidence") or []
            report["runtime_ready"] = False
            report["status"] = "STARTUP_BLOCKED"
            return report

        report["runtime_ready"] = True
        batch.assertions += [
            assert_equal("batch.raw_count", "orders_raw = عدد صفوف الإدخال", s1.get("raw"), int(t1["input"])),
            _count_assertion("batch.validated_count", "Validated count aggregate band", compare_count(s1.get("validated"), t1["validated_after_run"])),
            _count_assertion("batch.quarantine_count", "Quarantine count aggregate band", compare_count(s1.get("quarantine"), t1["quarantine"])),
            assert_zero("batch.duplicates", "لا توجد Business Keys مكررة", int(s1.get("duplicate_business_keys", -1))),
        ]
        unique_ok, unique_ev = mongo.has_unique_business_index()
        batch.assertions.append(A("batch.unique_index_runtime", "Unique Index فعلي على Business Key", "PASS" if unique_ok else "FAIL", True, unique_ok, unique_ev))
        inspect = getattr(mongo, "inspect_json_schema_validator", None)
        schema_proof = inspect() if callable(inspect) else {
            "status": "PRESENT" if mongo.has_json_schema_validator() else "UNVERIFIED",
            "reason": "validator_inspector_unavailable",
        }
        schema_ok = schema_proof["status"] == "PRESENT"
        report["schema_validator_inspection"] = schema_proof
        batch.assertions.append(A(
            "batch.schema_validator_runtime", "$jsonSchema Validator فعلي على validated",
            "PASS" if schema_ok else "INCONCLUSIVE", True, schema_ok,
            evidence=[json.dumps(schema_proof, ensure_ascii=False, sort_keys=True)],
            note=("Live MongoDB confirmed validator absent; academic rubric decides its weight."
                  if schema_proof["status"] in {"ABSENT", "COLLECTION_MISSING"} else
                  "Validator proof could not be established by the grader.")
            if not schema_ok else None,
        ))
        clean_cases = oracle.sample("test_01", classes=["correctable"], n=18)
        clean_a, audit_a = _verify_clean_samples(mongo, clean_cases)
        batch.assertions += [clean_a, audit_a, _verify_quarantine_evidence(mongo)]
        batch_network_blocked, batch_network_evidence = _spark_dependency_resolution_blocked(
            getattr(batch, "runtime_log", None)
        )
        if batch_network_blocked:
            # Keep independently proven facts (command/raw/explicit router engine)
            # and convert downstream facts that could not execute into review.
            for a in batch.assertions:
                if a.verdict == "FAIL" and a.key not in {"batch_pipeline.command", "batch.raw_count", "batch_pipeline.engine"}:
                    a.verdict = "INCONCLUSIVE"
                    a.note = "Blocked by Spark/Maven dependency resolution under the grader's isolated network."
                    a.evidence.extend(batch_network_evidence)
            report["cases"].append(_case_dict(batch))
            assertions = {}
            counts = {k: 0 for k in ["PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIP"]}
            for a in batch.assertions:
                assertions[a.key] = a.to_dict()
                counts[a.verdict] = counts.get(a.verdict, 0) + 1
            # Remaining Spark/Upsert/Idempotency behavior depends on the same ELT
            # stage and is therefore blocked, not failed.
            blocked = _midterm_blocked_assertions("GRADER_NETWORK_DEPENDENCY_BLOCKED", plan_b=plan_b)
            existing = set(assertions)
            for a in blocked:
                if a.key in existing:
                    continue
                assertions[a.key] = a.to_dict()
                counts[a.verdict] = counts.get(a.verdict, 0) + 1
            report["assertions"] = assertions
            report["assertion_counts"] = counts
            report["root_cause"] = "GRADER_NETWORK_DEPENDENCY_BLOCKED"
            report["root_cause_evidence"] = batch_network_evidence
            report["runtime_ready"] = True
            report["status"] = "COMPLETED_WITH_REVIEW"
            report["notes"] = [
                "Raw Batch behavior executed, but downstream ELT/Spark behavior required Maven artifacts unavailable in isolated mode.",
                "Blocked assertions are INCONCLUSIVE and must not be converted to zero.",
            ]
            return report

        report["cases"].append(_case_dict(batch))

        # Test 02: Spark. Generate a larger clean probe if a hard-coded threshold requires it.
        _live(f"{project_id}: stage 2/5 — Spark path")
        mongo.clear_documents()
        t2 = oracle.test("test_02")
        spark_file = inputs_dir / input_names["test_02"]
        spark_spec = dict(t2)
        spark_threshold = threshold
        if not plan.threshold_configurable and plan.threshold_mb:
            spark_threshold = float(plan.threshold_mb)
            if spark_file.stat().st_size / (1024 * 1024) <= spark_threshold:
                probe, rows, reason = ensure_large_clean_probe(spark_file, inputs_dir, spark_threshold)
                if probe != spark_file:
                    spark_file = probe
                    spark_spec.update({"input": rows, "validated_after_run": rows, "quarantine": 0, "probe_reason": reason})
        spark, t2_eff = execute_case("spark_pipeline", "test_02", fresh=False, expected_engine="pyspark",
                                     file_path=spark_file, spec_override=spark_spec, threshold_override=spark_threshold)
        s2 = spark.snapshot_after or {}
        spark_log = getattr(spark, "runtime_log", None)
        spark_blocked, spark_block_evidence = _spark_dependency_resolution_blocked(spark_log)
        precondition, precondition_evidence = _unproven_spark_execution_precondition(repo, spark_log)
        # A failed Spark command can be an actual student failure, but its
        # downstream *final* counts were never proven. Do not assign separate
        # count FAIL for zeros/partial records left by an unfinished stage.
        spark_unfinished = _spark_stage_unfinished(spark_log)
        if spark_blocked or precondition or spark_unfinished:
            reason = ("Blocked by isolated Maven dependency resolution." if spark_blocked else
                      "Spark execution precondition is unresolved; no downstream records could be evaluated."
                      if precondition else
                      "Spark command did not complete; downstream count snapshots are not final stage results.")
            evidence = (spark_block_evidence if spark_blocked else precondition_evidence
                        if precondition else [
                            f"Spark incomplete: returncode={spark_log.get('returncode')}; "
                            f"timed_out={bool(spark_log.get('timed_out'))}"
                        ])
            report.setdefault("stage_preconditions", {})["spark_pipeline"] = {
                "code": ("GRADER_NETWORK_DEPENDENCY_BLOCKED" if spark_blocked else
                         precondition if precondition else "SPARK_COMMAND_UNFINISHED"),
                "owner": "GRADER_ENVIRONMENT" if spark_blocked else "UNPROVEN",
                "evidence": evidence,
            }
            for a in spark.assertions:
                # Preserve a genuine failed student command. For known grader
                # preconditions only, keep the existing unproven-command policy.
                if (precondition or spark_blocked) and (
                    a.key == "spark_pipeline.command" or (spark_blocked and a.key == "spark_pipeline.engine")
                ):
                    a.verdict = "INCONCLUSIVE"
                    a.note = reason
                    a.evidence.extend(evidence)
            spark.assertions += [
                A("spark.raw_count", "Spark: orders_raw = الإدخال", "INCONCLUSIVE", int(t2_eff["input"]), s2.get("raw"),
                  evidence, note=reason),
                A("spark.validated_count", "Spark: validated = الإدخال النظيف", "INCONCLUSIVE", int(t2_eff["validated_after_run"]), s2.get("validated"),
                  evidence, note=reason),
                A("spark.quarantine_count", "Spark: quarantine = 0", "INCONCLUSIVE", int(t2_eff["quarantine"]), s2.get("quarantine"),
                  evidence, note=reason),
                A("spark.duplicates", "Spark: لا توجد Business Keys مكررة", "INCONCLUSIVE", 0, s2.get("duplicate_business_keys"),
                  evidence, note=reason),
            ]
        else:
            spark.assertions += [
                _count_assertion("spark.raw_count", "Spark raw count aggregate band", compare_count(s2.get("raw"), t2_eff["input"])),
                _count_assertion("spark.validated_count", "Spark validated count aggregate band", compare_count(s2.get("validated"), t2_eff["validated_after_run"])),
                _count_assertion("spark.quarantine_count", "Spark quarantine count exact zero", compare_count(s2.get("quarantine"), t2_eff["quarantine"])),
                assert_zero("spark.duplicates", "Spark: لا توجد Business Keys مكررة", int(s2.get("duplicate_business_keys", -1))),
            ]
        report["cases"].append(_case_dict(spark))

        # Test 03: baseline -> new/update/unchanged/quarantine -> rerun.
        _live(f"{project_id}: stage 3/5 — establish Upsert baseline")
        fresh_database()
        baseline, _ = execute_case("upsert_baseline", "test_01", fresh=False, expected_engine="python_batch")
        t3 = oracle.test("test_03")
        baseline.assertions.append(_count_assertion("upsert.baseline_validated", "Baseline reproducibility (batch correctness graded separately)",
                                                compare_baseline_replay((baseline.snapshot_after or {}).get("validated"), s1.get("validated"))))
        report["cases"].append(_case_dict(baseline))

        insert_cases = oracle.sample("test_03", actions=["insert"], n=12, seed=11)
        update_cases = oracle.sample("test_03", actions=["update"], n=12, seed=12)
        unchanged_cases = oracle.sample("test_03", actions=["unchanged"], n=12, seed=13)
        before_updates = _capture_docs(mongo, update_cases)
        before_unchanged = _capture_docs(mongo, unchanged_cases)

        _live(f"{project_id}: stage 4/5 — Upsert insert/update/unchanged")
        upsert1, _ = execute_case("upsert_first", "test_03", fresh=False)
        s31 = upsert1.snapshot_after or {}
        upsert1.assertions += [
            _count_assertion("upsert.final_validated", "Upsert inserted rows relative to existing baseline",
                                compare_new_inserts(s31.get("validated"), (upsert1.snapshot_before or {}).get("validated"), t3["inserted"])),
            assert_zero("upsert.duplicates_first", "لا توجد Business Keys مكررة بعد Upsert", int(s31.get("duplicate_business_keys", -1))),
        ]
        upsert1.assertions += _verify_upsert_actions(mongo, insert_cases, update_cases, unchanged_cases, before_updates, before_unchanged)
        _guard_unfinished_mutation_case(upsert1)
        report["cases"].append(_case_dict(upsert1))

        _live(f"{project_id}: stage 5/5 — Idempotency rerun")
        upsert2, _ = execute_case("upsert_rerun", "test_03", fresh=False)
        s32 = upsert2.snapshot_after or {}
        upsert2.assertions += [
            _count_assertion("idempotency.validated_stable", "Rerun count stable (not full idempotency proof)",
                                compare_stability(s32.get("validated"), (upsert2.snapshot_before or {}).get("validated"))),
            assert_zero("idempotency.duplicates", "إعادة التشغيل لا تنشئ Business Keys مكررة", int(s32.get("duplicate_business_keys", -1))),
        ]
        _guard_unfinished_mutation_case(upsert2)
        report["cases"].append(_case_dict(upsert2))

        if plan_b:
            t4 = oracle.test("test_04")
            inc1, _ = execute_case("incremental_first", "test_04", fresh=False)
            s41 = inc1.snapshot_after or {}
            inc1.assertions += [
                _count_assertion("incremental.final_validated", "Incremental newly inserted rows",
                                compare_new_inserts(s41.get("validated"), (inc1.snapshot_before or {}).get("validated"), t4["inserted"])),
                assert_zero("incremental.duplicates_first", "Delta لا ينشئ Business Keys مكررة", int(s41.get("duplicate_business_keys", -1))),
            ]
            _guard_unfinished_mutation_case(inc1)
            report["cases"].append(_case_dict(inc1))
            inc2, _ = execute_case("incremental_rerun", "test_04", fresh=False)
            s42 = inc2.snapshot_after or {}
            inc2.assertions += [
                _count_assertion("incremental.rerun_validated_stable", "Incremental rerun count stable (not full no-op proof)",
                                compare_stability(s42.get("validated"), (inc2.snapshot_before or {}).get("validated"))),
                assert_zero("incremental.rerun_duplicates", "إعادة Delta لا تنشئ Business Keys مكررة", int(s42.get("duplicate_business_keys", -1))),
            ]
            _guard_unfinished_mutation_case(inc2)
            report["cases"].append(_case_dict(inc2))

        assertions: dict[str, Any] = {}
        counts = {k: 0 for k in ["PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIP"]}
        for c in report["cases"]:
            for a in c.get("assertions", []):
                assertions[a["key"]] = a
                counts[a["verdict"]] = counts.get(a["verdict"], 0) + 1
        report["assertions"] = assertions
        report["assertion_counts"] = counts
        report["business_key_detected"] = mongo._existing_business_key()
        if counts.get("ERROR"):
            report["status"] = "ERROR"
        elif counts.get("FAIL"):
            report["status"] = "COMPLETED_WITH_FAILURES"
        elif counts.get("INCONCLUSIVE"):
            report["status"] = "COMPLETED_WITH_REVIEW"
        else:
            report["status"] = "PASS"
        _live(
            f"{project_id}: runtime complete | PASS={counts.get('PASS', 0)} "
            f"FAIL={counts.get('FAIL', 0)} INCONCLUSIVE={counts.get('INCONCLUSIVE', 0)} "
            f"ERROR={counts.get('ERROR', 0)}"
        )
        report["notes"] = [
            "Static file presence is supporting evidence only; runtime database state is authoritative.",
            "INCONCLUSIVE requires manual review and is never silently converted into zero marks.",
            "Teacher oracle files were not mounted into the student container.",
            "Each project used a dedicated MongoDB container and project-specific Docker network.",
        ]
        return report

    except Exception as exc:
        _live(f"{project_id}: ERROR {type(exc).__name__}: {exc}")
        report["status"] = "INFRA_OR_RUNTIME_ERROR"
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report
    finally:
        if mongo:
            mongo.close()
        if manage_sandbox and not keep_sandbox:
            try:
                _live(f"{project_id}: cleaning sandbox")
                sb.cleanup()
            except Exception as cleanup_exc:
                report.setdefault("cleanup_warnings", []).append(str(cleanup_exc))


def _case_dict(case: RuntimeCaseResult) -> dict[str, Any]:
    d = case.to_dict()
    log = getattr(case, "runtime_log", None)
    if log:
        d["run"] = log
    return d
