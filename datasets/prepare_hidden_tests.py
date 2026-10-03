from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLED = ROOT / 'midterm_hidden_tests_v2.zip'
GEN = ROOT / 'generate_hidden_tests.py'


def write_expected(out: Path):
    key = json.loads((out / 'teacher_key.json').read_text(encoding='utf-8'))
    expected = {
        'threshold_mb': key.get('recommended_discussion_threshold_mb', 20),
        'business_key': 'order_id',
        'test_01': key['test_01'],
        'test_02': key['test_02'],
        'test_03': key['test_03'],
        'test_04': key['test_04'],
    }
    (ROOT / 'expected.json').write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(out: Path, regenerate: bool = False, seed: int = 20260818):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    if not regenerate and BUNDLED.exists():
        with zipfile.ZipFile(BUNDLED) as z:
            z.extractall(out)
    else:
        subprocess.run([sys.executable, str(GEN), '--out-dir', str(out), '--seed', str(seed)], check=True)
    write_expected(out)
    return out


def ensure_prepared() -> Path:
    out = ROOT / 'hidden'
    needed = [out / 'teacher_key.json', out / 'teacher_manifest.csv', out / 'test_01_small_batch_pipeline.csv']
    if not all(p.exists() for p in needed):
        prepare(out)
    if not (ROOT / 'expected.json').exists():
        write_expected(out)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', type=int, default=20260818)
    p.add_argument('--out', default=str(ROOT / 'hidden'))
    p.add_argument('--regenerate', action='store_true', help='Generate a fresh hidden pack instead of extracting the bundled v2 pack')
    args = p.parse_args()
    out = prepare(Path(args.out), regenerate=args.regenerate, seed=args.seed)
    print('Hidden datasets prepared:', out)
    print('Expected file:', ROOT / 'expected.json')

if __name__ == '__main__':
    main()
