import unittest
import tempfile
from pathlib import Path
from grader.discovery import discover_execution_plan

ROOT = Path(__file__).resolve().parents[1]

class DiscoveryTests(unittest.TestCase):
    def test_aiman(self):
        p = discover_execution_plan(ROOT / "fixtures" / "aiman")
        self.assertIn("--input", p.ingest_command)
        self.assertIn("--db-name", p.ingest_command)
        self.assertEqual(p.database_name, "midterm_ecommerce")
        self.assertEqual(p.collections["raw"], "orders_raw")
        self.assertIsNotNone(p.reset_command)

    def test_khaled(self):
        p = discover_execution_plan(ROOT / "fixtures" / "khaled")
        self.assertEqual(p.database_name, "midterm_data_pipeline")
        self.assertIn("--input", p.ingest_command)
        self.assertTrue(any("Windows" in w for w in p.warnings))

    def test_hashem(self):
        p = discover_execution_plan(ROOT / "fixtures" / "hashem")
        self.assertEqual(p.database_name, "midterm_pipeline_db")
        self.assertIn("--threshold-mb", p.ingest_command)
        self.assertTrue(p.threshold_configurable)
        self.assertEqual(p.spark_master, "local[*]")

    def test_cli_alias_file_path(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\np.add_argument('--file-path')\n"
                "if __name__ == '__main__': p.parse_args()\n",
                encoding="utf-8",
            )
            p = discover_execution_plan(repo)
            self.assertIn("--file-path {file}", p.ingest_command)

    def test_required_run_subcommand(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n"
                "s=p.add_subparsers(dest='cmd', required=True)\n"
                "r=s.add_parser('run')\nr.add_argument('--input')\n"
                "if __name__ == '__main__': p.parse_args()\n",
                encoding="utf-8",
            )
            p = discover_execution_plan(repo)
            self.assertIn(" run --input {file}", p.ingest_command)

    def test_short_file_alias_prefers_declared_f(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "src").mkdir()
            (repo / "src" / "main.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n"
                "p.add_argument('-f', '--file')\n"
                "if __name__ == '__main__': p.parse_args()\n",
                encoding="utf-8",
            )
            p = discover_execution_plan(repo)
            self.assertIn("--file {file}", p.ingest_command)

    def test_documented_windows_script_paths_are_executable_on_linux(self):
        import shlex
        import subprocess
        import sys

        for documented_path, expected_path in (
            (r"src\main.py", "src/main.py"),
            (r".\src\main.py", "./src/main.py"),
        ):
            with self.subTest(documented_path=documented_path):
                with tempfile.TemporaryDirectory() as td:
                    repo = Path(td)
                    (repo / "src").mkdir()
                    (repo / "src" / "main.py").write_text(
                        "import argparse\np=argparse.ArgumentParser()\n"
                        "p.add_argument('--input')\np.parse_args()\n",
                        encoding="utf-8",
                    )
                    (repo / "README.md").write_text(
                        f"python {documented_path} --input data/orders.csv\n",
                        encoding="utf-8",
                    )
                    plan = discover_execution_plan(repo)
                    self.assertIsNotNone(plan.ingest_command)
                    self.assertNotIn("\\", plan.ingest_command)
                    self.assertIn(expected_path, plan.ingest_command)
                    command = plan.ingest_command.replace("{file}", "dummy.csv")
                    result = subprocess.run(
                        [sys.executable, *shlex.split(command)[1:]],
                        cwd=repo, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_documented_windows_py_launcher_uses_linux_python(self):
        for documented_path in (r"src\main.py", r".\src\main.py"):
            with self.subTest(documented_path=documented_path):
                with tempfile.TemporaryDirectory() as td:
                    repo = Path(td)
                    (repo / "src").mkdir()
                    (repo / "src" / "main.py").write_text(
                        "import argparse\np=argparse.ArgumentParser()\n"
                        "p.add_argument('--input')\np.parse_args()\n",
                        encoding="utf-8",
                    )
                    (repo / "README.md").write_text(
                        f"py {documented_path} --input data/orders.csv\n",
                        encoding="utf-8",
                    )
                    plan = discover_execution_plan(repo)
                    self.assertTrue(plan.ingest_command.startswith("python "), plan.ingest_command)
                    self.assertNotIn("\\", plan.ingest_command)
                    self.assertIn("src/main.py", plan.ingest_command)
                    self.assertIn("--input {file}", plan.ingest_command)

    def test_root_wrapper_resolves_src_main(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "src").mkdir()
            (repo / "main.py").write_text(
                "from src.main import main\nif __name__ == '__main__': main()\n",
                encoding="utf-8",
            )
            (repo / "src" / "main.py").write_text(
                "import argparse\ndef main():\n p=argparse.ArgumentParser(); p.add_argument('--input'); p.parse_args()\n"
                "if __name__ == '__main__': main()\n",
                encoding="utf-8",
            )
            p = discover_execution_plan(repo)
            self.assertEqual(p.entrypoint, "src/main.py")
            self.assertIn("--input {file}", p.ingest_command)

if __name__ == "__main__":
    unittest.main()
