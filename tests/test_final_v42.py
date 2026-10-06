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
