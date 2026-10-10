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
    audit_rows = []
    for src in data["sources"]:
        if src.get("type") == "overlay_dir":
            audit_rows.append({
                "run_id": src.get("run_id"), "type": src["type"],
                "files_seen": src.get("files_seen", 0),
                "recognized": src.get("recognized_files", 0),
                "midterm_reports": src.get("midterm_reports", 0),
                "spark_proofs": src.get("spark_proofs", 0),
                "final_proofs": src.get("final_proofs", 0),
                "evidence_overlays": src.get("evidence_overlays", 0),
                "metadata_files": src.get("metadata_files", 0),
                "ignored_files": src.get("ignored_files", 0),
                "changes": src.get("changes", 0),
                "files": "; ".join(f"{x['path']} [{x['kind']}: {x['changes']}]"
                                    for x in src.get("files", [])),
            })
    af = ["run_id", "type", "files_seen", "recognized", "midterm_reports",
          "spark_proofs", "final_proofs", "evidence_overlays", "metadata_files",
          "ignored_files", "changes", "files"]
    _write_csv(out / "source_audit.csv", audit_rows, af)
    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--base-run", type=int, required=True)
    p.add_argument("--overlay", action="append", default=[], help="RUN_ID:DIR, applied in order")
    p.add_argument("--rulings", type=Path)
    p.add_argument("--out", type=Path, default=Path("ledger_out"))
    p.add_argument("--expected-projects", type=int)
    p.add_argument("--frozen-http-preconditions", action="store_true",
                   help="Reclassify frozen Final timeout-without-HTTP FAIL as INCONCLUSIVE (never PASS)")
    a = p.parse_args()

    ledger = Ledger()
    ledger.load_base(a.base, run_id=a.base_run)
    for spec in a.overlay:
        run, _, folder = spec.partition(":")
        if not run.isdigit() or not folder:
            p.error(f"--overlay must be RUN_ID:DIR, got {spec!r}")
        if not Path(folder).is_dir():
            p.error(f"required overlay run {run} missing: {folder}")
        stats = ledger.apply_overlay_dir(Path(folder), run_id=int(run))
        print(json.dumps({"overlay_run": int(run), "files_seen": stats["files_seen"],
                          "grading_files": stats["recognized_files"] - stats["metadata_files"],
                          "metadata_files": stats["metadata_files"], "ignored_files": stats["ignored_files"],
                          "changes_applied": stats["changes"], "files": stats["files"]},
                         ensure_ascii=False), flush=True)
    if a.frozen_http_preconditions:
        stats = ledger.apply_frozen_transport_preconditions(base_run_id=a.base_run)
        print(json.dumps({"frozen_http_timeouts": stats}, ensure_ascii=False), flush=True)
    if a.rulings and not a.rulings.is_file():
        p.error(f"requested rulings file missing: {a.rulings}")
    if a.rulings and a.rulings.is_file():
        ledger.apply_rulings(json.loads(a.rulings.read_text(encoding="utf-8")))
    data = write_outputs(ledger, a.out, a.expected_projects)
    inv = data["invariants"]
    summary = {v: sum(1 for proj in data["projects"].values()
                      for ph in proj["phases"].values()
                      for entry in ph["entries"].values() if entry["verdict"] == v)
               for v in VERDICTS}
    print(json.dumps({"projects": len(data["projects"]), "invariants": inv,
                      "verdict_totals": summary,
                      "overlay_runs": [
                          {"run_id": src["run_id"], "recognized": src.get("recognized_files"),
                           "metadata": src.get("metadata_files"),
                           "ignored": src.get("ignored_files"), "changes_applied": src["changes"]}
                          for src in data["sources"] if src["type"] == "overlay_dir"
                      ],
                      "timeout_preconditions": [
                          {"run_id": src["run_id"], "changes": src["changes"],
                           "cases": src.get("cases", [])}
                          for src in data["sources"] if src["type"] == "frozen_http_timeout_precondition"
                      ],
                      "conflicts": len(data["conflicts"]), "rejected": len(data["rejected"]),
                      "pass_overrides": len(data["pass_overrides"])}, ensure_ascii=False, indent=2))
    return 0 if inv["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
