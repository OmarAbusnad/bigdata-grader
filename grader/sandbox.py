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

from .spark_dependency_audit import check_submission


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


def _normalize_python_launcher(command: str) -> str:
    """Map the Windows 'py' launcher to the active sandbox Python on Linux."""
    return re.sub(r"^\s*py(?=\s)", "python", str(command), count=1, flags=re.I)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


PLATFORM_ONLY_PACKAGES = {
    "pywin32", "pypiwin32", "pywinpty", "pywin32-ctypes",
    "windows-curses", "wincertstore", "win32-setctime", "tensorflow-intel",
}


def _read_requirements_text(source: Path) -> tuple[str, str]:
    raw = source.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    if b"\x00" in raw[:200]:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                text = raw.decode(enc)
                if "\x00" not in text:
                    return text, enc
            except UnicodeError:
                pass
    return raw.decode("utf-8-sig", errors="replace"), "utf-8-sig"


def _write_compat_requirements(source: Path, dest: Path) -> list[str]:
    """Create a conservative Linux-compatible fallback for Windows-only extras.

    The original requirements are always attempted first. This fallback never
    relaxes versions or removes general dependencies; it only skips a small,
    explicit set of packages that cannot install on Linux.
    """
    text, _encoding = _read_requirements_text(source)
    skipped: list[str] = []
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(("-", "--")):
            out.append(raw)
            continue
        name = re.split(r"[<>=!~\[;\s]", stripped, maxsplit=1)[0].strip().lower()
        if name in PLATFORM_ONLY_PACKAGES:
            skipped.append(name)
            out.append(f"# GRADER platform-only skip: {raw}")
        else:
            out.append(raw)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    return skipped


def _requirement_name(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "-", "--")):
        return ""
    return re.split(r"[<>=!~\[;\s]", stripped, maxsplit=1)[0].strip().lower().replace("_", "-")


def _write_runtime_requirements(repo: Path, source: Path, dest: Path) -> dict[str, Any]:
    """Build a bounded requirements profile for oversized environment snapshots.

    Only student-declared packages are eligible. We keep Big Data/API core packages
    and packages imported by runtime-relevant project modules. This avoids treating
    unrelated workstation/ML packages as mandatory grader dependencies.
    """
    text, _encoding = _read_requirements_text(source)
    lines = text.splitlines()
    by_name: dict[str, str] = {}
    for raw in lines:
        name = _requirement_name(raw)
        if name and name not in PLATFORM_ONLY_PACKAGES:
            by_name.setdefault(name, raw)

    core = {
        "pymongo", "pyspark", "fastapi", "uvicorn", "apscheduler", "schedule",
        "python-dotenv", "pandas", "numpy", "requests", "pydantic", "httpx",
        "pytest", "mongomock", "pyyaml", "tqdm", "gunicorn",
    }
    import_map = {
        "dotenv": "python-dotenv", "yaml": "pyyaml", "sklearn": "scikit-learn",
        "cv2": "opencv-python", "pil": "pillow", "bson": "pymongo",
        "dateutil": "python-dateutil", "fastapi": "fastapi", "uvicorn": "uvicorn",
        "pymongo": "pymongo", "pyspark": "pyspark", "pandas": "pandas",
        "numpy": "numpy", "apscheduler": "apscheduler", "schedule": "schedule",
        "tqdm": "tqdm", "requests": "requests", "pydantic": "pydantic",
        "httpx": "httpx", "mongomock": "mongomock", "flask": "flask",
    }
    relevant = re.compile(
        r"(main|api|pipeline|batch|spark|elt|quality|mongo|database|db|"
        r"quer|index|aggregat|material|scheduler|job|loader|router)",
        re.I,
    )
    imported: set[str] = set()
    for path in repo.rglob("*.py"):
        if any(part in {".git", ".venv", "venv", "__pycache__", "node_modules"} for part in path.parts):
            continue
        if not relevant.search(path.as_posix()):
            continue
        try:
            tree = __import__("ast").parse(path.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:
            continue
        for node in __import__("ast").walk(tree):
            if isinstance(node, __import__("ast").Import):
                for alias in node.names:
                    imported.add(alias.name.split(".", 1)[0].lower())
            elif isinstance(node, __import__("ast").ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0].lower())

    selected = set(core)
    selected |= {import_map.get(x, x.replace("_", "-")) for x in imported}
    selected &= set(by_name)

    # Preserve declaration order and exact student pins.
    out: list[str] = []
    selected_names: list[str] = []
    for raw in lines:
        name = _requirement_name(raw)
        if name in selected and name not in selected_names:
            out.append(raw)
            selected_names.append(name)

    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {
        "declared_count": len(by_name),
        "selected_count": len(selected_names),
        "selected_packages": selected_names,
    }


def _collect_requirement_manifests(repo: Path) -> list[Path]:
    """Collect student dependency manifests from root and conventional Phase-2 folders."""
    out: list[Path] = []
    root = repo / "requirements.txt"
    if root.is_file():
        out.append(root)
    allowed_roots = {"final_extension", "final", "phase2", "phase_2", "phase-2"}
    for path in repo.rglob("requirements*.txt"):
        if path == root or not path.is_file():
            continue
        rel = path.relative_to(repo)
        if len(rel.parts) <= 3 and rel.parts[0].lower() in allowed_roots:
            out.append(path)
    return sorted(out, key=lambda p: (0 if p == root else 1, p.as_posix().lower()))


def _write_combined_requirements(repo: Path, dest: Path) -> dict[str, Any]:
    manifests = _collect_requirement_manifests(repo)
    if not manifests:
        return {"manifests": [], "line_count": 0}
    seen: set[str] = set()
    lines: list[str] = []
    for manifest in manifests:
        text, _enc = _read_requirements_text(manifest)
        lines.append(f"# --- {manifest.relative_to(repo).as_posix()} ---")
        for raw in text.splitlines():
            key = raw.strip()
            if not key or key.startswith("#"):
                continue
            if key not in seen:
                seen.add(key)
                lines.append(raw)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "manifests": [p.relative_to(repo).as_posix() for p in manifests],
        "line_count": len(seen),
    }


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

    def _run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
        check: bool = False,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout or self.config.timeout_seconds,
            cwd=str(cwd) if cwd else None,
        )
        if check and p.returncode != 0:
            raise SandboxError(f"Command failed ({p.returncode}): {' '.join(args)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
        return p

    def prepare_build_context(self) -> None:
        if self.build_context.exists():
            shutil.rmtree(self.build_context)
        shutil.copytree(self.repo, self.build_context, ignore=shutil.ignore_patterns(".git", ".venv", "venv", ".grader_venv", "__pycache__", "*.pyc"))
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        compat_skipped: list[str] = []
        runtime_profile: dict[str, Any] = {}
        combined_req = self.build_context / ".grader.requirements.combined.txt"
        manifest_meta = _write_combined_requirements(self.build_context, combined_req)
        req = combined_req if combined_req.is_file() and manifest_meta.get("line_count") else (self.build_context / "requirements.txt")
        compat_req = self.build_context / ".grader.requirements.compat.txt"
        runtime_req = self.build_context / ".grader.requirements.runtime.txt"
        use_runtime_profile = False
        if req.is_file():
            compat_skipped = _write_compat_requirements(req, compat_req)
            runtime_profile = _write_runtime_requirements(self.build_context, req, runtime_req)
            # Large requirements files are commonly workstation/environment
            # snapshots. Installing all of them can exceed GitHub runner disk
            # before the actual Big Data project is tested.
            use_runtime_profile = int(runtime_profile.get("declared_count", 0) or 0) > 80
        self._compat_requirements_skipped = compat_skipped
        self._runtime_requirements_profile = runtime_profile
        self._requirements_manifest_meta = manifest_meta
        self._use_runtime_requirements_profile = use_runtime_profile

        # Opt-in, auditable prewarming of EXACTLY the student's declared MongoDB
        # connector artifact; executed during image build where Maven is reachable.
        # Student source is never executed; isolated runtime remains offline.
        spark_prefetch = {"enabled": False, "packages": [], "reason": "not_requested"}
        if os.environ.get("GRADER_PREWARM_SPARK") == "1":
            diagnosis = check_submission(self.repo, runtime_error="unresolved dependencies")
            spark_prefetch = {
                "enabled": diagnosis["status"] == "GRADER_NETWORK_DEPENDENCY_PRECONDITION",
                "packages": diagnosis["declared_coordinates"],
                "reason": diagnosis["status"],
            }
            if spark_prefetch["enabled"] and spark_prefetch["packages"]:
                (self.build_context / ".grader.spark-prefetch.txt").write_text(
                    ",".join(spark_prefetch["packages"]), encoding="utf-8"
                )
                (self.build_context / ".grader.spark-cache-only.py").write_text(
                    'print("GRADER_SPARK_PACKAGE_CACHE_ONLY")' + "\n",
                    encoding="utf-8",
                )
                prewarm_script = [
                    "#!/usr/bin/env bash",
                    "set -u",
                    "mkdir -p /home/student/.ivy2",
                    "export HOME=/home/student SPARK_LOCAL_IP=127.0.0.1",
                    'packages="$(cat /workspace/.grader.spark-prefetch.txt)"',
                    'timeout 240s /opt/student-venv/bin/spark-submit --master "local[1]" --conf spark.jars.ivy=/home/student/.ivy2 --packages "$packages" /workspace/.grader.spark-cache-only.py',
                    "rc=$?",
                    "echo GRADER_SPARK_PREFETCH_RC=$rc",
                    "chown -R student:student /home/student/.ivy2 || true",
                    "chmod -R u+rwX /home/student/.ivy2 || true",
                    "exit 0",
                ]
                (self.build_context / ".grader.spark-prewarm.sh").write_text(
                    "\n".join(prewarm_script) + "\n", encoding="utf-8",
                )
                # Resolve saved Maven/Ivy metadata using a local filesystem
                # resolver. Spark must NEVER query Maven Central from a student's
                # network-isolated runtime; dynamic transitive ranges must be
                # resolvable against the prewarmed Ivy metadata instead.
                (self.build_context / ".grader.spark-offline-ivy.xml").write_text(
                    '<ivysettings>\n'
                    '  <settings defaultResolver="offline-artifacts"/>\n'
                    '  <resolvers>\n'
                    '    <filesystem name="offline-artifacts" local="true">\n'
                    '      <ivy pattern="/home/student/.ivy2/cache/[organisation]/[module]/ivy-[revision].xml"/>\n'
                    '      <artifact pattern="/home/student/.ivy2/cache/[organisation]/[module]/[type]s/[artifact]-[revision](-[classifier]).[ext]"/>\n'
                    '    </filesystem>\n'
                    '  </resolvers>\n'
                    '</ivysettings>\n',
                    encoding="utf-8",
                )
                spark_conf = self.build_context / ".grader.spark-conf"
                spark_conf.mkdir(exist_ok=True)
                (spark_conf / "spark-defaults.conf").write_text(
                    "spark.jars.ivySettings file:///workspace/.grader.spark-offline-ivy.xml\n"
                    "spark.jars.ivy /home/student/.ivy2\n",
                    encoding="utf-8",
                )
        self._spark_prefetch = spark_prefetch

        # Keep an open-ended PySpark requirement binary-compatible with the declared Scala 2.12 connector.
        constraint_flag = ""
        try:
            from .spark_dependency_audit import check_submission as _audit, scala_compat_constraint
            constraint = scala_compat_constraint(_audit(self.repo))
            if constraint:
                (self.build_context / ".grader.constraints.txt").write_text(constraint + "\n", encoding="utf-8")
                constraint_flag = " -c .grader.constraints.txt"
        except Exception:
            constraint_flag = ""

        install_source = ".grader.requirements.combined.txt" if combined_req.is_file() and manifest_meta.get("line_count") else "requirements.txt"
        install_clause = (
            f'/opt/student-venv/bin/pip install --no-cache-dir -r .grader.requirements.runtime.txt{constraint_flag} '
            '&& echo "GRADER_REQUIREMENTS_MODE=runtime_profile_large_manifest"'
            if use_runtime_profile
            else f'(/opt/student-venv/bin/pip install --no-cache-dir -r {install_source}{constraint_flag} '
                 '|| (echo "GRADER_REQUIREMENTS_FALLBACK=platform_compat" '
                 f'&& /opt/student-venv/bin/pip install --no-cache-dir -r .grader.requirements.compat.txt{constraint_flag}))'
        )

        spark_runtime_conf = (
            "ENV SPARK_CONF_DIR=/workspace/.grader.spark-conf"
            if getattr(self, "_spark_prefetch", {}).get("enabled") else "# Spark prewarm disabled"
        )
        prewarm_step = (
            "RUN bash /workspace/.grader.spark-prewarm.sh"
            if getattr(self, "_spark_prefetch", {}).get("enabled") else ""
        )
        dockerfile = textwrap.dedent(f"""
            FROM bigdata-grader/student-runtime:4.1
            WORKDIR /workspace
            COPY . /workspace
            USER root
            RUN python -m venv /opt/student-venv \
                && /opt/student-venv/bin/python -m pip install --upgrade pip setuptools wheel \
                && if [ -f {install_source} ]; then \
                     {install_clause}; \
                   elif [ -f pyproject.toml ] || [ -f setup.py ]; then /opt/student-venv/bin/pip install --no-cache-dir .; \
                   fi
            {prewarm_step}
            {spark_runtime_conf}
            ENV PATH=/opt/student-venv/bin:$PATH \
                PYSPARK_PYTHON=/opt/student-venv/bin/python \
                PYSPARK_DRIVER_PYTHON=/opt/student-venv/bin/python \
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
        combined = (p.stdout or "") + "\n" + (p.stderr or "")
        fallback_used = "GRADER_REQUIREMENTS_FALLBACK=platform_compat" in combined
        runtime_profile_used = "GRADER_REQUIREMENTS_MODE=runtime_profile_large_manifest" in combined
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "elapsed_seconds": round(time.time()-t, 2),
            "image": self.image_name,
            "compatibility_fallback_used": fallback_used,
            "runtime_profile_used": runtime_profile_used,
            "runtime_requirements_profile": getattr(self, "_runtime_requirements_profile", {}) if runtime_profile_used else None,
            "spark_dependency_prewarm": getattr(self, "_spark_prefetch", {}),
            "spark_prefetch_log_tail": combined[-1200:] if getattr(self, "_spark_prefetch", {}).get("enabled") else None,
            "requirements_manifests": getattr(self, "_requirements_manifest_meta", {}).get("manifests", []),
            "platform_packages_skipped": list(getattr(self, "_compat_requirements_skipped", []) or []) if (fallback_used or runtime_profile_used) else [],
            "stdout_tail": p.stdout[-4000:],
            "stderr_tail": p.stderr[-8000:],
        }

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

    def run_student(
        self,
        command: str,
        *,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        stdin_text: str | None = None,
        working_directory: str | None = None,
    ) -> dict[str, Any]:
        """Run one student command in an ephemeral restricted container.

        /grader-tests is a read-only mount containing input datasets only. Teacher oracle files
        should live outside hidden_dir or be excluded by caller.
        """
        command = _normalize_python_launcher(command)
        cmd = "set -eu; (socat TCP-LISTEN:27017,fork,reuseaddr TCP:mongo:27017 >/tmp/socat.log 2>&1 &) ; exec " + command
        args = [
            "docker", "run", "--rm",
        ]
        if stdin_text is not None:
            args.append("-i")
        args += [
            "--name", self.runner_name,
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
        if working_directory:
            rel = str(working_directory).strip().replace("\\", "/").strip("/")
            if rel and rel != "." and ".." not in Path(rel).parts:
                args += ["-w", f"/workspace/{rel}"]
        # Do not use a login shell here. `bash -l` may rebuild PATH from
        # /etc/profile and hide /opt/student-venv/bin, which makes declared
        # student dependencies appear missing at runtime. Preserve the image
        # ENV PATH so commands execute with the per-project virtualenv.
        args += [self.image_name, "bash", "-c", cmd]
        t = time.time()
        try:
            p = self._run(args, timeout=timeout, input_text=stdin_text)
            result = {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "elapsed_seconds": round(time.time()-t, 3), "timed_out": False}
        except subprocess.TimeoutExpired as exc:
            self._run(["docker", "rm", "-f", self.runner_name], timeout=20)
            result = {
                "returncode": 124,
                "stdout": _as_text(exc.stdout),
                "stderr": _as_text(exc.stderr),
                "elapsed_seconds": round(time.time()-t, 3),
                "timed_out": True,
            }
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
