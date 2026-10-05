from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import textwrap
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class SandboxConfig:
    backend: str = "docker"
    cpus: float = 2.0
    memory: str = "6g"
    pids_limit: int = 512
    timeout_seconds: int = 1200
    network_profile: str = "isolated"   # isolated | compat
    read_only_root: bool = False
    no_new_privileges: bool = True
    mongo_image: str = "mongo:7.0"
    runner_image: str = "bigdata-grader/student-runtime:4.1"
    tmpfs_size: str = "1g"


class SandboxError(RuntimeError):
    pass


def docker_available() -> tuple[bool, str]:
    exe = shutil.which("docker")
    if not exe:
        return False, "docker executable not found"
    try:
        p = subprocess.run([exe, "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=20)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout).strip()
        return True, p.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def _safe_id(project_id: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9_.-]+", "-", project_id).strip("-.").lower() or "project"
    return x[:48]


class DockerSandbox:
    """Per-project Docker sandbox with a dedicated MongoDB container and network.

    Runtime code is never executed on the grader host. The student container receives
    CPU/RAM/PID limits, no-new-privileges, cap-drop=ALL, and a project-specific network.
    An internal TCP forwarder allows student code hard-coded to localhost:27017 to reach
    the dedicated MongoDB container.
    """
    def __init__(self, base: Path, project_id: str, repo: Path, hidden_dir: Path, config: SandboxConfig | None = None):
        self.base = Path(base)
        self.project_id = project_id
        self.repo = Path(repo)
        self.hidden_dir = Path(hidden_dir)
        self.config = config or SandboxConfig()
        sid = f"{_safe_id(project_id)}-{uuid.uuid4().hex[:8]}"
        self.id = sid
        self.network = f"bdg-{sid}"
        self.mongo_name = f"bdg-mongo-{sid}"
        self.runner_name = f"bdg-runner-{sid}"
        self.image_name = f"bdg-student-{sid}:latest"
        self.mongo_host_port: int | None = None
        self.mongo_host_uri: str | None = None
        self.sandbox_dir = self.base / "sandboxes" / project_id / sid
        self.build_context = self.sandbox_dir / "buildctx"
        self.logs_dir = self.sandbox_dir / "logs"
        self._started = False

    def _run(self, args: list[str], *, timeout: int | None = None, check: bool = False, cwd: Path | None = None) -> subprocess.CompletedProcess:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout or self.config.timeout_seconds, cwd=str(cwd) if cwd else None)
        if check and p.returncode != 0:
            raise SandboxError(f"Command failed ({p.returncode}): {' '.join(args)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
        return p

    def prepare_build_context(self) -> None:
        if self.build_context.exists():
            shutil.rmtree(self.build_context)
        shutil.copytree(self.repo, self.build_context, ignore=shutil.ignore_patterns(".git", ".venv", "venv", ".grader_venv", "__pycache__", "*.pyc"))
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        dockerfile = textwrap.dedent("""
            FROM bigdata-grader/student-runtime:4.1
            WORKDIR /workspace
            COPY . /workspace
            USER root
            RUN python -m venv /opt/student-venv \
                && /opt/student-venv/bin/python -m pip install --upgrade pip setuptools wheel \
                && if [ -f requirements.txt ]; then /opt/student-venv/bin/pip install --no-cache-dir -r requirements.txt; \
                   elif [ -f pyproject.toml ] || [ -f setup.py ]; then /opt/student-venv/bin/pip install --no-cache-dir .; \
                   fi
            ENV PATH=/opt/student-venv/bin:$PATH \
                PYTHONUNBUFFERED=1 \
                HOME=/tmp/student-home \
                SPARK_LOCAL_IP=127.0.0.1
            RUN mkdir -p /tmp/student-home /workspace/reports /workspace/data && chmod -R a+rwx /tmp/student-home /workspace/reports /workspace/data
            USER student
        """).strip() + "\n"
        (self.build_context / ".grader.Dockerfile").write_text(dockerfile, encoding="utf-8")

    def build(self) -> dict[str, Any]:
        self.prepare_build_context()
        t = time.time()
        p = self._run(["docker", "build", "-f", ".grader.Dockerfile", "-t", self.image_name, "."], cwd=self.build_context, timeout=max(1800, self.config.timeout_seconds))
        (self.logs_dir / "docker_build.stdout.log").write_text(p.stdout, encoding="utf-8", errors="replace")
        (self.logs_dir / "docker_build.stderr.log").write_text(p.stderr, encoding="utf-8", errors="replace")
        return {"ok": p.returncode == 0, "returncode": p.returncode, "elapsed_seconds": round(time.time()-t, 2), "image": self.image_name,
                "stdout_tail": p.stdout[-4000:], "stderr_tail": p.stderr[-8000:]}

    def start(self) -> dict[str, Any]:
        ok, detail = docker_available()
        if not ok:
            raise SandboxError(f"Docker unavailable: {detail}")
        self._run(["docker", "network", "create"] + (["--internal"] if self.config.network_profile == "isolated" else []) + [self.network], check=True)
        # Reserve a concrete loopback port before starting Mongo. Docker 28 on
        # GitHub-hosted runners may accept 127.0.0.1::27017 but fail to expose
        # a discoverable mapping via `docker port`. Using an explicit port keeps
        # the database host-only while making the grader-side URI deterministic.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            host_port = int(s.getsockname()[1])

        # Start Mongo on Docker's normal bridge so the grader host can reach the
        # loopback-published port. Then attach Mongo to the student's internal
        # network with alias "mongo". The student runner stays on the internal
        # network only, so it still has no outbound Internet access.
        mongo_args = [
            "docker", "run", "-d", "--rm", "--name", self.mongo_name,
            "-p", f"127.0.0.1:{host_port}:27017/tcp",
            "--memory", "2g", "--cpus", "1.0", "--pids-limit", "256",
            "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "SETGID", "--cap-add", "SETUID",
            self.config.mongo_image, "--bind_ip_all"
        ]
        self._run(mongo_args, check=True)
        self._run(["docker", "network", "connect", "--alias", "mongo", self.network, self.mongo_name], check=True)
        self._wait_mongo()
        self.mongo_host_port = host_port
        self.mongo_host_uri = f"mongodb://127.0.0.1:{self.mongo_host_port}"
        self._started = True
        return {"network": self.network, "mongo": self.mongo_name, "profile": self.config.network_profile, "host_port": self.mongo_host_port}

    def _wait_mongo(self, timeout: int = 45) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            p = self._run(["docker", "exec", self.mongo_name, "mongosh", "--quiet", "--eval", "db.adminCommand({ping:1}).ok"], timeout=10)
            if p.returncode == 0 and "1" in p.stdout:
                return
            time.sleep(1)
        raise SandboxError("MongoDB sandbox did not become ready")

    def run_student(self, command: str, *, env: dict[str, str] | None = None, timeout: int | None = None) -> dict[str, Any]:
        """Run one student command in an ephemeral restricted container.

        /grader-tests is a read-only mount containing input datasets only. Teacher oracle files
        should live outside hidden_dir or be excluded by caller.
        """
        cmd = "set -eu; (socat TCP-LISTEN:27017,fork,reuseaddr TCP:mongo:27017 >/tmp/socat.log 2>&1 &) ; exec " + command
        args = [
            "docker", "run", "--rm", "--name", self.runner_name,
            "--network", self.network,
            "--cpus", str(self.config.cpus), "--memory", self.config.memory,
            "--pids-limit", str(self.config.pids_limit),
            "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL",
            "--tmpfs", f"/tmp:rw,noexec,nosuid,size={self.config.tmpfs_size}",
            "-v", f"{self.hidden_dir.resolve()}:/grader-tests:ro",
            "-e", "MONGO_URI=mongodb://mongo:27017",
            "-e", "MONGODB_URI=mongodb://mongo:27017",
        ]
        if env:
            for k, v in env.items():
                args += ["-e", f"{k}={v}"]
        args += [self.image_name, "bash", "-lc", cmd]
        t = time.time()
        try:
            p = self._run(args, timeout=timeout)
            result = {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "elapsed_seconds": round(time.time()-t, 3), "timed_out": False}
        except subprocess.TimeoutExpired as exc:
            self._run(["docker", "rm", "-f", self.runner_name], timeout=20)
            result = {"returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "elapsed_seconds": round(time.time()-t, 3), "timed_out": True}
        return result

    def mongo_eval(self, js: str, *, db_name: str) -> tuple[int, str, str]:
        p = self._run(["docker", "exec", self.mongo_name, "mongosh", "--quiet", db_name, "--eval", js], timeout=60)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def mongo_snapshot(self, *, db_name: str, raw: str, validated: str, quarantine: str, business_key: str = "order_id") -> dict[str, Any]:
        js = f'''const d=db; const r=d.getCollection({json.dumps(raw)}); const v=d.getCollection({json.dumps(validated)}); const q=d.getCollection({json.dumps(quarantine)});
        const dup=v.aggregate([{{$group:{{_id:"${business_key}",c:{{$sum:1}}}}}},{{$match:{{c:{{$gt:1}}}}}},{{$count:"n"}}]).toArray();
        print(JSON.stringify({{raw:r.countDocuments({{}}),validated:v.countDocuments({{}}),quarantine:q.countDocuments({{}}),duplicate_business_keys:(dup[0]?.n||0),indexes:v.getIndexes(),validator:(d.getCollectionInfos({{name:{json.dumps(validated)}}})[0]?.options?.validator||null)}}));'''
        code, out, err = self.mongo_eval(js, db_name=db_name)
        if code != 0:
            raise SandboxError(f"Mongo snapshot failed: {err}")
        return json.loads(out.splitlines()[-1])

    def reset_database(self, db_name: str) -> None:
        self.mongo_eval(f"db.dropDatabase();", db_name=db_name)

    def cleanup(self, keep_image: bool = False) -> None:
        for name in [self.runner_name, self.mongo_name]:
            self._run(["docker", "rm", "-f", name], timeout=20)
        self._run(["docker", "network", "rm", self.network], timeout=20)
        if not keep_image:
            self._run(["docker", "image", "rm", "-f", self.image_name], timeout=60)
        self._started = False

    def metadata(self) -> dict[str, Any]:
        return {"id": self.id, "network": self.network, "mongo": self.mongo_name, "image": self.image_name, "config": asdict(self.config), "dir": str(self.sandbox_dir), "mongo_host_port": self.mongo_host_port}
