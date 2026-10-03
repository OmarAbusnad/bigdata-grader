import unittest
from pathlib import Path
from grader.static_checks import static_checks

ROOT = Path(__file__).resolve().parents[1]

class StaticChecksRegressionTests(unittest.TestCase):
    def test_verified_fixtures_show_capabilities(self):
        for name in ('aiman', 'khaled', 'hashem'):
            with self.subTest(name=name):
                result = static_checks(ROOT / 'fixtures' / name)
                for key in (
                    'has_readme', 'has_requirements', 'has_batch_loader', 'has_spark_loader',
                    'mentions_orders_raw', 'mentions_orders_validated', 'mentions_orders_quarantine',
                    'uses_upsert', 'uses_unique_index', 'has_tests'
                ):
                    self.assertTrue(result[key], f'{name}: expected {key}=True; got {result}')

if __name__ == '__main__':
    unittest.main()
