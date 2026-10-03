from __future__ import annotations
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--submissions', default='submission_groups.csv')
    p.add_argument('--runtime', action='store_true')
    p.add_argument('--plan-b', action='store_true')
    p.add_argument('--network-profile', choices=['isolated','compat'], default='isolated')
    p.add_argument('--continue-on-error', action='store_true')
    p.add_argument('--allow-low-confidence', action='store_true')
    args = p.parse_args()
    base = Path(__file__).resolve().parent
    rows = list(csv.DictReader((base / args.submissions).open(encoding='utf-8-sig', newline='')))
    summary=[]
    for row in rows:
        pid=row['project_id']
        cmd=[sys.executable, str(base/'evaluate.py'), '--project', pid, '--submissions', args.submissions, '--network-profile', args.network_profile]
        if args.runtime: cmd.append('--runtime')
        if args.plan_b: cmd.append('--plan-b')
        if args.allow_low_confidence: cmd.append('--allow-low-confidence')
        print(f"\n=== {pid} ===")
        proc=subprocess.run(cmd, cwd=base, text=True, capture_output=True)
        print(proc.stdout)
        if proc.stderr: print(proc.stderr, file=sys.stderr)
        summary.append({'project_id':pid,'returncode':proc.returncode})
        if proc.returncode and not args.continue_on_error:
            break
    out=base/'reports'/'batch_summary.json'; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"Summary: {out}")

if __name__=='__main__': main()
