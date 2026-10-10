"""Static audit of immutable frozen FastAPI submission source.

No student code is executed. AST inspection reports FastAPI imports/instances,
so the grader can distinguish a genuinely absent API from discovery failures.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

SKIP = {".git", ".venv", "venv", "__pycache__", "node_modules"}


def inspect_fastapi(root: Path) -> dict:
    root=root.resolve()
    if not root.is_dir():
        raise ValueError("Student source root missing")
    findings=[]
    scanned=[]
    syntax_errors=[]
    for p in sorted(root.rglob("*.py")):
        if any(part in SKIP for part in p.relative_to(root).parts):
            continue
        if p.stat().st_size>2_000_000:
            raise ValueError("Oversized frozen Python source file")
        content=p.read_text(encoding="utf-8-sig",errors="replace")
        rel=str(p.relative_to(root))
        scanned.append({"file":rel,"sha256":hashlib.sha256(content.encode()).hexdigest()})
        try:
            tree=ast.parse(content)
        except SyntaxError as exc:
            syntax_errors.append({"file":rel,"error":str(exc)})
            continue
        matches=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                if any(alias.name=="fastapi" or alias.name.startswith("fastapi.") for alias in n.names):
                    matches.add("FASTAPI_IMPORT")
            elif isinstance(n,ast.ImportFrom) and n.module and (
                n.module=="fastapi" or n.module.startswith("fastapi.")
            ):
                matches.add("FASTAPI_IMPORT")
            elif isinstance(n,ast.Call):
                if isinstance(n.func,ast.Name) and n.func.id in ("FastAPI","APIRouter"):
                    matches.add("FASTAPI_APP_OR_ROUTER")
                elif isinstance(n.func,ast.Attribute) and n.func.attr in ("FastAPI","APIRouter"):
                    matches.add("FASTAPI_APP_OR_ROUTER")
        if matches:
            findings.append({"path":rel,"indicators":sorted(matches)})
    if syntax_errors:
        status="INCONCLUSIVE_PARSE_ERRORS"
    elif findings:
        status="FASTAPI_SOURCE_EXISTS_REVIEW_GRADER_DISCOVERY"
    elif scanned:
        status="FASTAPI_ABSENT_IN_SUBMITTED_PYTHON_SOURCE"
    else:
        status="NO_PYTHON_SOURCE"
    return {
        "status":status,"source_python_files":len(scanned),"matches":findings,
        "syntax_errors":syntax_errors,"sha256_by_file":scanned,
        "student_code_executed":False,"grade_changed":False,
    }


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--project",required=True)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    proof=inspect_fastapi(a.root)
    proof["project_id"]=a.project
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:proof[k] for k in (
        "project_id","status","source_python_files","student_code_executed"
    )},ensure_ascii=False))


if __name__=="__main__":
    main()
