import pytest
from pathlib import Path
from targeted_spark_only import resolve_frozen_project_root

def test_frozen_nested_repo_exact_root(tmp_path):
    root=tmp_path/"repo"
    nested=root/"midterm-data-pipeline_FINAL_Ali_Alwadhaf"
    nested.mkdir(parents=True)
    saved="/home/runner/work/app/workspaces/P60/repo/midterm-data-pipeline_FINAL_Ali_Alwadhaf"
    assert resolve_frozen_project_root(root,{"repo_path":saved},"P60")==nested.resolve()

def test_normal_frozen_root_remains_unchanged(tmp_path):
    root=tmp_path/"repo";root.mkdir()
    assert resolve_frozen_project_root(root,{"repo_path":"/a/workspaces/P05/repo"},"P05")==root.resolve()

def test_nested_root_must_exist(tmp_path):
    root=tmp_path/"repo";root.mkdir()
    with pytest.raises(ValueError):
        resolve_frozen_project_root(root,{"repo_path":"/a/workspaces/P60/repo/fake"},"P60")
