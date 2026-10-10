"""Safely expose frozen archive-only submissions to the original grader.

Never executes archive content during extraction. Rejects traversal, links,
unexpected special files, oversized payloads or ambiguous project roots.
The original frozen tar/ZIP/RAR is left unchanged. The extracted tree is
a separate evaluation workspace, never committed to student repositories.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ALLOWED = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml",
           ".ini", ".cfg", ".env", ".sh", ".ps1", ".csv", ".xml",
           ".sql", ".properties", ".gitignore", ".dockerignore"}
BLOCKED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache",
                ".mypy_cache", "node_modules", ".idea", ".vscode"}
MAX_MEMBERS = 2500
MAX_MEMBER_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 120 * 1024 * 1024


class ArchiveUnsafe(ValueError):
    pass


def _safe_member(raw: str, size: int, *, is_dir=False) -> Path | None:
    name = raw.replace("\\", "/")
    pure = PurePosixPath(name)
    if (name.startswith("/") or "\x00" in name or ":" in pure.parts[0]
            or ".." in pure.parts or "." in pure.parts or pure.is_absolute()):
        raise ArchiveUnsafe(f"Unsafe path inside frozen archive: {raw!r}")
    if any(p.lower() in BLOCKED_DIRS for p in pure.parts):
        return None
    if is_dir:
        return None
    if size < 0 or size > MAX_MEMBER_BYTES:
        # Skip huge test data only if it is CSV; never silently truncate code.
        if pure.suffix.lower() == ".csv":
            return None
        raise ArchiveUnsafe(f"Member exceeds safety limits: {raw!r}")
    if pure.suffix.lower() not in ALLOWED and pure.name.lower() not in {
        "dockerfile", "makefile", ".env.example", ".gitignore",
    }:
        return None
    return Path(*pure.parts)


def _check_total(entries: list[tuple[str, int, bool]]):
    if len(entries) > MAX_MEMBERS:
        raise ArchiveUnsafe("Too many archive entries")
    total = sum(size for _, size, _ in entries if size > 0)
    # Large screenshots/VCS history can exist: only selected members count.
    if total > MAX_TOTAL_BYTES:
        raise ArchiveUnsafe("Selected archive contents exceed safety budget")


def _extract_zip(path: Path, destination: Path) -> dict:
    selections = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            unix_mode = info.external_attr >> 16
            if stat.S_ISLNK(unix_mode):
                raise ArchiveUnsafe(f"Symbolic links not permitted: {info.filename}")
            rel = _safe_member(info.filename, info.file_size, is_dir=info.is_dir())
            if rel:
                selections.append((info, rel))
        _check_total([(i.filename, i.file_size, False) for i, _ in selections])
        for info, rel in selections:
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    return {"container": "zip", "extracted_files": len(selections)}


def _extract_rar(path: Path, destination: Path) -> dict:
    try:
        import rarfile
    except ImportError as exc:
        raise RuntimeError("RAR extraction needs the rarfile package") from exc
    if not shutil.which("bsdtar"):
        raise RuntimeError("RAR extraction needs libarchive-tools (bsdtar)")
    selections = []
    with rarfile.RarFile(path) as r:
        for info in r.infolist():
            if info.is_symlink():
                raise ArchiveUnsafe("RAR symlink not permitted")
            if hasattr(info, "is_file") and not info.is_file():
                continue
            rel = _safe_member(info.filename, info.file_size, is_dir=info.is_dir())
            if rel:
                selections.append((info, rel))
        _check_total([(i.filename, i.file_size, False) for i, _ in selections])
    for info, rel in selections:
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["bsdtar", "-xOf", str(path.resolve()), info.filename],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=80,
        )
        if proc.returncode != 0 or len(proc.stdout) != info.file_size:
            raise ArchiveUnsafe(f"RAR extraction failed/incomplete for {info.filename!r}")
        target.write_bytes(proc.stdout)
    return {"container": "rar", "extracted_files": len(selections)}


def discover_project_root(destination: Path) -> Path:
    candidates = []
    for main in destination.rglob("src/main.py"):
        candidate = main.parent.parent
        if (candidate / "requirements.txt").is_file() and any(
            (candidate / p).is_file() for p in ("README.md", "readme.md", "README.txt")
        ):
            candidates.append(candidate)
    if len(candidates) != 1:
        raise ArchiveUnsafe(
            f"Expected exactly one documented runnable source root, got {len(candidates)}")
    return candidates[0]


def unpack_frozen_submission(frozen_repo: Path, output: Path, *,
                             archive_basename: str) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ArchiveUnsafe("Output must be a new, empty evaluation workspace")
    matches = [p for p in frozen_repo.rglob("*")
               if p.is_file() and p.name == archive_basename]
    if len(matches) != 1:
        raise ArchiveUnsafe(f"Expected exactly one {archive_basename!r} in frozen checkout")
    archive = matches[0]
    output.mkdir(parents=True, exist_ok=True)
    if archive.suffix.lower() == ".zip":
        proof = _extract_zip(archive, output)
    elif archive.suffix.lower() == ".rar":
        proof = _extract_rar(archive, output)
    else:
        raise ArchiveUnsafe("Only ZIP and RAR are accepted for this targeted recovery")
    root = discover_project_root(output)
    proof.update({
        "frozen_archive": archive.name,
        "source_root": str(root.resolve()),
        "has_readme": True,
        "has_requirements": True,
        "source_modified": False,
        "student_code_executed_during_extraction": False,
        "official_result_modified": False,
    })
    return proof


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen-repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--archive-basename", required=True)
    p.add_argument("--proof", type=Path, required=True)
    a=p.parse_args()
    proof=unpack_frozen_submission(a.frozen_repo,a.out,archive_basename=a.archive_basename)
    a.proof.parent.mkdir(parents=True, exist_ok=True)
    a.proof.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(proof,ensure_ascii=False))


if __name__=="__main__":
    main()
