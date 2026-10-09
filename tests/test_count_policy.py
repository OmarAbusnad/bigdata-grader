import pytest

from grader.count_policy import (
    compare_count,
    compare_new_inserts,
    compare_stability,
    compare_baseline_replay,
)


@pytest.mark.parametrize("observed,expected,verdict", [
    (17000, 17000, "PASS"),
    (17100, 17000, "PASS"),
    (17340, 17000, "INCONCLUSIVE"),
    (16000, 17000, "FAIL"),
    (18500, 17000, "FAIL"),
    (0, 17000, "FAIL"),
    (0, 0, "PASS"),
    (2, 0, "FAIL"),
    (None, 17000, "INCONCLUSIVE"),
])
def test_aggregate_bands(observed, expected, verdict):
    assert compare_count(observed, expected).verdict == verdict


def test_upsert_measures_delta_not_wrong_baseline():
    assert compare_new_inserts(19100, 18500, 600).verdict == "PASS"
    assert compare_new_inserts(19250, 18500, 600).verdict == "FAIL"
    assert compare_new_inserts(18500, 18500, 600).verdict == "FAIL"


def test_baseline_replay_does_not_count_same_error_twice():
    assert compare_baseline_replay(18500, 18500).verdict == "PASS"
    assert compare_baseline_replay(0, 0).verdict == "INCONCLUSIVE"


def test_idempotency_is_exact_and_nonempty():
    assert compare_stability(18994, 18994).verdict == "PASS"
    assert compare_stability(0, 0).verdict == "INCONCLUSIVE"
    assert compare_stability(18995, 18994).verdict == "FAIL"
    assert compare_stability(None, 12).verdict == "INCONCLUSIVE"


def test_invalid_policy_rejected():
    with pytest.raises(ValueError):
        compare_count(1, 2, .20, .05)
