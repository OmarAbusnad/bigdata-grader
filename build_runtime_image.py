from __future__ import annotations
import subprocess
from pathlib import Path
base = Path(__file__).resolve().parent
cmd = ["docker", "build", "-t", "bigdata-grader/student-runtime:4.1", str(base / "runtime-image")]
print(" ".join(cmd))
raise SystemExit(subprocess.call(cmd))
