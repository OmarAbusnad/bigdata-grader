from __future__ import annotations

import argparse
import csv
import json
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from grader.repository import RepositoryError, clone_repository, current_commit


BASE = Path(__file__).resolve().parent
DEFAULT_SUBMISSIONS = BASE / "submission_groups.csv"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _find_project(rows: list[dict[str, str]], project_id: str) -> dict[str, str]:
    for row in rows:
        if row.get("project_id") == project_id:
            return row
    raise KeyError(f"Unknown project_id: {project_id}")


def _canonical_clone_url(row: dict[str, str]) -> str:
    full = (row.get("repo_full_name") or "").strip().strip("/")
    if full and "/" in full:
        return f"https://github.com/{full}.git"

    raw = (row.get("repo_url") or "").strip()
    if not raw:
        raise ValueError("repo_url is empty")

    # Strip browser-only GitHub paths such as /tree/main/subdir.
    parsed = urlparse(raw)
    if (parsed.hostname or "").lower() == "github.com":
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
            return f"https://github.com/{parts[0]}/{repo}.git"
    return raw


def _workspace_subdir(row: dict[str, str]) -> str:
    """Preserve an explicitly submitted GitHub /tree/main/<subdir> path."""
    raw = (row.get("repo_url") or "").strip()
    m = re.search(r"github\.com/[^/]+/[^/]+/tree/(?:main|master)/(.+?)/?$", raw, re.I)
    return m.group(1).strip("/") if m else ""


def _write_metadata(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_tree_to_tar(tf: tarfile.TarFile, repo: Path) -> None:
    for item in sorted(repo.rglob("*")):
        rel = item.relative_to(repo)
        if ".git" in rel.parts:
            continue
        tf.add(item, arcname=Path("repo") / rel, recursive=False)


def freeze_one(submissions: Path, project_id: str, output_dir: Path, timeout: int) -> int:
    rows = _rows(submissions)
    row = _find_project(rows, project_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = output_dir / f"{project_id}.metadata.json"
    archive_path = output_dir / f"{project_id}.repo.tar.gz"
    workspace = BASE / "workspaces" / project_id / "repo"
    frozen_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "project_id": project_id,
        "students": row.get("students", ""),
        "student_nos": row.get("student_nos", ""),
        "repo_url": row.get("repo_url", ""),
        "repo_full_name": row.get("repo_full_name", ""),
        "clone_url": "",
        "commit_sha": "",
        "frozen_at_utc": frozen_at,
        "freeze_status": "ERROR",
        "freeze_error": "",
        "workspace_subdir": _workspace_subdir(row),
        "snapshot_name": archive_path.name,
    }

    try:
        clone_url = _canonical_clone_url(row)
        metadata["clone_url"] = clone_url
        clone_repository(clone_url, workspace, ref=(row.get("ref") or None), timeout=timeout)
        sha = current_commit(workspace) or ""
        if not sha:
            raise RepositoryError("Unable to resolve HEAD commit")

        subdir = metadata["workspace_subdir"]
        if subdir and not (workspace / subdir).exists():
            metadata["freeze_error"] = (
                f"Submitted workspace subdirectory does not exist at frozen commit: {subdir}"
            )
            _write_metadata(metadata_path, metadata)
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
            return 0

        with tarfile.open(archive_path, "w:gz", compresslevel=6) as tf:
            _add_tree_to_tar(tf, workspace)

        metadata["commit_sha"] = sha
        metadata["freeze_status"] = "READY"
        metadata["snapshot_bytes"] = archive_path.stat().st_size
    except Exception as exc:
        metadata["freeze_error"] = f"{type(exc).__name__}: {exc}"
        if archive_path.exists():
            archive_path.unlink()

    _write_metadata(metadata_path, metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    # A repository-level failure is recorded in metadata so the matrix can
    # continue freezing the rest of the class.
    return 0


def build_manifest(submissions: Path, artifacts_dir: Path, output: Path) -> int:
    rows = _rows(submissions)
    extra_fields = [
        "commit_sha",
        "frozen_at_utc",
        "freeze_status",
        "freeze_error",
        "workspace_subdir",
        "snapshot_name",
    ]
    base_fields = list(rows[0].keys()) if rows else ["project_id", "repo_url"]
    fields = base_fields + [f for f in extra_fields if f not in base_fields]

    ready = failed = 0
    for row in rows:
        pid = row.get("project_id", "")
        meta_path = artifacts_dir / f"{pid}.metadata.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                meta = {"freeze_status": "ERROR", "freeze_error": f"Invalid metadata: {exc}"}
        else:
            meta = {"freeze_status": "ERROR", "freeze_error": "Snapshot metadata artifact is missing"}

        for field in extra_fields:
            row[field] = str(meta.get(field, "") or "")
        if row["freeze_status"] == "READY":
            ready += 1
        else:
            failed += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_projects": len(rows),
        "ready_projects": ready,
        "failed_projects": failed,
        "manifest": output.name,
    }
    summary_path = output.with_name("freeze_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Freeze student repositories into immutable grading snapshots")
    p.add_argument("--submissions", default=str(DEFAULT_SUBMISSIONS))
    p.add_argument("--project", help="Freeze one project ID")
    p.add_argument("--output-dir", default="frozen")
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--build-manifest", action="store_true")
    p.add_argument("--artifacts-dir", default="frozen_downloads")
    p.add_argument("--output", default="frozen_submissions.csv")
    args = p.parse_args()

    submissions = Path(args.submissions).resolve()
    if args.build_manifest:
        return build_manifest(
            submissions,
            Path(args.artifacts_dir).resolve(),
            Path(args.output).resolve(),
        )
    if not args.project:
        p.error("--project is required unless --build-manifest is used")
    return freeze_one(
        submissions,
        args.project,
        Path(args.output_dir).resolve(),
        args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
