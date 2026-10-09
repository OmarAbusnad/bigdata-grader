from grader.discovery import (
    discover_execution_plan,
    _requires_real_mongo_backend,
)


def fixture(tmp_path, default="memory", docs=True):
    (tmp_path / "src").mkdir()
    (tmp_path / "requirements.txt").write_text("pymongo>=4.6",encoding="utf-8")
    (tmp_path / "src"/"main.py").write_text(f"""
import argparse
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--threshold-mb",type=float,default=200.0)
    p.add_argument("--mongo-database",default="midterm_orders")
    p.add_argument("--backend",choices=("mongo","memory"),default="{default}")
    a=p.parse_args()
if __name__ == "__main__":
    main()
""",encoding="utf-8")
    text = "To run: PYTHONPATH=src python src/main.py --input file.csv"
    if docs: text += " --backend mongo --mongo-database midterm_orders"
    (tmp_path/"README.md").write_text(text,encoding="utf-8")
    return tmp_path


def test_documented_mongo_overrides_in_memory_demo_only(tmp_path):
    repo=fixture(tmp_path)
    plan=discover_execution_plan(repo)
    assert " --backend mongo" in plan.ingest_command
    assert "--mongo-database {db_name}" in plan.ingest_command
    assert plan.database_configurable is True


def test_no_silent_override_without_explicit_student_docs(tmp_path):
    repo=fixture(tmp_path,docs=False)
    plan=discover_execution_plan(repo)
    assert " --backend mongo" not in plan.ingest_command


def test_do_not_override_student_default_mongo(tmp_path):
    repo=fixture(tmp_path,default="mongo")
    readme=(repo/"README.md").read_text()
    assert _requires_real_mongo_backend(repo,"src/main.py",readme) is False
