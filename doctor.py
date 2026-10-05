from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from grader.sandbox import docker_available


def cmd_version(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return {"ok": p.returncode == 0, "output": (p.stdout or p.stderr).strip()[:500]}
    except Exception as exc:
        return {"ok": False, "output": str(exc)}


base = Path(__file__).resolve().parent
docker_ok, docker_detail = docker_available()
hidden_dir = base / "datasets" / "hidden"
expected_file = base / "datasets" / "expected.json"

checks = {
    "python": cmd_version([shutil.which("python") or "python", "--version"]),
    "git": cmd_version(["git", "--version"]) if shutil.which("git") else {"ok": False, "output": "git not found"},
    "docker": {"ok": docker_ok, "output": docker_detail},
    "gemini_api_key": {
        "ok": bool(os.getenv("GEMINI_API_KEY")),
        "output": "configured" if os.getenv("GEMINI_API_KEY") else "not configured",
    },
    "hidden_generator": {
        "ok": (base / "datasets" / "generate_hidden_tests.py").exists(),
        "output": str(base / "datasets" / "generate_hidden_tests.py"),
    },
    "hidden_tests": {
        "ok": (hidden_dir / "test_01_small_batch_pipeline.csv").exists(),
        "output": str(hidden_dir),
    },
    "expected_results": {
        "ok": expected_file.exists(),
        "output": str(expected_file),
    },
    "practice_dataset": {
        "ok": (base / "datasets" / "practice" / "01_student_test_small.csv").exists(),
        "output": "optional for grading; generated/distributed separately",
    },
    "runtime_image": {"ok": False, "output": "not checked"},
}

if docker_ok:
    checks["runtime_image"] = cmd_version(["docker", "image", "inspect", "bigdata-grader/student-runtime:4.1"])

print(json.dumps(checks, ensure_ascii=False, indent=2))

required = [
    "python",
    "git",
    "docker",
    "gemini_api_key",
    "hidden_generator",
    "hidden_tests",
    "expected_results",
    "runtime_image",
]
if not all(checks[k]["ok"] for k in required):
    raise SystemExit(2)
