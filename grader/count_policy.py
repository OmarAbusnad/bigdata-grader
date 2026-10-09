"""Count-based grading guards.

Never infer pipeline correctness from counts alone. Use small tolerance bands for
aggregates, and strict observed-before/after invariants for idempotency.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CountDecision:
    verdict: str
    expected: int | None
    actual: int | None
    error_ratio: float | None
    reason: str


def compare_count(actual: int | None, expected: int | None,
                  pass_tolerance: float = 0.01,
                  review_tolerance: float = 0.05) -> CountDecision:
    """1% tolerance passes aggregate counts; 1-5% requires review; >5% fails.

    Independent field-level checks remain strict and are never overridden.
    Missing/invalid measurements are not failures attributable to the student.
    """
    if not (0 <= pass_tolerance <= review_tolerance < 1):
        raise ValueError("Invalid count tolerance policy")
    try:
        if isinstance(actual, bool) or isinstance(expected, bool):
            raise ValueError
        got, want = int(actual), int(expected)
        if got < 0 or want < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return CountDecision("INCONCLUSIVE", None, None, None, "missing_or_invalid_measurement")
    if want == 0:
        return CountDecision("PASS" if got == 0 else "FAIL", want, got,
                             0.0 if got == 0 else 1.0, "expected_zero_must_be_exact")
    ratio = abs(got - want) / want
    verdict = "PASS" if ratio <= pass_tolerance else ("INCONCLUSIVE" if ratio <= review_tolerance else "FAIL")
    return CountDecision(verdict, want, got, ratio, "aggregate_count_band")


def compare_new_inserts(actual_after: int | None, actual_before: int | None,
                        expected_inserts: int | None) -> CountDecision:
    """Evaluate the NEW rows caused by a delta, not the baseline's old mistakes."""
    try:
        if any(isinstance(x, bool) for x in (actual_after, actual_before, expected_inserts)):
            raise ValueError
        after, before, inserts = int(actual_after), int(actual_before), int(expected_inserts)
        if min(after, before, inserts) < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return CountDecision("INCONCLUSIVE", None, None, None, "missing_delta_measurement")
    if after < before:
        return CountDecision("FAIL", inserts, after - before, None,
                             "validated_count_decreased_during_insert_delta")
    return compare_count(after - before, inserts)


def compare_stability(after: int | None, before: int | None) -> CountDecision:
    """Count-only proof of a non-destructive rerun. 0->0 is never sufficient proof."""
    try:
        if isinstance(after, bool) or isinstance(before, bool):
            raise ValueError
        a, b = int(after), int(before)
        if min(a, b) < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return CountDecision("INCONCLUSIVE", None, None, None, "missing_stability_measurement")
    if a == b == 0:
        return CountDecision("INCONCLUSIVE", b, a, 0.0, "zero_rows_no_pipeline_proof")
    if a == b:
        return CountDecision("PASS", b, a, 0.0, "validated_count_unchanged_only")
    return CountDecision("FAIL", b, a, abs(a-b)/max(b, 1), "validated_count_changed_on_rerun")


def compare_baseline_replay(actual_baseline: int | None, original_batch: int | None) -> CountDecision:
    """Avoid punishing a student twice for a batch discrepancy vs the oracle."""
    return compare_stability(actual_baseline, original_batch)
