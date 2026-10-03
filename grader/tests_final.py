from __future__ import annotations
import requests


def test_final_api(base_url: str = "http://127.0.0.1:8000", timeout: int = 30) -> dict:
    endpoints = [
        ("GET", "/health"),
        ("GET", "/queries"),
        ("GET", "/aggregations"),
        ("GET", "/jobs"),
    ]
    out = []
    for method, path in endpoints:
        try:
            r = requests.request(method, base_url + path, timeout=timeout)
            out.append({"method": method, "path": path, "status_code": r.status_code, "ok": r.ok, "body": r.text[:2000]})
        except Exception as e:
            out.append({"method": method, "path": path, "status_code": None, "ok": False, "error": str(e)})
    return {"checks": out}
