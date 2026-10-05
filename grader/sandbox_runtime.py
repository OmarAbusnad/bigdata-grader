from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .models import ExecutionPlan, RuntimeCaseResult
from .mongo_checker import MongoChecker
from .oracle import HiddenOracle
from .runtime_evidence import detect_engine
from .sandbox import DockerSandbox, SandboxConfig, SandboxError
from .spark_probe import ensure_large_clean_probe
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


def _render_command(plan: ExecutionPlan, file_rel: str, db_name: str, threshold_mb: float | None) -> str:
    if not plan.ingest_command:
        raise SandboxError("No ingest command was resolved")
    cmd = plan.ingest_command
    cmd = cmd.replace("{file}", f"/grader-tests/{file_rel}")
    cmd = cmd.replace("{db_name}", db_name)
    cmd = cmd.replace("{threshold_mb}", str(threshold_mb if threshold_mb is not None else 200))
    if any(x in cmd for x in ["&&", "||", ";", "|", ">", "<", "`", "$("]):
        raise SandboxError("Unsafe shell metacharacters detected in resolved command")
    return cmd


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
        shutil.copy2(src, dst)
        mapping[test_name] = dst.name
    return mapping


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
) -> dict[str, Any]:
    """Behavior-first midterm suite in Docker with host-side independent Mongo verification."""
    if not plan.ingest_command:
        return {"status": "MANUAL_REVIEW_REQUIRED", "reason": "No ingest command resolved"}

    inputs_dir = base / "sandboxes" / project_id / "input_view"
    input_names = _copy_input_view(hidden_dir, oracle, inputs_dir)

    safe_pid = "".join(c if c.isalnum() else "_" for c in project_id).lower()
    effective_db = f"grader_{safe_pid}" if plan.database_configurable else (plan.database_name or f"grader_{safe_pid}")
    # Hidden discussion datasets are calibrated around the instructor's
    # recommended threshold (currently 20 MB). If the student's threshold is
    # configurable, drive the project with that discussion threshold so Test 01
    # proves Batch and Test 02 proves Spark. Only fall back to the student's
    # hard-coded threshold when it is not configurable.
    threshold = float(oracle.threshold_mb if plan.threshold_configurable else (plan.threshold_mb or oracle.threshold_mb))

    sb = DockerSandbox(base, project_id, repo, inputs_dir, sandbox_config)
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
        build = sb.build()
        report["build"] = build
        if not build["ok"]:
            report["status"] = "DEPENDENCY_BUILD_ERROR"
            return report

        report["sandbox_start"] = sb.start()
        if not sb.mongo_host_uri:
            raise SandboxError("MongoDB grader-side host URI was not established")

        mongo = MongoChecker(sb.mongo_host_uri, effective_db, plan.collections, business_key=plan.business_key or "order_id")
        mongo.ping()

        def run_setup() -> None:
            if not plan.setup_command:
                return
            env = {
                "MONGO_DB_NAME": effective_db,
                "MONGO_DATABASE": effective_db,
                "DATABASE_NAME": effective_db,
                "SMALL_FILE_THRESHOLD_MB": str(threshold),
                "FILE_SIZE_THRESHOLD_MB": str(threshold),
                "THRESHOLD_MB": str(threshold),
            }
            r = sb.run_student(plan.setup_command, env=env, timeout=min(timeout, 300))
            report["setup_runs"].append({**r, "stdout": r.get("stdout", "")[-8000:], "stderr": r.get("stderr", "")[-8000:]})

        def fresh_database() -> None:
            mongo.drop_database()
            run_setup()

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
                "SMALL_FILE_THRESHOLD_MB": str(effective_threshold),
                "FILE_SIZE_THRESHOLD_MB": str(effective_threshold),
                "THRESHOLD_MB": str(effective_threshold),
                "GRADER_RUN": "1",
            }
            run = sb.run_student(cmd, env=env, timeout=timeout)
            after = mongo.snapshot().to_dict()
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
            }
            return case, spec

        # Test 01: Batch + full ELT behavior.
        batch, t1 = execute_case("batch_pipeline", "test_01", fresh=True, expected_engine="python_batch")
        s1 = batch.snapshot_after or {}
        batch.assertions += [
            assert_equal("batch.raw_count", "orders_raw = عدد صفوف الإدخال", s1.get("raw"), int(t1["input"])),
            assert_equal("batch.validated_count", "orders_validated = النتيجة المتوقعة", s1.get("validated"), int(t1["validated_after_run"])),
            assert_equal("batch.quarantine_count", "orders_quarantine = النتيجة المتوقعة", s1.get("quarantine"), int(t1["quarantine"])),
            assert_zero("batch.duplicates", "لا توجد Business Keys مكررة", int(s1.get("duplicate_business_keys", -1))),
        ]
        unique_ok, unique_ev = mongo.has_unique_business_index()
        batch.assertions.append(A("batch.unique_index_runtime", "Unique Index فعلي على Business Key", "PASS" if unique_ok else "FAIL", True, unique_ok, unique_ev))
        schema_ok = mongo.has_json_schema_validator()
        batch.assertions.append(A("batch.schema_validator_runtime", "$jsonSchema Validator فعلي على validated", "PASS" if schema_ok else "INCONCLUSIVE", True, schema_ok,
                                  note="عدم إثبات الـvalidator لا يتحول إلى خصم تلقائي ما لم ينص الـRubric الرسمي عليه."))
        clean_cases = oracle.sample("test_01", classes=["correctable"], n=18)
        clean_a, audit_a = _verify_clean_samples(mongo, clean_cases)
        batch.assertions += [clean_a, audit_a, _verify_quarantine_evidence(mongo)]
        report["cases"].append(_case_dict(batch))

        # Test 02: Spark. Generate a larger clean probe if a hard-coded threshold requires it.
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
        spark.assertions += [
            assert_equal("spark.raw_count", "Spark: orders_raw = الإدخال", s2.get("raw"), int(t2_eff["input"])),
            assert_equal("spark.validated_count", "Spark: validated = الإدخال النظيف", s2.get("validated"), int(t2_eff["validated_after_run"])),
            assert_equal("spark.quarantine_count", "Spark: quarantine = 0", s2.get("quarantine"), int(t2_eff["quarantine"])),
            assert_zero("spark.duplicates", "Spark: لا توجد Business Keys مكررة", int(s2.get("duplicate_business_keys", -1))),
        ]
        report["cases"].append(_case_dict(spark))

        # Test 03: baseline -> new/update/unchanged/quarantine -> rerun.
        fresh_database()
        baseline, _ = execute_case("upsert_baseline", "test_01", fresh=False, expected_engine="python_batch")
        t3 = oracle.test("test_03")
        baseline.assertions.append(assert_equal("upsert.baseline_validated", "Baseline validated قبل Test 03",
                                                (baseline.snapshot_after or {}).get("validated"), int(t3["baseline_validated_before_test"])))
        report["cases"].append(_case_dict(baseline))

        insert_cases = oracle.sample("test_03", actions=["insert"], n=12, seed=11)
        update_cases = oracle.sample("test_03", actions=["update"], n=12, seed=12)
        unchanged_cases = oracle.sample("test_03", actions=["unchanged"], n=12, seed=13)
        before_updates = _capture_docs(mongo, update_cases)
        before_unchanged = _capture_docs(mongo, unchanged_cases)

        upsert1, _ = execute_case("upsert_first", "test_03", fresh=False)
        s31 = upsert1.snapshot_after or {}
        upsert1.assertions += [
            assert_equal("upsert.final_validated", "Validated بعد أول Test 03", s31.get("validated"), int(t3["validated_after_first_run"])),
            assert_zero("upsert.duplicates_first", "لا توجد Business Keys مكررة بعد Upsert", int(s31.get("duplicate_business_keys", -1))),
        ]
        upsert1.assertions += _verify_upsert_actions(mongo, insert_cases, update_cases, unchanged_cases, before_updates, before_unchanged)
        report["cases"].append(_case_dict(upsert1))

        upsert2, _ = execute_case("upsert_rerun", "test_03", fresh=False)
        s32 = upsert2.snapshot_after or {}
        upsert2.assertions += [
            assert_equal("idempotency.validated_stable", "إعادة Test 03 لا تغيّر validated", s32.get("validated"), int(t3["validated_after_rerun"])),
            assert_zero("idempotency.duplicates", "إعادة التشغيل لا تنشئ Business Keys مكررة", int(s32.get("duplicate_business_keys", -1))),
        ]
        report["cases"].append(_case_dict(upsert2))

        if plan_b:
            t4 = oracle.test("test_04")
            inc1, _ = execute_case("incremental_first", "test_04", fresh=False)
            s41 = inc1.snapshot_after or {}
            inc1.assertions += [
                assert_equal("incremental.final_validated", "Validated بعد Delta Test 04", s41.get("validated"), int(t4["validated_after_first_run"])),
                assert_zero("incremental.duplicates_first", "Delta لا ينشئ Business Keys مكررة", int(s41.get("duplicate_business_keys", -1))),
            ]
            report["cases"].append(_case_dict(inc1))
            inc2, _ = execute_case("incremental_rerun", "test_04", fresh=False)
            s42 = inc2.snapshot_after or {}
            inc2.assertions += [
                assert_equal("incremental.rerun_validated_stable", "إعادة Delta لا تغيّر validated", s42.get("validated"), int(t4["validated_after_rerun"])),
                assert_zero("incremental.rerun_duplicates", "إعادة Delta لا تنشئ Business Keys مكررة", int(s42.get("duplicate_business_keys", -1))),
            ]
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
        report["notes"] = [
            "Static file presence is supporting evidence only; runtime database state is authoritative.",
            "INCONCLUSIVE requires manual review and is never silently converted into zero marks.",
            "Teacher oracle files were not mounted into the student container.",
            "Each project used a dedicated MongoDB container and project-specific Docker network.",
        ]
        return report

    except Exception as exc:
        report["status"] = "INFRA_OR_RUNTIME_ERROR"
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report
    finally:
        if mongo:
            mongo.close()
        if not keep_sandbox:
            try:
                sb.cleanup()
            except Exception as cleanup_exc:
                report.setdefault("cleanup_warnings", []).append(str(cleanup_exc))


def _case_dict(case: RuntimeCaseResult) -> dict[str, Any]:
    d = case.to_dict()
    log = getattr(case, "runtime_log", None)
    if log:
        d["run"] = log
    return d
