from __future__ import annotations
import csv
import subprocess
from pathlib import Path
from grader.repository import clone_repository, current_commit

base=Path(__file__).resolve().parent
src=base/'submission_groups.csv'
out=base/'frozen_submissions.csv'
rows=list(csv.DictReader(src.open(encoding='utf-8-sig', newline='')))
fields=list(rows[0].keys()) if rows else ['project_id','repo_url']
if 'commit_sha' not in fields: fields.append('commit_sha')
for r in rows:
    repo=base/'workspaces'/r['project_id']/'repo'
    clone_repository(r['repo_url'], repo, ref=r.get('ref') or None)
    r['commit_sha']=current_commit(repo) or ''
with out.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
print(out)
