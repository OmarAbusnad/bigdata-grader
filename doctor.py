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
checks = {
    "python": cmd_version([shutil.which("python") or "python", "--version"]),
    "git": cmd_version(["git", "--version"]) if shutil.which("git") else {"ok": False, "output": "git not found"},
    "docker": {"ok": docker_ok, "output": docker_detail},
    "openai_api_key": {"ok": bool(os.getenv("OPENAI_API_KEY")), "output": "configured" if os.getenv("OPENAI_API_KEY") else "not configured"},
    "hidden_generator": {"ok": (base / "datasets" / "generate_hidden_tests.py").exists(), "output": str(base / "datasets" / "generate_hidden_tests.py")},
    "practice_dataset": {"ok": (base / "datasets" / "practice" / "01_student_test_small.csv").exists(), "output": str(base / "datasets" / "practice" / "01_student_test_small.csv")},
    "runtime_image": {"ok": False, "output": "not checked"},
}
if docker_ok:
    checks["runtime_image"] = cmd_version(["docker", "image", "inspect", "bigdata-grader/student-runtime:4.1"])

print(json.dumps(checks, ensure_ascii=False, indent=2))
required = ["python", "git", "docker", "hidden_generator", "practice_dataset"]
if not all(checks[k]["ok"] for k in required):
    raise SystemExit(2)
