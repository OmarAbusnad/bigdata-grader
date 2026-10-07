from __future__ import annotations

from pathlib import Path

from grader.api_semantic_normalizer import deterministic_normalize
from grader.final_compliance import (
    meaningful_payload,
    readme_contract,
    explain_compliance,
    job_log_compliance,
)
from grader.final_runtime import _blocked_assertions


def test_semantic_normalizer_understands_object_map():
    body = {
        "queries_count": 5,
        "queries": {
            "q1": {"description": "one"},
            "q2": {"description": "two"},
            "q3": {"description": "three"},
            "q4": {"description": "four"},
            "q5": {"description": "five"},
        },
    }
    result = deterministic_normalize("queries", body)
    assert result["declared_count"] == 5
    assert result["names"] == ["q1", "q2", "q3", "q4", "q5"]
    assert result["source"] == "deterministic"


def test_meaningful_payload_prefers_deterministic_evidence():
    result = meaningful_payload({"data": [{"city": "Sanaa", "total_sales": 1234}]})
    assert result["supported"] is True
    assert result["source"] == "deterministic"


def test_readme_contract_requires_all_phase2_topics_and_env(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("MONGO_URI=mongodb://localhost\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        """
# Install
pip install -r requirements.txt

# Run
uvicorn src.api:app --port 8000

FastAPI /health /docs
Queries and Indexes with Explain executionStats
Aggregation reports
Materialized Views with refresh-mv
Scheduled Jobs with cron schedule
""",
        encoding="utf-8",
    )
    result = readme_contract(tmp_path)
    assert result["covered_topics"] == result["required_topics"]
    assert result["env_example"] is True
    assert result["requirements"] is True
    assert result["source"] == "deterministic"


def test_explain_compliance_three_cases_before_after_and_rationale(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        """
Explain executionStats before indexes and after indexes.
Reason for choosing each index and its effect on examinedDocs and execution time.
قبل إنشاء الفهارس وبعد إنشاء الفهارس مع توضيح سبب الاختيار والأثر.
""",
        encoding="utf-8",
    )
    (tmp_path / "queries.py").write_text(
        '''
db.command("explain", {"find": "orders", "filter": {"city": "Sanaa"}}, verbosity="executionStats")
db.command("explain", {"find": "orders", "filter": {"status": "Delivered"}}, verbosity="executionStats")
db.command("explain", {"find": "orders", "filter": {"customer_id": "C1"}}, verbosity="executionStats")
''',
        encoding="utf-8",
    )
    result = explain_compliance(tmp_path)
    assert result["supported"] is True
    assert result["query_count"] >= 3
    assert result["before_after"] is True
    assert result["rationale"] is True


def test_job_log_compliance_requires_four_fields():
    result = job_log_compliance([
        {
            "job": "refresh",
            "started_at": "2026-10-06T10:00:00",
            "finished_at": "2026-10-06T10:00:02",
            "status": "success",
            "result": {"updated": 3},
        }
    ])
    assert result["supported"] is True
    assert result["source"] == "deterministic"


def test_startup_gate_blocks_dependents_instead_of_cascade_fails():
    blocked = _blocked_assertions("STUDENT_DEPENDENCY_FAILURE")
    assert blocked
    assert all(x["verdict"] == "INCONCLUSIVE" for x in blocked)
    assert all(x["actual"] == "BLOCKED" for x in blocked)


def test_setup_discovery_rejects_tree_diagram(tmp_path: Path):
    from grader.discovery import discover_execution_plan

    (tmp_path / "README.md").write_text(
        """
Project tree:
|-- src/
|   |-- mongo_setup.py                # init indexes

Run:
python main.py --input data.csv
""",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        'import argparse\np=argparse.ArgumentParser()\np.add_argument("--input")\n',
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mongo_setup.py").write_text("print('setup')\n", encoding="utf-8")
    plan = discover_execution_plan(tmp_path)
    assert plan.setup_command == "python src/mongo_setup.py"


def test_meaningful_payload_does_not_accept_labels_only():
    result = meaningful_payload({"query_name": "q1", "title": "My Query", "status": "SUCCESS"})
    assert result["supported"] is not True


def test_startup_classifier_detects_missing_declared_dependency(tmp_path: Path):
    from grader.final_runtime import _classify_startup_failure

    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    result = _classify_startup_failure(
        tmp_path,
        {
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'tqdm'",
            "timed_out": False,
        },
    )
    assert result["code"] == "STUDENT_DEPENDENCY_FAILURE"


def test_final_discovery_uses_documented_uvicorn_target_without_agent(tmp_path: Path):
    from grader.final_discovery import discover_final_plan

    (tmp_path / "README.md").write_text(
        "Run:\nuvicorn src.api:app --host 127.0.0.1 --port 8000\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'ok': True}\n",
        encoding="utf-8",
    )
    plan = discover_final_plan(tmp_path)
    assert plan["api_target"] == "src.api:app"
    assert plan["api_target_source"] == "readme"
    assert plan["requires_agent"] is False


def test_midterm_plan_skips_agent_when_deterministic_is_strong(tmp_path: Path, monkeypatch):
    from grader.plan_resolution import resolve_execution_plan

    (tmp_path / "README.md").write_text("python main.py --input data.csv\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pymongo\n", encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "import argparse\np=argparse.ArgumentParser()\np.add_argument('--input')\np.parse_args()\n",
        encoding="utf-8",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("agent should not be called for a strong deterministic plan")

    monkeypatch.setattr("grader.plan_resolution.analyze_repository_with_llm", forbidden)
    plan, meta = resolve_execution_plan(tmp_path, use_ai=True, confidence_threshold=0.50)
    assert plan.ingest_command
    assert meta["status"] == "DETERMINISTIC_READY"
    assert meta["agent_called"] is False


def test_startup_classifier_treats_missing_config_as_configuration(tmp_path: Path):
    from grader.final_runtime import _classify_startup_failure

    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    result = _classify_startup_failure(
        tmp_path,
        {
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'config'",
            "timed_out": False,
        },
    )
    assert result["code"] == "STUDENT_CONFIGURATION_FAILURE"


def test_materialized_view_aggregation_basis_deterministic(tmp_path: Path):
    from grader.final_compliance import materialized_view_aggregation_basis

    (tmp_path / "mv.py").write_text(
        "def refresh_mv(db):\n    rows = db.orders.aggregate([])\n    return list(rows)\n",
        encoding="utf-8",
    )
    result = materialized_view_aggregation_basis(tmp_path)
    assert result["supported"] is True
    assert result["source"] == "deterministic"


def test_suites_expose_shared_sandbox_lifecycle():
    import inspect
    from grader.sandbox_runtime import run_behavioral_suite
    from grader.final_runtime import run_final_suite

    mid = inspect.signature(run_behavioral_suite).parameters
    fin = inspect.signature(run_final_suite).parameters
    assert "shared_sandbox" in mid
    assert "student_inputs_dir" in mid
    assert "manage_sandbox" in mid
    assert "shared_sandbox" in fin
    assert "manage_sandbox" in fin


def test_unified_evaluator_exists_and_has_modes():
    import evaluate_project
    assert callable(evaluate_project.main)


def test_platform_compat_requirements_only_skip_known_windows_packages(tmp_path: Path):
    from grader.sandbox import _write_compat_requirements

    src = tmp_path / "requirements.txt"
    dst = tmp_path / "compat.txt"
    src.write_text(
        "pymongo==4.17.0\npywin32==311\nnumpy==2.1.0\nwindows-curses==2.4.1\n",
        encoding="utf-8",
    )
    skipped = _write_compat_requirements(src, dst)
    text = dst.read_text(encoding="utf-8")
    assert set(skipped) == {"pywin32", "windows-curses"}
    assert "pymongo==4.17.0" in text
    assert "numpy==2.1.0" in text
    assert "# GRADER platform-only skip: pywin32==311" in text


def test_structured_stdin_renders_without_shell_pipe():
    from grader.models import ExecutionPlan
    from grader.sandbox_runtime import _render_stdin

    plan = ExecutionPlan(
        repo_path="/tmp/project",
        ingest_command="python src/main.py",
        ingest_stdin="2\n{file}\n\n3\n",
    )
    value = _render_stdin(plan, "hidden.csv", "grader_p1", 20)
    assert value == "2\n/grader-tests/hidden.csv\n\n3\n"


def test_spark_network_dependency_is_inconclusive_candidate():
    from grader.sandbox_runtime import _spark_dependency_resolution_blocked

    blocked, evidence = _spark_dependency_resolution_blocked({
        "stderr_tail": "UNRESOLVED DEPENDENCIES\nHost repo1.maven.org not found\nmodule not found: org.mongodb.spark#mongo-spark-connector",
    })
    assert blocked is True
    assert evidence


def test_static_checks_accept_lowercase_readme(tmp_path: Path):
    from grader.static_checks import static_checks

    (tmp_path / "readme.md").write_text("# docs\n", encoding="utf-8")
    result = static_checks(tmp_path)
    assert result["has_readme"] is True
    assert result["_evidence"]["has_readme"] == ["readme.md"]


def test_midterm_readiness_gate_classifies_interactive_discovery(tmp_path: Path):
    from grader.sandbox_runtime import _classify_midterm_start_failure

    result = _classify_midterm_start_failure(
        tmp_path,
        {"stderr_tail": "EOFError: EOF when reading a line", "stdout_tail": "", "timed_out": False},
    )
    assert result["code"] == "GRADER_DISCOVERY_FAILURE"


def test_midterm_readiness_gate_classifies_missing_local_config(tmp_path: Path):
    from grader.sandbox_runtime import _classify_midterm_start_failure

    (tmp_path / "requirements.txt").write_text("pymongo\n", encoding="utf-8")
    result = _classify_midterm_start_failure(
        tmp_path,
        {"stderr_tail": "ModuleNotFoundError: No module named 'config'", "stdout_tail": "", "timed_out": False},
    )
    assert result["code"] == "STUDENT_CONFIGURATION_FAILURE"


def test_recovery_agent_is_not_called_for_deterministic_student_failure():
    from evaluate import _runtime_command_failure_context
    runtime = {
        "status": "STARTUP_BLOCKED",
        "root_cause": "STUDENT_CONFIGURATION_FAILURE",
        "cases": [{"run": {"returncode": 1, "stderr_tail": "boom"}}],
    }
    assert _runtime_command_failure_context(runtime) == ""


def test_recovery_agent_is_called_for_discovery_failure():
    from evaluate import _runtime_command_failure_context
    runtime = {
        "status": "STARTUP_BLOCKED",
        "root_cause": "GRADER_DISCOVERY_FAILURE",
        "cases": [{"name": "batch_pipeline", "command": "python main.py", "run": {"returncode": 1, "stderr_tail": "EOFError"}}],
    }
    assert "EOFError" in _runtime_command_failure_context(runtime)


def test_requirements_utf16_platform_fallback(tmp_path: Path):
    from grader.sandbox import _write_compat_requirements

    src = tmp_path / "requirements.txt"
    dst = tmp_path / "compat.txt"
    src.write_text("pymongo==4.17.0\npywin32==311\n", encoding="utf-16")
    skipped = _write_compat_requirements(src, dst)
    text = dst.read_text(encoding="utf-8")
    assert skipped == ["pywin32"]
    assert "pymongo==4.17.0" in text
    assert "\x00" not in text


def test_lowercase_readme_final_discovery_and_contract(tmp_path: Path):
    from grader.final_discovery import discover_final_plan
    from grader.final_compliance import readme_contract

    (tmp_path / "readme.md").write_text(
        """
Install: pip install -r requirements.txt
Run: uvicorn src.api:app --host 127.0.0.1 --port 8000
FastAPI /health /docs
Queries, Indexes, Explain executionStats
Aggregation reports
Materialized Views
Scheduled Jobs
""",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("MONGO_URI=mongodb://localhost\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n", encoding="utf-8")
    plan = discover_final_plan(tmp_path)
    contract = readme_contract(tmp_path)
    assert plan["api_target"] == "src.api:app"
    assert plan["static"]["has_readme"] is True
    assert plan["static"]["readme_file"] == "readme.md"
    assert contract["readme_file"] == "readme.md"
    assert contract["covered_topics"] == contract["required_topics"]


def test_platform_fallback_skips_tensorflow_intel_but_keeps_tensorflow(tmp_path: Path):
    from grader.sandbox import _write_compat_requirements

    src = tmp_path / "requirements.txt"
    dst = tmp_path / "compat.txt"
    src.write_text(
        "tensorflow==2.17.0\ntensorflow-intel==2.17.0\npymongo==4.17.0\n",
        encoding="utf-8",
    )
    skipped = _write_compat_requirements(src, dst)
    text = dst.read_text(encoding="utf-8")
    assert "tensorflow-intel" in skipped
    assert "tensorflow==2.17.0" in text
    assert "pymongo==4.17.0" in text


def test_runtime_requirements_profile_keeps_declared_bigdata_dependencies_only(tmp_path: Path):
    from grader.sandbox import _write_runtime_requirements

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        "from fastapi import FastAPI\nimport pymongo\nimport pandas\n",
        encoding="utf-8",
    )
    req = tmp_path / "requirements.txt"
    out = tmp_path / "runtime.txt"
    req.write_text(
        "fastapi==0.127.0\npymongo==4.17.0\npandas==2.2.3\n"
        "tensorflow==2.17.0\ndeepface==0.0.93\npywin32==311\n",
        encoding="utf-8",
    )
    meta = _write_runtime_requirements(tmp_path, req, out)
    text = out.read_text(encoding="utf-8")
    assert "fastapi==0.127.0" in text
    assert "pymongo==4.17.0" in text
    assert "pandas==2.2.3" in text
    assert "tensorflow" not in text
    assert "deepface" not in text
    assert "pywin32" not in text
    assert meta["selected_count"] == 3


def test_documented_ingest_command_preserves_required_readme_flags(tmp_path: Path):
    from grader.discovery import _documented_ingest_command

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        """
import argparse
p=argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--action", choices=["run", "route"], default="run")
p.add_argument("--write", action="store_true")
""",
        encoding="utf-8",
    )
    readme = 'python src/main.py --input "data/orders.csv" --action run --write'
    cmd, entry = _documented_ingest_command(tmp_path, readme)
    assert entry == "src/main.py"
    assert cmd == "python src/main.py --input {file} --action run --write"


def test_documented_ingest_command_prefers_module_entrypoint(tmp_path: Path):
    from grader.discovery import _documented_ingest_command

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pipeline_entry.py").write_text(
        'import argparse\np=argparse.ArgumentParser()\np.add_argument("--input", required=True)\n',
        encoding="utf-8",
    )
    readme = 'python -m src.pipeline_entry --input "<CSV_PATH>"'
    cmd, entry = _documented_ingest_command(tmp_path, readme)
    assert entry == "src/pipeline_entry.py"
    assert cmd == "python -m src.pipeline_entry --input {file}"


def test_documented_ingest_rejects_stale_flag_and_uses_valid_positional(tmp_path: Path):
    from grader.discovery import _documented_ingest_command

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        'import argparse\np=argparse.ArgumentParser()\np.add_argument("csv_path")\n',
        encoding="utf-8",
    )
    readme = """
python src/main.py --csv data/orders.csv
python src/main.py data/orders.csv
"""
    cmd, entry = _documented_ingest_command(tmp_path, readme)
    assert entry == "src/main.py"
    assert cmd == "python src/main.py {file}"


def test_timeout_bytes_are_normalized_to_text():
    from grader.sandbox import _as_text
    assert _as_text(b"Spark timeout \xff") == "Spark timeout �"


def test_windows_py_launcher_uses_sandbox_python():
    from grader.sandbox import _normalize_python_launcher
    assert _normalize_python_launcher("py -m src.main --input x.csv") == "python -m src.main --input x.csv"
    assert _normalize_python_launcher("python -m src.main") == "python -m src.main"


def test_pipeline_success_marker_overrides_server_timeout():
    from grader.sandbox_runtime import _pipeline_completed_before_timeout
    assert _pipeline_completed_before_timeout({
        "timed_out": True,
        "stdout_tail": "ALL PHASE 1 & PHASE 2 PIPELINE STAGES COMPLETED SUCCESSFULLY\nINFO: Uvicorn running",
        "stderr_tail": "",
    }) is True
    assert _pipeline_completed_before_timeout({
        "timed_out": True,
        "stdout_tail": "starting pipeline",
        "stderr_tail": "",
    }) is False


def test_discovery_supports_mongodb_database_alias_and_positional_input(tmp_path: Path):
    from grader.discovery import discover_execution_plan

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        'import argparse\np=argparse.ArgumentParser()\np.add_argument("csv_path")\n',
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text(
        "MONGODB_URI=mongodb://localhost:27017\nMONGODB_DATABASE=midterm_data_pipeline\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("pymongo\n", encoding="utf-8")
    plan = discover_execution_plan(tmp_path)
    assert plan.ingest_command == "python src/main.py {file}"
    assert plan.database_name == "midterm_data_pipeline"
    assert plan.database_configurable is True
    assert plan.mongo_uri == "mongodb://localhost:27017"


def test_discovery_appends_no_server_only_when_cli_declares_it(tmp_path: Path):
    from grader.discovery import discover_execution_plan

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        'import argparse\np=argparse.ArgumentParser()\np.add_argument("--input", required=True)\np.add_argument("--no-server", action="store_true")\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("pymongo\n", encoding="utf-8")
    plan = discover_execution_plan(tmp_path)
    assert plan.ingest_command == "python src/main.py --input {file} --no-server"


def test_mongo_env_parser_rejects_getenv_expression_as_literal():
    from grader.discovery import _parse_settings

    result = _parse_settings(
        'MONGO_DATABASE = os.getenv("MONGO_DATABASE", "ecommerce_store")\n'
        'MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")\n'
    )
    assert result["db"] == "ecommerce_store"
    assert result["uri"] == "mongodb://localhost:27017"
    assert "." not in result["db"]


def test_probe_names_from_supports_names_array():
    from grader.final_runtime import _probe_python
    text = _probe_python()
    assert '"names"' in text


def test_mv_initialization_precondition_is_not_student_fail():
    from grader.final_runtime import _mv_requires_initialization
    assert _mv_requires_initialization({
        "status": 500,
        "ok": False,
        "body": {"detail": {"message": "Materialized Views are not initialized. Run --bootstrap first."}},
    }) is True
    assert _mv_requires_initialization({
        "status": 200,
        "ok": True,
        "body": {"status": "success"},
    }) is False


def test_dynamic_query_metadata_can_supply_params_not_declared_in_openapi():
    from grader.final_runtime import _probe_python
    text = _probe_python()
    assert "for pname in sorted(selected)" in text
    assert "params[pname] = sample_value(pname, {})" in text


def test_execution_repair_agent_sanitizes_commands_and_workdir(tmp_path: Path):
    from grader.agent_analyzer import _sanitize_command, _sanitize_working_directory

    (tmp_path / "final_extension").mkdir()
    assert _sanitize_command("python -m src.phase2.materialized_views --bootstrap") == "python -m src.phase2.materialized_views --bootstrap"
    assert _sanitize_command("python x.py && rm -rf /") is None
    assert _sanitize_working_directory(tmp_path, "final_extension") == "final_extension"
    assert _sanitize_working_directory(tmp_path, "../outside") == "."


def test_final_suite_accepts_recovery_commands_parameter():
    import inspect
    from grader.final_runtime import run_final_suite

    params = inspect.signature(run_final_suite).parameters
    assert "recovery_commands" in params


def test_sandbox_run_student_accepts_working_directory():
    import inspect
    from grader.sandbox import DockerSandbox

    params = inspect.signature(DockerSandbox.run_student).parameters
    assert "working_directory" in params


def test_unified_evaluator_invokes_execution_repair_agent():
    import inspect
    import evaluate_project

    source = inspect.getsource(evaluate_project.main)
    assert "analyze_execution_repair_with_llm" in source
    assert "recovery_commands=repair_commands" in source


def test_execution_repair_has_retry_and_model_fallback():
    import inspect
    from grader.agent_analyzer import analyze_execution_repair_with_llm

    source = inspect.getsource(analyze_execution_repair_with_llm)
    assert "GRADER_LLM_FALLBACK_MODELS" in source
    assert "gemini-2.5-pro" in source
    assert "gemini-2.5-flash" in source
    assert "transient_statuses" in source
    assert "attempt_no in range(1, 3)" in source
    assert "fallback_used" in source


def test_command_reference_validation_supports_working_directory(tmp_path: Path):
    from grader.agent_analyzer import _command_references_exist

    (tmp_path / "final_extension" / "final").mkdir(parents=True)
    (tmp_path / "final_extension" / "final" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "final_extension" / "final" / "cli.py").write_text("", encoding="utf-8")

    assert _command_references_exist(
        tmp_path,
        "python -m final.cli refresh-full",
        "final_extension",
    ) is True
    assert _command_references_exist(
        tmp_path,
        "python -m final.cli refresh-full",
        ".",
    ) is False


def test_targeted_context_includes_nearest_nested_readme(tmp_path: Path):
    from grader.agent_analyzer import collect_targeted_files
    from grader.models import ExecutionPlan

    nested = tmp_path / "final_extension" / "src" / "final"
    nested.mkdir(parents=True)
    (tmp_path / "final_extension" / "README.md").write_text(
        "python -m final.cli refresh-full\n",
        encoding="utf-8",
    )
    (nested / "api.py").write_text("print('api')\n", encoding="utf-8")
    plan = ExecutionPlan(repo_path=str(tmp_path), entrypoint="final_extension/src/final/api.py")
    files = collect_targeted_files(tmp_path, plan)
    paths = {x["path"] for x in files}
    assert "final_extension/README.md" in paths


def test_readme_repair_fallback_extracts_exact_commands(tmp_path: Path):
    from grader.agent_analyzer import _grounded_readme_repair_commands

    (tmp_path / "final_extension" / "final").mkdir(parents=True)
    (tmp_path / "final_extension" / "final" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "final_extension" / "final" / "cli.py").write_text("", encoding="utf-8")
    content = """
python -m final.cli indexes
python -m final.cli explain
python -m final.cli refresh-full
"""
    files = [{"path": "final_extension/README.md", "content": content}]
    failure_context = {
        "assertions": [
            {"key": "final.indexes.count", "verdict": "FAIL"},
            {"key": "final.indexes.explain", "verdict": "FAIL"},
            {"key": "final.mv.refresh", "verdict": "INCONCLUSIVE"},
        ]
    }
    cmds = _grounded_readme_repair_commands(tmp_path, files, failure_context, max_commands=3)
    assert [x["command"] for x in cmds] == [
        "python -m final.cli indexes",
        "python -m final.cli explain",
        "python -m final.cli refresh-full",
    ]
    assert all(x["working_directory"] == "final_extension" for x in cmds)


def test_final_probe_retries_jobs_from_available_names_error():
    from grader.final_runtime import _probe_python
    text = _probe_python()
    assert "job_names_from_error" in text
    assert "Available:" in text
