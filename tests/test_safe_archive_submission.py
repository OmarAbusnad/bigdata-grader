import os
import stat
import zipfile
import pytest

from grader.safe_archive_submission import ArchiveUnsafe, unpack_frozen_submission


def _zip_project(path, *, malicious=None, symlink=False):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("student/src/main.py", 'print("not executed during extraction")\n')
        z.writestr("student/README.md", "# Frozen project\n")
        z.writestr("student/requirements.txt", "pymongo>=4.6\n")
        z.writestr("student/.git/objects/ab/cd", "Git objects must not be extracted")
        if malicious:
            z.writestr(malicious, "unsafe")
        if symlink:
            link=zipfile.ZipInfo("student/src/escape.py")
            link.create_system=3
            link.external_attr=(stat.S_IFLNK | 0o777)<<16
            z.writestr(link, "../../../outside")


def test_safe_zip_extracts_documented_project_without_running_code(tmp_path):
    frozen=tmp_path/"frozen";frozen.mkdir()
    _zip_project(frozen/"submission.zip")
    output=tmp_path/"extracted"
    proof=unpack_frozen_submission(frozen,output,archive_basename="submission.zip")
    assert proof["container"]=="zip"
    assert proof["extracted_files"]==3
    root=output/"student"
    assert root.joinpath("src/main.py").exists()
    assert not root.joinpath(".git").exists()
    assert proof["student_code_executed_during_extraction"] is False
    assert (frozen/"submission.zip").exists()


def test_traversal_is_rejected_before_any_extract(tmp_path):
    frozen=tmp_path/"frozen";frozen.mkdir()
    _zip_project(frozen/"submission.zip",malicious="../escape.txt")
    with pytest.raises(ArchiveUnsafe):
        unpack_frozen_submission(frozen,tmp_path/"out",archive_basename="submission.zip")
    assert not (tmp_path/"escape.txt").exists()


def test_zip_symlinks_are_rejected(tmp_path):
    frozen=tmp_path/"frozen";frozen.mkdir()
    _zip_project(frozen/"submission.zip",symlink=True)
    with pytest.raises(ArchiveUnsafe):
        unpack_frozen_submission(frozen,tmp_path/"out",archive_basename="submission.zip")


def test_cannot_pick_ambiguous_root(tmp_path):
    frozen=tmp_path/"frozen";frozen.mkdir()
    with zipfile.ZipFile(frozen/"submission.zip","w") as z:
        for folder in ("one","two"):
            z.writestr(f"{folder}/src/main.py","print(1)")
            z.writestr(f"{folder}/README.md","# Repo")
            z.writestr(f"{folder}/requirements.txt","pytest")
    with pytest.raises(ArchiveUnsafe,match="exactly one"):
        unpack_frozen_submission(frozen,tmp_path/"out",archive_basename="submission.zip")
