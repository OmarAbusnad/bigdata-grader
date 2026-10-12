"""Regression for P50: nested scheduler_status.jobs is a real job list."""
import json
import re
import urllib.parse
from grader.final_runtime import _probe_python


def _run_job_listing(body):
    script = _probe_python()
    start = script.index('j = request("GET", "/jobs", timeout=30)')
    stop = script.index("# Adaptive retry:", start)
    snippet = script[start:stop]
    calls = []
    def request(method, path, payload=None, timeout=30):
        calls.append((method, path))
        if method == "GET":
            return {"status": 200, "ok": True, "body": body}
        return {"status": 200, "ok": True, "body": {"status": "SUCCESS"}}
    def fallback(value, preferred):
        # Match previous behavior: wrapper-only API returned no usable names.
        return []
    scope = {"request": request, "names_from": fallback,
             "urllib": urllib, "result": {}, "re": re, "json": json}
    exec(compile(snippet, "<isolated final scheduler probe>", "exec"), scope)
    return scope["result"], calls


def test_p50_nested_jobs_generate_two_true_manual_probe_requests():
    body = {"status": "SUCCESS", "scheduler_status": {
        "scheduler_running": True, "jobs_count": 2,
        "jobs": [{"job_name": "refresh_materialized_views", "interval_minutes": 5},
                 {"job_name": "daily_executive_report", "interval_minutes": 10}]}}
    got, calls = _run_job_listing(body)
    assert got["job_names"] == ["refresh_materialized_views", "daily_executive_report"]
    assert len(got["job_calls"]) == 2
    assert calls == [
        ("GET", "/jobs"),
        ("POST", "/jobs/refresh_materialized_views/run"),
        ("POST", "/jobs/daily_executive_report/run"),
    ]
    assert all(c["response"]["ok"] for c in got["job_calls"])


def test_empty_jobs_do_not_invent_achievements():
    got, calls = _run_job_listing({"scheduler_status": {"jobs_count": 0, "jobs": []}})
    assert got["job_names"] == []
    assert got["job_calls"] == []
    assert calls == [("GET", "/jobs")]
