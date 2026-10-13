from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .models import AssertionResult, RuntimeCaseResult
from .runner import render_command, run_command
from .mongo_checker import MongoChecker
from .oracle import HiddenOracle, OracleCase
from .normalization import compare_clean_record, clean_payload, audit_entries, error_codes, semantic_equal, records_equivalent
from .runtime_evidence import find_latest_metrics, detect_engine, find_metric_value
from .spark_probe import ensure_large_clean_probe


def A(key: str, label: str, verdict: str, expected: Any = None, actual: Any = None,
      evidence: list[str] | None = None, note: str | None = None) -> AssertionResult:
    return AssertionResult(key, label, verdict, expected, actual, evidence or [], note)


def assert_equal(key: str, label: str, actual: Any, expected: Any, evidence: list[str] | None = None) -> AssertionResult:
    return A(key, label, 'PASS' if actual == expected else 'FAIL', expected, actual, evidence)


def assert_zero(key: str, label: str, actual: int) -> AssertionResult:
    return assert_equal(key, label, actual, 0)


def _env(plan, threshold_mb: float, db_name: str | None = None) -> dict[str, str]:
    env = {
        'MONGO_URI': plan.mongo_uri,
        'MONGO_DB_NAME': db_name or plan.database_name or '',
        'MONGO_DATABASE': db_name or plan.database_name or '',
        'SMALL_FILE_THRESHOLD_MB': str(threshold_mb),
        'FILE_SIZE_THRESHOLD_MB': str(threshold_mb),
        'THRESHOLD_MB': str(threshold_mb),
    }
    if plan.spark_master:
        env['SPARK_MASTER_URL'] = plan.spark_master
        env['SPARK_MASTER'] = plan.spark_master
    return env


_INCREMENTAL_STAGES = frozenset({
    'upsert_first', 'upsert_rerun', 'incremental_first', 'incremental_rerun',
})


def _documented_incremental_command(command: str, repo: Path, stage: str | None) -> str:
    """Honor a safe documented CLI no-reset flag on only incremental stages.

    Do not attempt arbitrary commands/flags from a student's README. The flag
    must be documented *and* declared in the same frozen source entrypoint.
    """
    if stage not in _INCREMENTAL_STAGES or '--no-reset' in command:
        return command
    # Apply only to a directly invoked, known CLI entrypoint; no shell chains.
    parts = command.split()
    if len(parts) < 2 or parts[0] not in ('python', 'python3') or parts[1] != 'src/main.py':
        return command
    if any(operator in command for operator in ('&&', ';', '|', '>', '<')):
        return command
    readme = repo / 'README.md'
    source = repo / 'src' / 'main.py'
    if not readme.is_file() or not source.is_file():
        return command
    try:
        docs = readme.read_text(encoding='utf-8-sig', errors='replace')
        code = source.read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return command
    if '--no-reset' in docs and ("'--no-reset'" in code or '"--no-reset"' in code):
        return command + ' --no-reset'
    return command


def _run_ingest(plan, repo: Path, file: Path, threshold: float, timeout: int, venv: str | Path | None, db_name: str | None = None, stage: str | None = None):
    effective_db = db_name or plan.database_name
    cmd = render_command(plan.ingest_command, file=file, threshold_mb=threshold, db_name=effective_db)
    cmd = _documented_incremental_command(cmd, repo, stage)
    result = run_command(cmd, repo, timeout=timeout, env=_env(plan, threshold, effective_db), venv=venv)
    metrics, metrics_path = find_latest_metrics(repo)
    return cmd, result, metrics, metrics_path


def _run_setup(plan, repo: Path, timeout: int, venv: str | Path | None, db_name: str | None = None) -> dict | None:
    if not plan.setup_command:
        return None
    result = run_command(plan.setup_command, repo, timeout=min(timeout, 300), env=_env(plan, plan.threshold_mb or 20, db_name), venv=venv)
    return result.to_dict()


def _execution_assertion(name: str, result) -> AssertionResult:
    evidence = [f'returncode={result.returncode}', f'elapsed={result.elapsed_seconds:.3f}s']
    if result.timed_out:
        return A(f'{name}.command', 'انتهاء تشغيل المشروع دون Timeout', 'FAIL', 'returncode=0', 'TIMEOUT', evidence)
    return A(f'{name}.command', 'انتهاء تشغيل المشروع بنجاح', 'PASS' if result.ok else 'FAIL', 0, result.returncode, evidence,
             None if result.ok else (result.stderr[-800:] or result.stdout[-800:]))


def _engine_assertion(name: str, engine: str | None, expected: str, evidence: list[str], plan) -> AssertionResult:
    if engine is None:
        return A(f'{name}.engine', f'استخدام المحرك المتوقع: {expected}', 'INCONCLUSIVE', expected, None, evidence,
                 'لم أجد دليل Runtime كافيًا في metrics/MongoDB/console؛ لا تُحسب كرسوب تلقائي.')
    return A(f'{name}.engine', f'استخدام المحرك المتوقع: {expected}', 'PASS' if engine == expected else 'FAIL', expected, engine, evidence,
             'تم ضبط حد الاختبار عبر CLI/Environment عندما يدعم المشروع ذلك.')


# Cleaning-style sample checks are deliberately tolerant: the assignment does not fix exact canonical
# spellings, so only a clearly low match rate is a failure and the middle band stays 'review'.
SAMPLE_PASS_AT = .70
SAMPLE_FAIL_BELOW = .40


def _ratio_assertion(key: str, label: str, passed: int, total: int, pass_at: float = .80, fail_below: float = .50,
                     evidence: list[str] | None = None) -> AssertionResult:
    if total == 0:
        return A(key, label, 'INCONCLUSIVE', None, None, evidence, 'لا توجد حالات قابلة للتحقق.')
    ratio = passed / total
    verdict = 'PASS' if ratio >= pass_at else ('FAIL' if ratio < fail_below else 'INCONCLUSIVE')
    return A(key, label, verdict, f'>={pass_at:.0%}', f'{passed}/{total} ({ratio:.0%})', evidence)


def _verify_clean_samples(mongo: MongoChecker, cases: list[OracleCase]) -> tuple[AssertionResult, AssertionResult]:
    checked = good = audit_good = 0
    evidence: list[str] = []
    audit_evidence: list[str] = []
    for case in cases:
        if not case.expected_order_id or not case.expected_clean_record:
            continue
        checked += 1
        doc = mongo.find_validated(case.expected_order_id)
        ok, notes = compare_clean_record(doc, case.expected_clean_record)
        if ok:
            good += 1
        elif len(evidence) < 8:
            evidence.append(f'{case.expected_order_id}: ' + ('; '.join(notes) if notes else 'not found'))
        external_audit = getattr(mongo, 'external_audit', None)
        if doc and (audit_entries(doc) or (callable(external_audit) and external_audit(case.expected_order_id))):
            audit_good += 1
        elif len(audit_evidence) < 8:
            audit_evidence.append(f'{case.expected_order_id}: no audit entries')
    return (
        _ratio_assertion('batch.cleaning_samples', 'عينات Cleaning مطابقة للـOracle', good, checked, pass_at=SAMPLE_PASS_AT, fail_below=SAMPLE_FAIL_BELOW, evidence=evidence),
        _ratio_assertion('batch.audit_trail', 'Audit Trail موجود للحالات المصححة', audit_good, checked, pass_at=SAMPLE_PASS_AT, fail_below=SAMPLE_FAIL_BELOW, evidence=audit_evidence),
    )


def _verify_quarantine_evidence(mongo: MongoChecker) -> AssertionResult:
    docs = mongo.sample_docs('quarantine', 40)
    if not docs:
        return A('batch.quarantine_errors', 'سجلات Quarantine تحتوي أسباب/أكواد خطأ', 'FAIL', 'non-empty', 0)
    good = sum(1 for d in docs if error_codes(d))
    return _ratio_assertion('batch.quarantine_errors', 'سجلات Quarantine تحتوي أسباب/أكواد خطأ', good, len(docs), pass_at=.75, fail_below=.30)


def _capture_docs(mongo: MongoChecker, cases: list[OracleCase]) -> dict[str, dict[str, Any] | None]:
    return {c.expected_order_id: mongo.find_validated(c.expected_order_id) for c in cases if c.expected_order_id}


def _verify_upsert_actions(mongo: MongoChecker, inserts: list[OracleCase], updates: list[OracleCase], unchanged: list[OracleCase],
                           before_updates: dict[str, dict[str, Any] | None], before_unchanged: dict[str, dict[str, Any] | None]) -> list[AssertionResult]:
    out: list[AssertionResult] = []

    ins_good = ins_total = 0
    ins_ev = []
    for c in inserts:
        if not c.expected_clean_record:
            continue
        ins_total += 1
        doc = mongo.find_validated(c.expected_order_id)
        ok, notes = compare_clean_record(doc, c.expected_clean_record)
        if ok:
            ins_good += 1
        elif len(ins_ev) < 6:
            ins_ev.append(f'{c.expected_order_id}: {"; ".join(notes) or "not found"}')
    out.append(_ratio_assertion('upsert.insert_samples', 'عينات Insert الجديدة صحيحة', ins_good, ins_total, pass_at=SAMPLE_PASS_AT, fail_below=SAMPLE_FAIL_BELOW, evidence=ins_ev))

    upd_good = upd_total = 0
    upd_ev = []
    for c in updates:
        if not c.expected_clean_record:
            continue
        upd_total += 1
        before = clean_payload(before_updates.get(c.expected_order_id))
        after_doc = mongo.find_validated(c.expected_order_id)
        after = clean_payload(after_doc)
        matches, notes = compare_clean_record(after_doc, c.expected_clean_record)
        changed = bool(before) and not records_equivalent(before_updates.get(c.expected_order_id), after_doc)
        if matches and changed:
            upd_good += 1
        elif len(upd_ev) < 6:
            upd_ev.append(f'{c.expected_order_id}: matches={matches}, changed={changed}; {"; ".join(notes)}')
    out.append(_ratio_assertion('upsert.update_samples', 'عينات Update غيّرت السجل الموجود إلى القيمة المتوقعة', upd_good, upd_total, pass_at=SAMPLE_PASS_AT, fail_below=SAMPLE_FAIL_BELOW, evidence=upd_ev))

    same_good = same_total = 0
    same_ev = []
    for c in unchanged:
        same_total += 1
        before = clean_payload(before_unchanged.get(c.expected_order_id))
        after = clean_payload(mongo.find_validated(c.expected_order_id))
        ok = bool(before) and records_equivalent(before_unchanged.get(c.expected_order_id), mongo.find_validated(c.expected_order_id))
        if ok:
            same_good += 1
        elif len(same_ev) < 6:
            same_ev.append(f'{c.expected_order_id}: business payload changed or record missing')
    out.append(_ratio_assertion('upsert.unchanged_samples', 'عينات Unchanged بقيت دون تغيير في بيانات الأعمال', same_good, same_total, pass_at=SAMPLE_PASS_AT, fail_below=SAMPLE_FAIL_BELOW, evidence=same_ev))
    return out


def _metrics_assertions(prefix: str, metrics: dict[str, Any] | None, expected: dict[str, int], metrics_path: str | None) -> list[AssertionResult]:
    if not metrics:
        return [A(f'{prefix}.metrics_present', 'إنتاج Metrics/Report قابل للقراءة', 'INCONCLUSIVE', 'JSON metrics', None,
                  note='لم أعثر على ملف JSON قياسي؛ قد يكون المشروع يسجل المقاييس بصيغة أخرى.')]
    out = [A(f'{prefix}.metrics_present', 'إنتاج Metrics/Report قابل للقراءة', 'PASS', 'JSON metrics', metrics_path, [metrics_path or 'metrics'])]
    aliases = {
        'input': ('read_rows', 'raw_count', 'raw_rows', 'loaded_raw', 'rows_read', 'input_rows', 'processed'),
        'quarantine': ('count_quarantine', 'quarantine_count', 'quarantined', 'quarantine'),
        'inserted': ('count_inserted', 'inserted_count', 'inserted'),
        'updated': ('count_updated', 'updated_count', 'updated'),
        'unchanged': ('count_unchanged', 'unchanged_count', 'unchanged'),
    }
    for name, exp in expected.items():
        value = find_metric_value(metrics, aliases.get(name, (name,)))
        if value is None:
            out.append(A(f'{prefix}.metric_{name}', f'Metric {name}', 'INCONCLUSIVE', exp, None, [metrics_path or 'metrics']))
            continue
        try:
            actual = int(value)
        except Exception:
            actual = value
        out.append(assert_equal(f'{prefix}.metric_{name}', f'Metric {name}', actual, exp, [metrics_path or 'metrics']))
    return out


def run_midterm_runtime(plan, repo_path: Path, hidden_dir: Path, oracle: HiddenOracle, timeout: int = 900,
                        venv: str | Path | None = None, run_plan_b: bool = False,
                        database_override: str | None = None) -> dict:
    """Execute the student's real project against hidden data, then independently verify MongoDB state.

    This is behavior-first grading: static files are evidence only. A feature passes here only when the
    student's entrypoint runs and the resulting database state matches the hidden oracle.
    """
    if not plan.ingest_command:
        return {'status': 'MANUAL_REVIEW', 'reason': 'No ingest command discovered. Add grader.yaml or review README manually.'}
    if not plan.database_name:
        return {'status': 'MANUAL_REVIEW', 'reason': 'Mongo database name not discovered. Add grader.yaml or explicit config.'}

    effective_db = database_override if (database_override and plan.database_configurable) else plan.database_name
    try:
        mongo = MongoChecker(plan.mongo_uri, effective_db, plan.collections, business_key=plan.business_key)
        mongo.ping()
    except Exception as exc:
        return {'status': 'INFRA_ERROR', 'reason': f'Cannot initialize/connect to MongoDB: {exc}', 'mongo_uri': plan.mongo_uri}

    threshold = oracle.threshold_mb
    cases: list[RuntimeCaseResult] = []
    setup_runs: list[dict] = []

    def fresh_database():
        mongo.drop_database()
        setup = _run_setup(plan, repo_path, timeout, venv, effective_db)
        if setup:
            setup_runs.append(setup)

    def clear_data():
        mongo.clear_documents()

    def execute_case(case_name: str, test_key: str, fresh: bool, expected_engine: str | None = None,
                     file_override: Path | None = None, spec_override: dict | None = None,
                     threshold_override: float | None = None) -> tuple[RuntimeCaseResult, dict, str | None]:
        if fresh:
            fresh_database()
        spec = dict(spec_override or oracle.test(test_key))
        file_path = file_override or (hidden_dir / spec['file'])
        effective_threshold = threshold if threshold_override is None else threshold_override
        before = mongo.snapshot().to_dict()
        cmd, result, metrics, metrics_path = _run_ingest(plan, repo_path, file_path, effective_threshold, timeout, venv, effective_db, stage=case_name)
        after = mongo.snapshot().to_dict()
        engine, engine_ev = detect_engine(result.stdout, result.stderr, metrics, mongo.distinct_engine_values())
        if file_override:
            engine_ev = [f'probe:{file_path.name} size={file_path.stat().st_size/(1024*1024):.1f}MB threshold={effective_threshold}MB'] + engine_ev
        case = RuntimeCaseResult(case_name, cmd, result, before, after, engine, engine_ev, metrics)
        case.assertions.append(_execution_assertion(case_name, result))
        if expected_engine:
            eng_assert = _engine_assertion(case_name, engine, expected_engine, engine_ev, plan)
            file_mb = file_path.stat().st_size / (1024 * 1024)
            if expected_engine == 'pyspark' and file_mb <= effective_threshold and not plan.threshold_configurable:
                eng_assert.verdict = 'INCONCLUSIVE'
                eng_assert.note = (f'ملف الاختبار حجمه {file_mb:.1f}MB ولم يتجاوز Threshold المشروع '
                                   f'{effective_threshold:.1f}MB، لذلك لا أعتبر اختيار Batch رسوبًا في Spark.')
            if expected_engine == 'python_batch' and file_mb > effective_threshold and not plan.threshold_configurable:
                eng_assert.verdict = 'INCONCLUSIVE'
                eng_assert.note = (f'ملف الاختبار حجمه {file_mb:.1f}MB وهو أكبر من Threshold المشروع '
                                   f'{effective_threshold:.1f}MB، لذلك هذا الملف لا يستطيع إثبات مسار Batch بعدل.')
            case.assertions.append(eng_assert)
        return case, spec, metrics_path

    # Test 01 — Batch + full pipeline
    batch, t1, t1_metrics_path = execute_case('batch_pipeline', 'test_01', True, 'python_batch')
    s = batch.snapshot_after or {}
    batch.assertions += [
        assert_equal('batch.raw_count', 'orders_raw = عدد صفوف الإدخال', s.get('raw'), int(t1['input'])),
        assert_equal('batch.validated_count', 'orders_validated = النتيجة المتوقعة', s.get('validated'), int(t1['validated_after_run'])),
        assert_equal('batch.quarantine_count', 'orders_quarantine = النتيجة المتوقعة', s.get('quarantine'), int(t1['quarantine'])),
        assert_zero('batch.duplicates', 'لا توجد Business Keys مكررة في validated', int(s.get('duplicate_business_keys', -1))),
    ]
    unique_ok, unique_ev = mongo.has_unique_business_index()
    batch.assertions.append(A('batch.unique_index_runtime', 'Unique Index موجود فعليًا على Business Key', 'PASS' if unique_ok else 'FAIL', True, unique_ok, unique_ev))
    batch.assertions.append(A('batch.schema_validator_runtime', '$jsonSchema Validator موجود فعليًا على validated', 'PASS' if mongo.has_json_schema_validator() else 'INCONCLUSIVE', True, mongo.has_json_schema_validator(),
                              note='INCONCLUSIVE لا يعني رسوبًا إذا لم يكن الـvalidator جزءًا إلزاميًا في rubric النهائية.'))
    clean_cases = oracle.sample('test_01', classes=['correctable'], n=18)
    clean_a, audit_a = _verify_clean_samples(mongo, clean_cases)
    batch.assertions += [clean_a, audit_a, _verify_quarantine_evidence(mongo)]
    batch.assertions += _metrics_assertions('batch', batch.metrics, {'input': int(t1['input']), 'quarantine': int(t1['quarantine'])}, t1_metrics_path)
    cases.append(batch)

    # Test 02 — Spark path. If a project hard-codes a threshold above the bundled file size,
    # generate a clean probe that really crosses *that student's* threshold instead of falsely failing it.
    clear_data()
    t2 = oracle.test('test_02')
    spark_file = hidden_dir / t2['file']
    spark_spec = dict(t2)
    spark_threshold = threshold
    if not plan.threshold_configurable and plan.threshold_mb:
        spark_threshold = float(plan.threshold_mb)
        if spark_file.stat().st_size / (1024 * 1024) <= spark_threshold:
            probe, rows, reason = ensure_large_clean_probe(spark_file, hidden_dir / '_generated', spark_threshold)
            if probe != spark_file:
                spark_file = probe
                spark_spec = dict(t2)
                spark_spec.update({'input': rows, 'validated_after_run': rows, 'quarantine': 0, 'probe_reason': reason})
    spark, t2, t2_metrics_path = execute_case('spark_pipeline', 'test_02', False, 'pyspark',
                                               file_override=spark_file, spec_override=spark_spec,
                                               threshold_override=spark_threshold)
    s = spark.snapshot_after or {}
    spark.assertions += [
        assert_equal('spark.raw_count', 'Spark: orders_raw = الإدخال', s.get('raw'), int(t2['input'])),
        assert_equal('spark.validated_count', 'Spark: validated = الإدخال النظيف', s.get('validated'), int(t2['validated_after_run'])),
        assert_equal('spark.quarantine_count', 'Spark: quarantine = 0', s.get('quarantine'), int(t2['quarantine'])),
        assert_zero('spark.duplicates', 'Spark: لا توجد Business Keys مكررة', int(s.get('duplicate_business_keys', -1))),
    ]
    spark.assertions += _metrics_assertions('spark', spark.metrics, {'input': int(t2['input']), 'quarantine': int(t2['quarantine'])}, t2_metrics_path)
    cases.append(spark)

    # Test 03 — baseline -> insert/update/unchanged -> rerun
    fresh_database()
    baseline, _, _ = execute_case('upsert_baseline', 'test_01', False, 'python_batch')
    baseline.assertions += [assert_equal('upsert.baseline_validated', 'Baseline validated قبل Test 03', (baseline.snapshot_after or {}).get('validated'), int(oracle.test('test_03')['baseline_validated_before_test']))]
    cases.append(baseline)

    insert_cases = oracle.sample('test_03', actions=['insert'], n=12, seed=11)
    update_cases = oracle.sample('test_03', actions=['update'], n=12, seed=12)
    unchanged_cases = oracle.sample('test_03', actions=['unchanged'], n=12, seed=13)
    before_updates = _capture_docs(mongo, update_cases)
    before_unchanged = _capture_docs(mongo, unchanged_cases)

    upsert1, t3, t3_metrics_path = execute_case('upsert_first', 'test_03', False, None)
    s31 = upsert1.snapshot_after or {}
    upsert1.assertions += [
        assert_equal('upsert.final_validated', 'Validated بعد أول Test 03', s31.get('validated'), int(t3['validated_after_first_run'])),
        assert_zero('upsert.duplicates_first', 'لا توجد Business Keys مكررة بعد Upsert', int(s31.get('duplicate_business_keys', -1))),
    ]
    upsert1.assertions += _verify_upsert_actions(mongo, insert_cases, update_cases, unchanged_cases, before_updates, before_unchanged)
    upsert1.assertions += _metrics_assertions('upsert', upsert1.metrics, {
        'inserted': int(t3['inserted']), 'updated': int(t3['updated']), 'unchanged': int(t3['unchanged']), 'quarantine': int(t3['quarantine'])
    }, t3_metrics_path)
    cases.append(upsert1)

    upsert2, _, _ = execute_case('upsert_rerun', 'test_03', False, None)
    s32 = upsert2.snapshot_after or {}
    upsert2.assertions += [
        assert_equal('idempotency.validated_stable', 'إعادة Test 03 لا تغيّر عدد validated', s32.get('validated'), int(t3['validated_after_rerun'])),
        assert_zero('idempotency.duplicates', 'إعادة التشغيل لا تنشئ Business Keys مكررة', int(s32.get('duplicate_business_keys', -1))),
    ]
    cases.append(upsert2)

    # Optional Test 04 — incremental/Plan B
    if run_plan_b:
        inc1, t4, t4_metrics_path = execute_case('incremental_first', 'test_04', False, None)
        s41 = inc1.snapshot_after or {}
        inc1.assertions += [
            assert_equal('incremental.final_validated', 'Validated بعد Delta Test 04', s41.get('validated'), int(t4['validated_after_first_run'])),
            assert_zero('incremental.duplicates_first', 'Delta لا ينشئ Business Keys مكررة', int(s41.get('duplicate_business_keys', -1))),
        ]
        inc1.assertions += _metrics_assertions('incremental', inc1.metrics, {
            'inserted': int(t4['inserted']), 'updated': int(t4['updated']), 'unchanged': int(t4['unchanged']), 'quarantine': int(t4['quarantine'])
        }, t4_metrics_path)
        cases.append(inc1)
        inc2, _, _ = execute_case('incremental_rerun', 'test_04', False, None)
        s42 = inc2.snapshot_after or {}
        inc2.assertions += [
            assert_equal('incremental.rerun_validated_stable', 'إعادة Delta لا تغيّر validated', s42.get('validated'), int(t4['validated_after_rerun'])),
            assert_zero('incremental.rerun_duplicates', 'إعادة Delta لا تنشئ Business Keys مكررة', int(s42.get('duplicate_business_keys', -1))),
        ]
        cases.append(inc2)

    # Aggregate verdict and a machine-readable assertion index.
    all_assertions = [a for c in cases for a in c.assertions]
    counts = {k: sum(1 for a in all_assertions if a.verdict == k) for k in ['PASS', 'FAIL', 'INCONCLUSIVE', 'ERROR', 'SKIP']}
    if counts['ERROR']:
        status = 'ERROR'
    elif counts['FAIL']:
        status = 'COMPLETED_WITH_FAILURES'
    elif counts['INCONCLUSIVE']:
        status = 'COMPLETED_WITH_REVIEW'
    else:
        status = 'PASS'

    payload = {
        'status': status,
        'grading_mode': 'behavior_first_runtime',
        'database': effective_db,
        'database_original': plan.database_name,
        'database_isolated': bool(database_override and plan.database_configurable),
        'business_key_detected': mongo._existing_business_key(),
        'threshold_mb_used': threshold,
        'setup_runs': setup_runs,
        'assertion_counts': counts,
        'cases': [c.to_dict() for c in cases],
        'assertions': {a.key: a.to_dict() for a in all_assertions},
        'notes': [
            'Static file presence is not authoritative; runtime database state is.',
            'INCONCLUSIVE is routed to manual review and should not automatically deduct marks.',
            'orders_raw may be append-only on rerun; idempotency is judged primarily from validated state and duplicate business keys.',
        ],
    }
    mongo.close()
    return payload
