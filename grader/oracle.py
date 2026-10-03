from __future__ import annotations
import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASET_ALIASES = {
    'test_01': 'TEST_01_BATCH_PIPELINE',
    'test_02': 'TEST_02_LARGE_SPARK',
    'test_03': 'TEST_03_UPSERT_IDEMPOTENCY',
    'test_04': 'TEST_04_INCREMENTAL_PLAN_B',
}

@dataclass
class OracleCase:
    dataset: str
    csv_row_number: int
    input_order_id: str
    expected_order_id: str
    expected_class: str
    expected_action: str
    error_type: str
    teacher_note: str
    expected_clean_record: dict[str, Any] | None

class HiddenOracle:
    def __init__(self, key_path: str | Path, manifest_path: str | Path):
        self.key_path = Path(key_path)
        self.manifest_path = Path(manifest_path)
        self.key = json.loads(self.key_path.read_text(encoding='utf-8'))

    @property
    def threshold_mb(self) -> float:
        return float(self.key.get('recommended_discussion_threshold_mb', 20))

    def test(self, name: str) -> dict[str, Any]:
        return dict(self.key[name])

    def _iter_cases(self, dataset_name: str):
        with self.manifest_path.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('dataset') != dataset_name:
                    continue
                payload = None
                if row.get('expected_clean_record_json'):
                    try:
                        payload = json.loads(row['expected_clean_record_json'])
                    except Exception:
                        payload = None
                yield OracleCase(
                    dataset=row.get('dataset', ''),
                    csv_row_number=int(row.get('csv_row_number') or 0),
                    input_order_id=row.get('input_order_id', ''),
                    expected_order_id=row.get('expected_order_id', ''),
                    expected_class=row.get('expected_class', ''),
                    expected_action=row.get('expected_action', ''),
                    error_type=row.get('error_type', ''),
                    teacher_note=row.get('teacher_note', ''),
                    expected_clean_record=payload,
                )

    def cases(self, test_name: str) -> list[OracleCase]:
        dataset = DATASET_ALIASES.get(test_name, test_name)
        return list(self._iter_cases(dataset))

    def sample(self, test_name: str, *, actions: list[str] | None = None,
               classes: list[str] | None = None, n: int = 12, seed: int = 20260818) -> list[OracleCase]:
        rows = self.cases(test_name)
        if actions:
            rows = [r for r in rows if r.expected_action in actions]
        if classes:
            rows = [r for r in rows if r.expected_class in classes]
        if len(rows) <= n:
            return rows
        rng = random.Random(seed + sum(ord(c) for c in test_name))
        return rng.sample(rows, n)
