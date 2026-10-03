from __future__ import annotations
import csv
import re
from pathlib import Path


def _bump_identifier(value: str, cycle: int, field: str) -> str:
    if cycle == 0 or not value:
        return value
    m = re.search(r'(\d+)\s*$', value)
    if not m:
        return f'{value}-{cycle}'
    n = int(m.group(1)) + cycle * 10_000_000
    prefix = value[:m.start(1)]
    return f'{prefix}{n}'


def ensure_large_clean_probe(base_csv: str | Path, out_dir: str | Path, threshold_mb: float,
                             margin_mb: float = 5.0, max_mb: float = 320.0) -> tuple[Path, int, str]:
    """Return a clean CSV guaranteed to exceed a student's hard-coded router threshold when feasible.

    The bundled clean Spark test is reused when already large enough. Otherwise rows are streamed and
    identifiers are offset per cycle so each duplicated row remains a distinct business entity.
    """
    base = Path(base_csv)
    base_mb = base.stat().st_size / (1024 * 1024)
    if base_mb > threshold_mb:
        # Count data rows without materializing them.
        with base.open(encoding='utf-8-sig', newline='') as f:
            rows = sum(1 for _ in f) - 1
        return base, rows, f'bundled file ({base_mb:.1f} MB) already exceeds threshold {threshold_mb:.1f} MB'

    target_mb = threshold_mb + max(2.0, margin_mb)
    if target_mb > max_mb:
        with base.open(encoding='utf-8-sig', newline='') as f:
            rows = sum(1 for _ in f) - 1
        return base, rows, f'threshold {threshold_mb:.1f} MB exceeds dynamic probe cap {max_mb:.1f} MB'

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'dynamic_spark_probe_{int(threshold_mb)}mb.csv'
    if out.exists() and out.stat().st_size / (1024 * 1024) > threshold_mb:
        with out.open(encoding='utf-8-sig', newline='') as f:
            rows = sum(1 for _ in f) - 1
        return out, rows, f'reused generated probe ({out.stat().st_size/(1024*1024):.1f} MB)'

    target_bytes = int(target_mb * 1024 * 1024)
    total = 0
    cycle = 0
    with base.open(encoding='utf-8-sig', newline='') as src0:
        reader0 = csv.DictReader(src0)
        fieldnames = reader0.fieldnames or []
    with out.open('w', encoding='utf-8-sig', newline='') as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        while dst.tell() < target_bytes:
            with base.open(encoding='utf-8-sig', newline='') as src:
                reader = csv.DictReader(src)
                for row in reader:
                    row = dict(row)
                    if 'order_id' in row:
                        row['order_id'] = _bump_identifier(row['order_id'], cycle, 'order_id')
                    if 'id_order' in row:
                        row['id_order'] = _bump_identifier(row['id_order'], cycle, 'id_order')
                    if 'customer_id' in row:
                        row['customer_id'] = _bump_identifier(row['customer_id'], cycle, 'customer_id')
                    writer.writerow(row)
                    total += 1
                    if total % 5000 == 0:
                        dst.flush()
                        if dst.tell() >= target_bytes:
                            break
            cycle += 1
    size_mb = out.stat().st_size / (1024 * 1024)
    return out, total, f'generated clean probe {size_mb:.1f} MB > threshold {threshold_mb:.1f} MB'
