from grader.discovery import discover_execution_plan


def make(tmp_path, readme, files):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pymongo\n", encoding="utf-8")


def test_documented_command_without_input_arg_is_kept_for_fixed_csv_pipelines(tmp_path):
    make(tmp_path, "## Run\n```\npython -m pipeline.run_pipeline\n```\n", {
        "pipeline/__init__.py": "",
        "pipeline/run_pipeline.py": "import csv\nDATA='data/orders.csv'\nwith open(DATA) as f:\n    csv.DictReader(f)\n",
    })
    plan = discover_execution_plan(tmp_path)
    assert plan.ingest_command == "python -m pipeline.run_pipeline"
    assert "{file}" not in plan.ingest_command
    assert plan.confidence >= 0.8, plan.confidence


def test_command_with_input_argument_still_wins(tmp_path):
    make(tmp_path, "```\npython -m pipeline.run_pipeline\npython src/main.py --input data/x.csv\n```\n", {
        "pipeline/__init__.py": "",
        "pipeline/run_pipeline.py": "import csv\nopen('data/orders.csv')\n",
        "src/main.py": "import argparse,csv\np=argparse.ArgumentParser();p.add_argument('--input')\n",
    })
    plan = discover_execution_plan(tmp_path)
    assert "{file}" in plan.ingest_command and "--input" in plan.ingest_command


def test_non_pipeline_modules_are_not_taken(tmp_path):
    make(tmp_path, "```\npython -m pipeline.aggregation_reports\n```\n", {
        "pipeline/__init__.py": "",
        "pipeline/aggregation_reports.py": "import csv\nopen('x.csv')\n",
    })
    plan = discover_execution_plan(tmp_path)
    assert plan.ingest_command is None


def test_documented_audit_script_does_not_displace_heuristic_ingest(tmp_path):
    make(tmp_path, "```\npython scripts/audit_all.py\n```\n", {
        "scripts/audit_all.py": "import csv\nopen('data/x.csv')\n",
        "src/main.py": "import argparse\np=argparse.ArgumentParser();p.add_argument('--input')\n",
    })
    plan = discover_execution_plan(tmp_path)
    assert "audit_all" not in (plan.ingest_command or "")
