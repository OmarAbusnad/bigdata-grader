import csv
from pathlib import Path

def test_p24_roster_points_to_latest_accepted_exact_source():
    with Path("submission_groups.csv").open(encoding="utf-8-sig",newline="") as f:
        matches=[r for r in csv.DictReader(f) if r["project_id"]=="P24"]
    assert len(matches)==1
    assert matches[0]["repo_full_name"]=="mohsenalfahed2026-sketch/Sagralbrsh"
    assert matches[0]["repo_url"]=="https://github.com/mohsenalfahed2026-sketch/Sagralbrsh"
