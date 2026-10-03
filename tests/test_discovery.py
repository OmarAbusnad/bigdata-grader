import unittest
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

if __name__ == "__main__":
    unittest.main()
