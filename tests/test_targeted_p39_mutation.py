import ast
from pathlib import Path
from targeted_p39_mutation import STAGES, FROZEN_SHA, STAGE_EXPECTATION

def test_targeted_p39_never_runs_full_spark_or_final_suite():
    assert FROZEN_SHA == "ec844f735a04f351b8e9785d209ddfce74a0c829"
    assert [s[0] for s in STAGES] == [
        "baseline_prerequisite_not_rescored", "upsert_first",
        "upsert_rerun", "incremental_first", "incremental_rerun"
    ]
    assert [flag for _, _, flag in STAGES] == [False, True, True, True, True]
    assert set(STAGE_EXPECTATION) == {stage for stage, _, _ in STAGES}
    ast.parse(Path("targeted_p39_mutation.py").read_text())
