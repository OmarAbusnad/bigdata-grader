"""Regression: external LLM failures cannot stop a safe, discoverable student command."""
from types import SimpleNamespace

from evaluate_project import _should_hold_for_plan_review


def test_low_confidence_with_known_command_can_execute():
    resolution = {"requires_manual_review": True, "status": "ERROR", "reason": "429 Too Many Requests"}
    plan = SimpleNamespace(ingest_command="python src/main.py --input {file} --database {db_name}")
    assert _should_hold_for_plan_review(resolution, plan, False) is False


def test_no_command_and_low_confidence_remains_manual_review():
    resolution = {"requires_manual_review": True, "status": "ERROR"}
    assert _should_hold_for_plan_review(resolution, SimpleNamespace(ingest_command=None), False) is True


def test_user_explicit_override_allows_unresolved_plan():
    resolution = {"requires_manual_review": True}
    assert _should_hold_for_plan_review(resolution, SimpleNamespace(ingest_command=None), True) is False


def test_high_confidence_does_not_block():
    resolution = {"requires_manual_review": False}
    assert _should_hold_for_plan_review(resolution, SimpleNamespace(ingest_command=None), False) is False
