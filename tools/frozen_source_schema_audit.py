#!/usr/bin/env python3
"""Read-only provenance-guarded static source audit; NEVER execute student code."""
import argparse, hashlib, io, json, pathlib, re, tarfile, zipfile
PROJECTS = ("P16", "P41", "P44", "P47", "P50", "P52")
SCHEMA = re.compile(r"\\$jsonSchema|validationAction|validationLevel|collMod|schema_validation|create_collection|validator\\s*=", re.I)
AUDIT = re.compile(r"audit_trail|audit_log|audit_history|correction_log|original_value|corrected_value|correction_reason|audit_entries|audit_record|audit_events", re.I)
MAX_TEXT_BYTES = 150_000
MAX_NESTED_ZIP = 80_000_000
MAX_HITS = 50

def assertions(report):
    entries = (report.get("runtime") or {}).get("assertions") or {}
    if isinstance(entries, dict):
        return entries
    if isinstance(entries, list):
        return {a["key"]: a for a in entries if isinstance(a, dict) and isinstance(a.get("key"), str)}
    return {}

def scan_bytes(path, data, found):
    if len(data) > MAX_TEXT_BYTES or not path.lower().endswith((".py", ".md", ".txt", ".toml", ".json", ".yml", ".yaml")):
        return
    if any(x in path.lower() for x in ("/.git/", "/__pycache__/", "/datasets/hidden", "/.env", "/venv", "/site-packages/", "/node_modules/", "/dist/", "/build/")):
        return
    if path.lower().endswith("schema_validation.py") and len(found["schema"]) < MAX_HITS:
        found["schema"].append({"path": path[:240], "line": 1, "indicator": "schema_validation.py:filename_only"})
    text = data.decode("utf-8-sig", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        for kind, regex in (("schema", SCHEMA), ("audit", AUDIT)):
            if regex.search(line) and len(found[kind]) < MAX_HITS:
                found[kind].append({"path": path[:240], "line": i, "indicator": regex.search(line).group(0)[:60]})

def audit(project, root, out):
    folder = root / project
    report = {"project_id": project, "mode": "FROZEN_SOURCE_STATIC_ONLY",
              "academic_grade_changed": False, "student_code_executed": False,
              "historical_pass_overwritten": False, "schema_runtime_verified": False,
              "audit_runtime_verified": False,
              "original_freeze_run": 37390623044, "original_grading_run": 37874152827,
              "original_freeze_url": "https://github.com/omrbosnd/bigdata-grader/actions/runs/37390623044",
              "original_grade_url": "https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827",
              "issue_schema": "https://github.com/omrbosnd/bigdata-grader/issues/35",
              "issue_audit": "https://github.com/omrbosnd/bigdata-grader/issues/36"}
    out_file = out / project / "forensics" / "FROZEN_STATIC_SCHEMA_AUDIT_20261014.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        meta_path = folder / "frozen" / (project + ".metadata.json")
        tar_path = folder / "frozen" / (project + ".repo.tar.gz")
        original_path = folder / "original" / "reports" / project / "result.json"
        for path in (meta_path, tar_path, original_path):
            if not path.exists():
                raise ValueError("missing_artifact_component:" + str(path))
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        assessed = json.loads(original_path.read_text(encoding="utf-8-sig"))
        source_sha = meta.get("commit_sha")
        if (meta.get("project_id") != project or assessed.get("project_id") != project or
            meta.get("freeze_status") != "READY" or
            not source_sha or assessed.get("commit_sha") != source_sha):
            raise ValueError("frozen_source_vs_assessed_report_sha_mismatch")
        if tar_path.stat().st_size != int(meta.get("snapshot_bytes") or -1):
            raise ValueError("frozen_source_archive_byte_length_mismatch")
        report["exact_student_sha"] = source_sha
        report["frozen_archive_sha256"] = hashlib.sha256(tar_path.read_bytes()).hexdigest()
        report["source_guard"] = "VERIFIED_EXACT_SAME_SHA"
        report["original_relevant_assertions"] = {}
        for key in ("batch.schema_validator_runtime", "batch.audit_trail"):
            a = assertions(assessed).get(key)
            report["original_relevant_assertions"][key] = a.get("verdict", "NOT_RECORDED") if isinstance(a, dict) else "NOT_RECORDED"
        found = {"schema": [], "audit": []}
        files_examined, nested_archives, archive_members = 0, 0, []
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                name = member.name.lstrip("./")
                if name.endswith((".py", ".md", ".txt", ".yml", ".yaml", ".json")) and member.size <= MAX_TEXT_BYTES:
                    source = tar.extractfile(member)
                    if source:
                        scan_bytes(name, source.read(MAX_TEXT_BYTES+1), found)
                        files_examined += 1
                elif name.lower().endswith(".zip"):
                    archive_members.append(name[:240])
                    if member.size > MAX_NESTED_ZIP:
                        continue
                    nested_archives += 1
                    source = tar.extractfile(member)
                    if not source:
                        continue
                    try:
                        with zipfile.ZipFile(io.BytesIO(source.read(MAX_NESTED_ZIP+1))) as z:
                            for nested in z.infolist()[:20000]:
                                if nested.is_dir() or nested.file_size > MAX_TEXT_BYTES or nested.flag_bits & 1:
                                    continue
                                nested_path = name + "::" + nested.filename
                                if not nested_path.lower().endswith((".py", ".md", ".txt", ".yml", ".yaml", ".json")):
                                    continue
                                scan_bytes(nested_path, z.read(nested, pwd=None), found)
                                files_examined += 1
                    except (zipfile.BadZipFile, RuntimeError, ValueError):
                        archive_members.append("unreadable_nested_zip:" + name[:200])
        report["source_scan"] = {
            "safe_text_files_examined": files_examined, "nested_archives_examined": nested_archives,
            "nested_zip_evidence": archive_members[:20],
            "schema_indicators": found["schema"], "audit_indicators": found["audit"]}
        report["schema_decision"] = "SOURCE_INDICATORS_FOUND_RUNTIME_UNVERIFIED" if found["schema"] else "NO_STATIC_INDICATORS_RUNTIME_UNVERIFIED"
        report["audit_decision"] = "SOURCE_INDICATORS_FOUND_RUNTIME_UNVERIFIED" if found["audit"] else "NO_STATIC_INDICATORS_RUNTIME_UNVERIFIED"
        report["root_cause_owner"] = "HUMAN_REVIEW_REQUIRED"
        report["next_step"] = "Use exact frozen SHA and recorded source contract to define isolated validator accept/reject and redacted per-sample audit probes; do not infer student FAIL/PASS from keyword markers."
    except Exception as exc:
        report["source_guard"] = "BLOCKED_UNVERIFIED"
        report["block_reason"] = type(exc).__name__ + ":" + str(exc)[:250]
        report["root_cause_owner"] = "PRECONDITION_NOT_SATISFIED"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return {"project": project, "status": report["source_guard"],
            "schema_markers": len(report.get("source_scan", {}).get("schema_indicators", [])),
            "audit_markers": len(report.get("source_scan", {}).get("audit_indicators", [])),
            "path": str(out_file)}

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--projects", nargs="+", choices=PROJECTS, default=list(PROJECTS))
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args=parser.parse_args()
    print(json.dumps([audit(p, args.root, args.out) for p in args.projects], ensure_ascii=False, indent=2))
