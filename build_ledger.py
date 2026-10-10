#!/usr/bin/env python3
"""Build the master adjudication ledger from saved evidence (no student code runs).

  python build_ledger.py --base saved_reports --base-run 37874152827 \
      --overlay 38003977105:overlays/spark_p05 --overlay 38015912512:overlays/archives \
      --rulings rulings.json --out ledger_out --expected-projects 68
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from grader.ledger import Ledger, VERDICTS, review_hint


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_outputs(ledger: Ledger, out: Path, expected: int | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    data = ledger.to_dict(expected_projects=expected)
    (out / "ledger.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    entries, summary, queue = [], [], []
    for pid in sorted(ledger.projects):
        proj = ledger.projects[pid]
        row = {"project_id": pid, "students": proj["students"], "frozen_sha": proj["frozen_sha"]}
        for phase in ("midterm", "final"):
            ph = proj["phases"][phase]
            counts = ledger.counts(pid, phase)
            row[f"{phase}_status"] = ph["status"]
            for v in VERDICTS:
                row[f"{phase}_{v}"] = counts[v]
            for key, e in sorted(ph["entries"].items()):
                base = {"project_id": pid, "phase": phase, "key": key, "verdict": e["verdict"],
                        "source": e["origin"].get("type"), "run_id": e["origin"].get("run_id"),
                        "flags": ";".join(e["flags"]), "changed": bool(e["history"])}
                entries.append(base)
                if e["verdict"] != "PASS":
                    queue.append({**base, "expected": e["expected"], "actual": e["actual"],
                                  "note": e["note"], "hint": review_hint(e)})
        summary.append(row)
    ef = ["project_id", "phase", "key", "verdict", "source", "run_id", "flags", "changed"]
    _write_csv(out / "entries.csv", entries, ef)
    _write_csv(out / "review_queue.csv", queue, ef + ["expected", "actual", "note", "hint"])
    sf = ["project_id", "students", "frozen_sha"] + [f"{p}_{x}" for p in ("midterm", "final")
                                                    for x in ["status", *VERDICTS]]
    _write_csv(out / "project_summary.csv", summary, sf)
    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--base-run", type=int, required=True)
    p.add_argument("--overlay", action="append", default=[], help="RUN_ID:DIR, applied in order")
    p.add_argument("--rulings", type=Path)
    p.add_argument("--out", type=Path, default=Path("ledger_out"))
    p.add_argument("--expected-projects", type=int)
    a = p.parse_args()

    ledger = Ledger()
    ledger.load_base(a.base, run_id=a.base_run)
    for spec in a.overlay:
        run, _, folder = spec.partition(":")
        if not run.isdigit() or not folder:
            p.error(f"--overlay must be RUN_ID:DIR, got {spec!r}")
        if not Path(folder).is_dir():
            print(f"WARNING: overlay dir missing, skipped: {folder}", file=sys.stderr)
            continue
        ledger.apply_overlay_dir(Path(folder), run_id=int(run))
    if a.rulings and a.rulings.is_file():
        ledger.apply_rulings(json.loads(a.rulings.read_text(encoding="utf-8")))
    data = write_outputs(ledger, a.out, a.expected_projects)
    inv = data["invariants"]
    print(json.dumps({"projects": len(data["projects"]), "invariants": inv,
                      "conflicts": len(data["conflicts"]), "rejected": len(data["rejected"]),
                      "pass_overrides": len(data["pass_overrides"])}, ensure_ascii=False, indent=2))
    return 0 if inv["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
