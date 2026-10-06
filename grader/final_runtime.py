from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from .sandbox import DockerSandbox, SandboxConfig
from .api_semantic_normalizer import normalize_probe
from .final_compliance import meaningful_payload, readme_contract, explain_compliance, job_log_compliance


REQUIRED_ENDPOINTS = {
    "/health": "get",
    "/ingest": "post",
    "/indexes": "post",
    "/queries": "get",
    "/queries/{name}": "get",
    "/aggregations": "get",
    "/aggregations/{name}": "get",
    "/refresh-mv": "post",
    "/jobs": "get",
    "/jobs/{name}/run": "post",
}


def _assertion(key: str, label: str, verdict: str, *, expected: Any = None, actual: Any = None,
               evidence: list[str] | None = None, note: str | None = None) -> dict[str, Any]:
    return {
        "key": key, "label": label, "verdict": verdict, "expected": expected,
        "actual": actual, "evidence": evidence or [], "note": note,
    }


def _classify_startup_failure(repo: Path, service_run: dict[str, Any]) -> dict[str, Any]:
    """Use deterministic evidence first; keep AI out of root-cause classification when rules suffice."""
    stdout = str(service_run.get("stdout") or "")
    stderr = str(service_run.get("stderr") or "")
    text = stdout + "\n" + stderr
    if service_run.get("timed_out"):
        return {"code": "TIMEOUT", "evidence": ["service startup timed out"]}

    m = re.search(r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]", text)
    if m:
        module = m.group(1)
        top = module.split(".", 1)[0]
        local = (repo / f"{top}.py").is_file() or (repo / top / "__init__.py").is_file()
        requirements = ""
        try:
            requirements = (repo / "requirements.txt").read_text(encoding="utf-8-sig", errors="replace").lower()
        except Exception:
            pass
        declared = bool(re.search(rf"(?m)^\s*{re.escape(top.lower())}(?:\s|[<>=!~\[]|$)", requirements))
        if not local and not declared:
            return {
                "code": "STUDENT_DEPENDENCY_FAILURE",
                "evidence": [f"missing module: {module}", f"{top} not declared in requirements.txt"],
            }
        return {
            "code": "STUDENT_CONFIGURATION_FAILURE",
            "evidence": [f"module import failed: {module}"],
        }

    if re.search(r"SyntaxError|IndentationError", text):
        return {"code": "STUDENT_CODE_FAILURE", "evidence": ["Python syntax/import-time error"]}
    if re.search(r"ImportError:", text):
        return {"code": "STUDENT_CONFIGURATION_FAILURE", "evidence": ["ImportError during API startup"]}
    if re.search(r"Address already in use|port.*already", text, re.I):
        return {"code": "GRADER_INFRA_FAILURE", "evidence": ["port collision in sandbox"]}
    return {
        "code": "STUDENT_CONFIGURATION_OR_DEPENDENCY_FAILURE",
        "evidence": ["server did not become ready; no narrower deterministic rule matched"],
    }


def _blocked_assertions(reason: str) -> list[dict[str, Any]]:
    """Dependent final checks are blocked when runtime readiness was not achieved."""
    specs = [
        ("final.api.contract", "Required unified API contract is exposed"),
        ("final.api.health", "GET /health works"),
        ("final.api.docs", "Swagger /docs is available"),
        ("final.api.ingest", "POST /ingest invokes the project pipeline"),
        ("final.queries.count", "At least five practical queries are exposed"),
        ("final.queries.runtime", "Practical queries execute against seeded data"),
        ("final.aggregations.count", "At least five aggregation reports are exposed"),
        ("final.aggregations.runtime", "Aggregation reports execute and return actual data"),
        ("final.indexes.count", "Indexes required for Phase 2 exist"),
        ("final.indexes.compound", "At least one compound index exists"),
        ("final.indexes.explain", "Three explain/executionStats cases before/after indexes are evidenced"),
        ("final.mv.refresh", "Materialized-view refresh endpoint works"),
        ("final.mv.collections", "At least two populated materialized-view collections exist"),
        ("final.mv.incremental", "Materialized-view refresh is incremental"),
        ("final.jobs.count", "At least two scheduled jobs are exposed"),
        ("final.jobs.manual_run", "Scheduled jobs support manual execution"),
        ("final.jobs.schedule", "Job schedules are visible/configured"),
        ("final.jobs.logging", "Job logs include start/end/status/result"),
    ]
    return [
        _assertion(k, label, "INCONCLUSIVE", expected="runtime ready", actual="BLOCKED",
                   note=f"Blocked by root cause: {reason}")
        for k, label in specs
    ]


def _fixture_docs() -> list[dict[str, Any]]:
    rows = [
        ("F-001", "Sanaa", "Delivered", "CUST-001", "2026-01-01T10:20:00", "cash", 125.0),
        ("F-002", "Sanaa", "Pending", "CUST-001", "2026-01-02T11:00:00", "card", 80.0),
        ("F-003", "Aden", "Delivered", "CUST-002", "2026-01-03T09:30:00", "cash", 310.0),
        ("F-004", "Taiz", "Cancelled", "CUST-003", "2026-02-01T15:00:00", "wallet", 45.0),
        ("F-005", "Ibb", "Delivered", "CUST-004", "2026-02-03T18:10:00", "card", 510.0),
        ("F-006", "Sanaa", "Shipped", "CUST-005", "2026-03-05T13:15:00", "cash", 210.0),
        ("F-007", "Aden", "Delivered", "CUST-006", "2026-03-08T07:45:00", "wallet", 905.0),
        ("F-008", "Hodeidah", "Pending", "CUST-007", "2026-04-01T10:00:00", "cash", 65.0),
        ("F-009", "Sanaa", "Delivered", "CUST-008", "2026-04-10T12:00:00", "card", 1500.0),
        ("F-010", "Taiz", "Shipped", "CUST-009", "2026-05-11T14:30:00", "wallet", 175.0),
        ("F-011", "Ibb", "Delivered", "CUST-010", "2026-05-12T08:20:00", "cash", 260.0),
        ("F-012", "Sanaa", "Delivered", "CUST-001", "2026-06-01T16:40:00", "card", 740.0),
    ]
    docs = []
    for order_id, city, status, customer_id, order_date, payment_method, total in rows:
        clean = {
            "order_id": order_id, "city": city, "status": status,
            "customer_id": customer_id, "order_date": order_date,
            "payment_method": payment_method, "total_amount": total,
            "payment_amount": total, "currency": "YER", "delivery_type": "standard",
        }
        docs.append({
            **clean,
            "record_clean": dict(clean),
            "cleaned_record": dict(clean),
            "updated_at": order_date,
            "created_at": order_date,
            "quality_status": "valid",
        })
    return docs


def _probe_python() -> str:
    return r'''import json, time, urllib.parse, urllib.request, urllib.error

BASE = "http://127.0.0.1:8000"
DATASET = "/grader-tests/test_01_small_batch_pipeline.csv"

def request(method, path, body=None, timeout=180):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try: parsed = json.loads(raw)
            except Exception: parsed = raw[:5000]
            return {"status": r.status, "ok": 200 <= r.status < 300, "body": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try: parsed = json.loads(raw)
        except Exception: parsed = raw[:5000]
        return {"status": e.code, "ok": False, "body": parsed}
    except Exception as e:
        return {"status": None, "ok": False, "error": f"{type(e).__name__}: {e}"}

def resolve_schema(openapi, schema):
    if not isinstance(schema, dict): return {}
    ref = schema.get("$ref")
    if ref and ref.startswith("#/"):
        cur = openapi
        for part in ref[2:].split("/"):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        return cur if isinstance(cur, dict) else {}
    return schema

def sample_value(name, schema=None):
    n = name.lower()
    schema = resolve_schema(openapi, schema or {})
    typ = schema.get("type")
    if typ == "integer": return 10
    if typ == "number": return 10.0
    if typ == "boolean": return True
    if typ == "array": return []
    enum = schema.get("enum")
    if isinstance(enum, list) and enum: return enum[0]
    if "city" in n: return "Sanaa"
    if "status" in n: return "Delivered"
    if "customer" in n: return "CUST-001"
    if "payment" in n or "method" in n: return "cash"
    if "engine" in n: return "batch"
    if "start" in n and "date" in n: return "2026-01-01"
    if "end" in n and "date" in n: return "2026-12-31"
    if "date" in n: return "2026-01-01"
    if any(x in n for x in ["limit", "size", "count", "batch"]): return 10
    if any(x in n for x in ["min", "amount", "total", "price", "value"]): return 10
    return "test"

def names_from(value, preferred):
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                child = value[key]
                if isinstance(child, dict):
                    keys = [
                        str(k) for k, v in child.items()
                        if str(k).lower() not in {"count", "total", "status", "message", "meta", "metadata"}
                        and not str(k).lower().endswith("_count")
                    ]
                    if keys: return keys
                got = names_from(child, preferred)
                if got: return got
        object_keys = [
            str(k) for k, v in value.items()
            if isinstance(v, dict)
            and str(k).lower() not in {"meta", "metadata", "status", "message"}
            and not str(k).lower().endswith("_count")
        ]
        if len(object_keys) >= 2: return object_keys
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                val = item.get("name") or item.get("id") or item.get("key") or item.get("job")
                if val is not None: out.append(str(val))
        return out
    return []

def build_ingest_body(openapi):
    post = ((openapi.get("paths") or {}).get("/ingest") or {}).get("post") or {}
    schema = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    schema = resolve_schema(openapi, schema)
    props = schema.get("properties") or {}
    if props:
        body = {}
        for name, prop_schema in props.items():
            n = name.lower()
            body[name] = DATASET if any(x in n for x in ["path", "file", "input"]) else sample_value(name, prop_schema)
        return [body]
    return [
        {"input_path": DATASET}, {"file_path": DATASET}, {"path": DATASET},
        {"file": DATASET}, {"input": DATASET},
    ]

result = {"server_ready": False}
openapi = None
chk = {}
for _ in range(35):
    chk = request("GET", "/openapi.json", timeout=2)
    if chk.get("ok") and isinstance(chk.get("body"), dict):
        openapi = chk["body"]
        result["server_ready"] = True
        break
    time.sleep(1)

if not openapi:
    result["startup_check"] = chk
    print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)

result["openapi"] = {"status": 200, "paths": {p: sorted((ops or {}).keys()) for p, ops in (openapi.get("paths") or {}).items()}}
result["docs"] = request("GET", "/docs", timeout=10)
result["health"] = request("GET", "/health", timeout=15)

ingest_attempts = []
for body in build_ingest_body(openapi):
    r = request("POST", "/ingest", body, timeout=240)
    ingest_attempts.append({"body_keys": sorted(body.keys()), "response": r})
    if r.get("ok") or r.get("status") not in (400, 404, 422):
        break
result["ingest_attempts"] = ingest_attempts
result["indexes"] = request("POST", "/indexes", {}, timeout=60)

q = request("GET", "/queries", timeout=30)
result["queries"] = q
qnames = names_from(q.get("body"), ["queries", "items", "data", "results"])
result["query_names"] = qnames[:30]
qcalls = []
qspec = ((openapi.get("paths") or {}).get("/queries/{name}") or {}).get("get") or {}
for name in qnames[:5]:
    params = {}
    for p in qspec.get("parameters") or []:
        if p.get("in") != "query": continue
        pname = p.get("name")
        if pname and (p.get("required") or pname.lower() == "limit"):
            params[pname] = sample_value(pname, p.get("schema") or {})
    suffix = "?" + urllib.parse.urlencode(params) if params else ""
    qcalls.append({"name": name, "params": params, "response": request("GET", "/queries/" + urllib.parse.quote(name, safe="") + suffix, timeout=60)})
result["query_calls"] = qcalls

a = request("GET", "/aggregations", timeout=30)
result["aggregations"] = a
anames = names_from(a.get("body"), ["aggregations", "items", "data", "results", "reports", "aggregation_reports", "available_reports"])
result["aggregation_names"] = anames[:30]
result["aggregation_calls"] = [
    {"name": name, "response": request("GET", "/aggregations/" + urllib.parse.quote(name, safe=""), timeout=90)}
    for name in anames[:5]
]

result["refresh_mv_first"] = request("POST", "/refresh-mv", {}, timeout=120)
result["refresh_mv_second"] = request("POST", "/refresh-mv", {}, timeout=120)

j = request("GET", "/jobs", timeout=30)
result["jobs"] = j
jnames = names_from(j.get("body"), ["jobs", "items", "data", "results", "scheduled_jobs", "tasks", "registered_jobs"])
result["job_names"] = jnames[:30]
result["job_calls"] = [
    {"name": name, "response": request("POST", "/jobs/" + urllib.parse.quote(name, safe="") + "/run", {}, timeout=120)}
    for name in jnames[:2]
]
result["jobs_after_runs"] = request("GET", "/jobs", timeout=30)

print("FINAL_PROBE_JSON=" + json.dumps(result, ensure_ascii=False))
'''


def _probe_shell() -> str:
    return r'''#!/usr/bin/env bash
set -u
if [ -z "$FINAL_API_TARGET" ]; then
  echo "FINAL_API_TARGET is required"
  exit 2
fi
python -m uvicorn "$FINAL_API_TARGET" --host 127.0.0.1 --port 8000 >/tmp/final-api.log 2>&1 &
pid=$!
cleanup() {
  kill "$pid" >/dev/null 2>&1 || true
  wait "$pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT
python /grader-tests/final_api_probe.py
rc=$?
echo "FINAL_API_SERVER_LOG_BEGIN"
tail -n 160 /tmp/final-api.log 2>/dev/null || true
echo "FINAL_API_SERVER_LOG_END"
exit "$rc"
'''


def _extract_probe(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if line.startswith("FINAL_PROBE_JSON="):
            try:
                return json.loads(line.split("=", 1)[1])
            except Exception:
                return {}
    return {}


def _nested(doc: dict[str, Any], dotted: str) -> Any:
    cur: Any = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _contains_ixscan(value: Any) -> bool:
    if isinstance(value, dict):
        if str(value.get("stage", "")).upper() == "IXSCAN":
            return True
        return any(_contains_ixscan(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_ixscan(v) for v in value)
    return False


def _find_active_database(
    client: MongoClient,
    preferred_name: str,
    *,
    validated_name: str,
    raw_name: str,
    quarantine_name: str,
    health_body: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Select the database actually used by the student's API from runtime state.

    The grader container is isolated per project, so inspecting its database list
    is stronger and safer than trusting a guessed database name.
    """
    hinted: set[str] = set()

    def collect_hints(value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                kl = str(k).lower()
                if kl in {"database", "db", "db_name", "database_name", "mongo_db", "mongo_database"} and isinstance(v, str) and v.strip():
                    hinted.add(v.strip())
                collect_hints(v)
        elif isinstance(value, list):
            for item in value[:30]:
                collect_hints(item)

    collect_hints(health_body)
    scores: list[tuple[float, str, dict[str, Any]]] = []
    for name in client.list_database_names():
        if name in {"admin", "config", "local"}:
            continue
        dbx = client[name]
        try:
            cols = set(dbx.list_collection_names())
        except Exception:
            continue
        score = 0.0
        reasons: list[str] = []
        if name == preferred_name:
            score += 1.0
            reasons.append("preferred")
        if name in hinted:
            score += 8.0
            reasons.append("health_hint")
        for col_name, weight in [
            (validated_name, 6.0),
            (raw_name, 4.0),
            (quarantine_name, 3.0),
        ]:
            if col_name in cols:
                score += weight
                try:
                    count = dbx[col_name].count_documents({})
                except Exception:
                    count = 0
                if count > 0:
                    score += min(5.0, 1.0 + (count > 10) + (count > 1000))
                    reasons.append(f"{col_name}:{count}")
        extra_signal = 0
        for cname in cols:
            low = cname.lower()
            if re.search(r"(^mv[_-]|material|summary|view|job.*log|log.*job)", low):
                extra_signal += 1
        if extra_signal:
            score += min(3.0, extra_signal)
            reasons.append(f"phase2_collections:{extra_signal}")
        scores.append((score, name, {"collections": sorted(cols), "reasons": reasons}))

    if not scores:
        return preferred_name, {"source": "fallback", "candidates": []}
    scores.sort(key=lambda x: (-x[0], x[1]))
    best_score, best_name, meta = scores[0]
    return best_name, {
        "source": "runtime_database_state",
        "selected": best_name,
        "score": best_score,
        "health_hints": sorted(hinted),
        "reasons": meta["reasons"],
        "candidates": [
            {"database": name, "score": score, "reasons": m["reasons"]}
            for score, name, m in scores[:8]
        ],
    }


def _second_refresh_incremental(probe: dict[str, Any]) -> tuple[bool, list[str]]:
    response = probe.get("refresh_mv_second") or {}
    body = response.get("body")
    evidence = []
    if not response.get("ok"):
        return False, evidence
    txt = json.dumps(body, ensure_ascii=False).lower()
    if "incremental" in txt:
        return True, ["Second refresh reports incremental mode."]

    def walk(v: Any):
        if isinstance(v, dict):
            for k, val in v.items():
                kl = str(k).lower()
                if any(x in kl for x in ["changed", "processed", "delta", "new_rows"]) and isinstance(val, (int, float)):
                    yield kl, val
                yield from walk(val)
        elif isinstance(v, list):
            for item in v:
                yield from walk(item)

    zeros = [(k, v) for k, v in walk(body) if v == 0]
    if zeros:
        return True, ["Second refresh reports zero changed/delta rows: " + ", ".join(k for k, _ in zeros[:5])]
    return False, evidence


def run_final_suite(
    *, base: Path, project_id: str, repo: Path, hidden_dir: Path,
    execution_plan, final_plan: dict[str, Any], sandbox_config: SandboxConfig,
    timeout: int = 1200, keep_sandbox: bool = False,
) -> dict[str, Any]:
    assertions = []
    api_target = str(final_plan.get("api_target") or "")
    db_name = execution_plan.database_name or f"grader_{project_id.lower()}"
    validated_name = (execution_plan.collections or {}).get("validated", "orders_validated")
    raw_name = (execution_plan.collections or {}).get("raw", "orders_raw")
    quarantine_name = (execution_plan.collections or {}).get("quarantine", "orders_quarantine")

    if not api_target:
        assertions.append(_assertion(
            "final.api.discovered", "FastAPI application discovered", "FAIL",
            expected="FastAPI app", actual=None, evidence=final_plan.get("warnings") or [],
        ))
        return {"status": "COMPLETED_WITH_FAILURES", "assertions": assertions,
                "assertion_counts": {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 0, "ERROR": 0}, "probe": {}}

    hidden_dir.mkdir(parents=True, exist_ok=True)
    (hidden_dir / "final_api_probe.py").write_text(_probe_python(), encoding="utf-8")
    (hidden_dir / "run_final_api.sh").write_text(_probe_shell(), encoding="utf-8")

    sb = DockerSandbox(base, f"{project_id}-final", repo, hidden_dir, sandbox_config)
    probe = {}
    service_run = {}
    host_evidence = {}

    try:
        build = sb.build()
        if not build.get("ok"):
            return {
                "status": "COMPLETED_WITH_FAILURES",
                "error": "Student dependency image could not be built.",
                "build": build,
                "assertions": [
                    _assertion(
                        "final.environment.build", "Student environment builds from declared dependencies", "FAIL",
                        expected="successful image build", actual=build.get("returncode"),
                        evidence=[build.get("stderr_tail", "")[-3000:]],
                        note="Root cause: STUDENT_DEPENDENCY_FAILURE",
                    ),
                    *_blocked_assertions("STUDENT_DEPENDENCY_FAILURE"),
                ],
                "assertion_counts": {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": len(_blocked_assertions("x")), "ERROR": 0},
            }

        sb.start()
        sb.reset_database(db_name)

        if execution_plan.setup_command:
            host_evidence["setup"] = sb.run_student(
                execution_plan.setup_command,
                env={"MONGO_DATABASE": db_name, "MONGO_DB_NAME": db_name, "DB_NAME": db_name},
                timeout=min(timeout, 180),
            )

        client = MongoClient(sb.mongo_host_uri, serverSelectionTimeoutMS=10000)
        db = client[db_name]
        validated = db[validated_name]
        try:
            validated.insert_many(_fixture_docs(), ordered=False, bypass_document_validation=True)
        except Exception as exc:
            host_evidence["fixture_warning"] = f"{type(exc).__name__}: {exc}"

        indexes_before = validated.index_information()
        collections_before = set(db.list_collection_names())

        service_run = sb.run_student(
            "bash /grader-tests/run_final_api.sh",
            env={"FINAL_API_TARGET": api_target, "MONGO_DATABASE": db_name, "MONGO_DB_NAME": db_name, "DB_NAME": db_name},
            timeout=max(timeout, 600),
        )
        probe = _extract_probe(str(service_run.get("stdout") or ""))
        semantic = normalize_probe(probe)
        probe["semantic_normalization"] = semantic

        if not probe.get("server_ready"):
            classified = _classify_startup_failure(repo, service_run)
            reason = str(classified.get("code") or "STUDENT_CONFIGURATION_OR_DEPENDENCY_FAILURE")
            startup = _assertion(
                "final.api.server", "FastAPI server starts in a clean environment", "FAIL",
                expected=True, actual=False,
                evidence=[str(service_run.get("stderr") or "")[-3500:], str(service_run.get("stdout") or "")[-3500:]],
                note=f"Root cause: {reason}. Dependent checks are BLOCKED, not failed.",
            )
            blocked = _blocked_assertions(reason)
            assertions.extend([
                _assertion("final.api.discovered", "FastAPI application discovered", "PASS",
                           expected="FastAPI app", actual=api_target, evidence=final_plan.get("evidence") or []),
                startup,
                *blocked,
            ])
            counts = {"PASS": 1, "FAIL": 1, "INCONCLUSIVE": len(blocked), "ERROR": 0}
            return {
                "status": "STARTUP_BLOCKED",
                "root_cause": reason,
                "root_cause_evidence": classified.get("evidence") or [],
                "runtime_ready": False,
                "assertions": assertions,
                "assertion_counts": counts,
                "probe": probe,
                "service_run": {
                    "returncode": service_run.get("returncode"),
                    "elapsed_seconds": service_run.get("elapsed_seconds"),
                    "timed_out": service_run.get("timed_out"),
                    "stdout_tail": str(service_run.get("stdout") or "")[-7000:],
                    "stderr_tail": str(service_run.get("stderr") or "")[-5000:],
                },
                "host_evidence": host_evidence,
                "sandbox": sb.metadata(),
            }

        active_db_name, active_db_meta = _find_active_database(
            client,
            db_name,
            validated_name=validated_name,
            raw_name=raw_name,
            quarantine_name=quarantine_name,
            health_body=(probe.get("health") or {}).get("body"),
        )
        if active_db_name != db_name:
            db_name = active_db_name
            db = client[db_name]
            validated = db[validated_name]
        host_evidence["active_database_resolution"] = active_db_meta

        openapi_paths = ((probe.get("openapi") or {}).get("paths") or {})
        assertions.append(_assertion("final.api.discovered", "FastAPI application discovered", "PASS",
                                     expected="FastAPI app", actual=api_target, evidence=final_plan.get("evidence") or []))
        assertions.append(_assertion("final.api.server", "FastAPI server starts in a clean environment",
                                     "PASS" if probe.get("server_ready") else "FAIL",
                                     expected=True, actual=bool(probe.get("server_ready")),
                                     evidence=[str(service_run.get("stderr") or "")[-1500:]]))

        missing = []
        for path, method in REQUIRED_ENDPOINTS.items():
            methods = [str(x).lower() for x in (openapi_paths.get(path) or [])]
            if method not in methods:
                missing.append(f"{method.upper()} {path}")
        assertions.append(_assertion("final.api.contract", "Required unified API contract is exposed",
                                     "PASS" if not missing else "FAIL",
                                     expected=[f"{m.upper()} {p}" for p, m in REQUIRED_ENDPOINTS.items()],
                                     actual="all present" if not missing else {"missing": missing}))

        health = probe.get("health") or {}
        assertions.append(_assertion("final.api.health", "GET /health works", "PASS" if health.get("ok") else "FAIL",
                                     expected="2xx", actual=health.get("status"),
                                     evidence=[json.dumps(health.get("body"), ensure_ascii=False)[:1200]]))
        docs = probe.get("docs") or {}
        assertions.append(_assertion("final.api.docs", "Swagger /docs is available", "PASS" if docs.get("ok") else "FAIL",
                                     expected="2xx", actual=docs.get("status")))

        ingest_attempts = probe.get("ingest_attempts") or []
        ingest_ok = any((x.get("response") or {}).get("ok") for x in ingest_attempts)
        pipeline_counts = {}
        for cname in (raw_name, validated_name, quarantine_name):
            try:
                pipeline_counts[cname] = db[cname].count_documents({}) if cname in db.list_collection_names() else 0
            except Exception:
                pipeline_counts[cname] = 0
        pipeline_effect = pipeline_counts.get(raw_name, 0) > 0 or pipeline_counts.get(validated_name, 0) > 0
        assertions.append(_assertion(
            "final.api.ingest",
            "POST /ingest invokes the existing project pipeline on hidden data",
            "PASS" if ingest_ok and pipeline_effect else ("INCONCLUSIVE" if ingest_ok else "FAIL"),
            expected={"http_2xx": True, "pipeline_database_effect": True},
            actual={
                "statuses": [(x.get("response") or {}).get("status") for x in ingest_attempts],
                "database": db_name,
                "counts": pipeline_counts,
            },
            evidence=[json.dumps(ingest_attempts[-1] if ingest_attempts else {}, ensure_ascii=False)[:1800]],
        ))

        qnames = (semantic.get("queries") or {}).get("names") or probe.get("query_names") or []
        qmeta = semantic.get("queries") or {}
        qcount = max(len(qnames), int(qmeta.get("declared_count") or 0))
        assertions.append(_assertion("final.queries.count", "At least five practical queries are exposed",
                                     "PASS" if qcount >= 5 else "FAIL", expected=">= 5", actual=qcount,
                                     evidence=[json.dumps(qmeta, ensure_ascii=False)[:1800]]))
        qcalls = probe.get("query_calls") or []
        qok = sum(1 for x in qcalls if (x.get("response") or {}).get("ok"))
        qpayload = [
            meaningful_payload((x.get("response") or {}).get("body"))
            for x in qcalls if (x.get("response") or {}).get("ok")
        ]
        # The official requirement asks for five practical queries. It does not
        # require every grader-chosen parameter combination to return non-empty
        # rows, so 2xx execution is authoritative here. Payload semantics remain
        # supporting evidence only.
        qverdict = (
            "PASS" if qok >= 5 and qcount >= 5
            else "INCONCLUSIVE" if qcount >= 5 and qok > 0
            else "FAIL"
        )
        assertions.append(_assertion("final.queries.runtime", "Practical queries execute successfully",
                                     qverdict,
                                     expected="5 successful query calls",
                                     actual={"http_ok": qok, "called": len(qcalls)},
                                     evidence=[json.dumps(qpayload, ensure_ascii=False)[:3000]]))

        anames = (semantic.get("aggregations") or {}).get("names") or probe.get("aggregation_names") or []
        ameta = semantic.get("aggregations") or {}
        acount = max(len(anames), int(ameta.get("declared_count") or 0))
        assertions.append(_assertion("final.aggregations.count", "At least five aggregation reports are exposed",
                                     "PASS" if acount >= 5 else "FAIL", expected=">= 5", actual=acount,
                                     evidence=[json.dumps(ameta, ensure_ascii=False)[:1800]]))
        acalls = probe.get("aggregation_calls") or []
        aok = sum(1 for x in acalls if (x.get("response") or {}).get("ok"))
        apayload = [
            meaningful_payload((x.get("response") or {}).get("body"))
            for x in acalls if (x.get("response") or {}).get("ok")
        ]
        ameaningful = sum(1 for x in apayload if x.get("supported") is True)
        aambiguous = any(x.get("supported") is None for x in apayload)
        averdict = (
            "PASS" if aok >= 5 and ameaningful >= 5
            else "INCONCLUSIVE" if (acount >= 5 and (aambiguous or aok > 0))
            else "FAIL"
        )
        assertions.append(_assertion("final.aggregations.runtime", "Aggregation reports execute and return actual data",
                                     averdict,
                                     expected="5 successful aggregation calls with actual results",
                                     actual={"http_ok": aok, "meaningful_results": ameaningful, "called": len(acalls)},
                                     evidence=[json.dumps(apayload, ensure_ascii=False)[:3000]]))

        indexes_after = validated.index_information()
        non_id = [(n, spec) for n, spec in indexes_after.items() if n != "_id_"]
        compound = [(n, spec) for n, spec in non_id if len(spec.get("key") or []) >= 2]
        assertions.append(_assertion("final.indexes.count", "Indexes required for Phase 2 exist",
                                     "PASS" if len(non_id) >= 3 else "FAIL",
                                     expected=">= 3 non-_id indexes", actual=len(non_id),
                                     evidence=[json.dumps({k: v.get("key") for k, v in non_id}, ensure_ascii=False)[:2500]]))
        assertions.append(_assertion("final.indexes.compound", "At least one compound index exists",
                                     "PASS" if compound else "FAIL", expected=">= 1 compound index", actual=len(compound),
                                     evidence=[json.dumps({k: v.get("key") for k, v in compound}, ensure_ascii=False)[:1500]]))

        ixscan_hits = 0
        ixscan_evidence = []
        seen_fields = set()
        for name, spec in non_id:
            keys = spec.get("key") or []
            if not keys:
                continue
            field = str(keys[0][0])
            if field == execution_plan.business_key or field in seen_fields:
                continue
            seen_fields.add(field)
            doc = validated.find_one({field: {"$exists": True}})
            if not doc:
                continue
            value = _nested(doc, field)
            if value is None:
                continue
            try:
                exp = db.command("explain", {"find": validated_name, "filter": {field: value}}, verbosity="executionStats")
                if _contains_ixscan(exp):
                    ixscan_hits += 1
                    ixscan_evidence.append(f"{name}: IXSCAN observed for {field}")
            except Exception as exc:
                ixscan_evidence.append(f"{name}: explain error {type(exc).__name__}: {exc}")

        static = final_plan.get("static") or {}
        explain_doc = explain_compliance(repo)
        explain_pass = bool(explain_doc.get("supported") and ixscan_hits >= 1)
        explain_partial = bool(explain_doc.get("supported") or ixscan_hits >= 1)
        assertions.append(_assertion(
            "final.indexes.explain",
            "Three explain/executionStats cases before/after indexes plus rationale/effect are evidenced",
            "PASS" if explain_pass else ("INCONCLUSIVE" if explain_partial else "FAIL"),
            expected={
                "distinct_queries": ">= 3",
                "executionStats": True,
                "before_after": True,
                "index_rationale_effect": True,
                "runtime_index_use": True,
            },
            actual={**explain_doc, "runtime_ixscan_hits": ixscan_hits},
            evidence=ixscan_evidence + [json.dumps(explain_doc, ensure_ascii=False)[:2200]],
        ))

        mv1 = probe.get("refresh_mv_first") or {}
        mv2 = probe.get("refresh_mv_second") or {}
        assertions.append(_assertion("final.mv.refresh", "Materialized-view refresh endpoint works",
                                     "PASS" if mv1.get("ok") else "FAIL", expected="2xx", actual=mv1.get("status"),
                                     evidence=[json.dumps(mv1.get("body"), ensure_ascii=False)[:1800]]))
        collections_after = set(db.list_collection_names())
        mv_names, mv_counts = [], {}
        for name in sorted(collections_after):
            low = name.lower()
            if name in {raw_name, validated_name, quarantine_name}: continue
            if re.search(r"(^mv[_-]|material|summary|view)", low) and not re.search(r"state|contribution|meta", low):
                try: count = db[name].count_documents({})
                except Exception: count = 0
                if count > 0:
                    mv_names.append(name); mv_counts[name] = count
        assertions.append(_assertion("final.mv.collections", "At least two populated materialized-view collections exist",
                                     "PASS" if len(mv_names) >= 2 else "FAIL", expected=">= 2", actual=len(mv_names),
                                     evidence=[json.dumps(mv_counts, ensure_ascii=False)]))
        incremental, inc_ev = _second_refresh_incremental(probe)
        assertions.append(_assertion("final.mv.incremental", "Second materialized-view refresh is incremental/idempotent",
                                     "PASS" if incremental else ("INCONCLUSIVE" if mv2.get("ok") else "FAIL"),
                                     expected="incremental or zero-change second refresh",
                                     actual=json.dumps(mv2.get("body"), ensure_ascii=False)[:1200], evidence=inc_ev))

        jnames = (semantic.get("jobs") or {}).get("names") or probe.get("job_names") or []
        jmeta = semantic.get("jobs") or {}
        jcount = max(len(jnames), int(jmeta.get("declared_count") or 0))
        assertions.append(_assertion("final.jobs.count", "At least two scheduled jobs are exposed",
                                     "PASS" if jcount >= 2 else "FAIL", expected=">= 2", actual=jcount,
                                     evidence=[json.dumps(jmeta, ensure_ascii=False)[:1800]]))
        jcalls = probe.get("job_calls") or []
        jok = sum(1 for x in jcalls if (x.get("response") or {}).get("ok"))
        assertions.append(_assertion("final.jobs.manual_run", "Scheduled jobs support manual execution",
                                     "PASS" if jok >= 2 else ("INCONCLUSIVE" if jcount >= 2 else "FAIL"),
                                     expected="2 successful manual runs", actual=f"{jok}/{len(jcalls)}",
                                     evidence=[json.dumps(jcalls, ensure_ascii=False)[:2500]]))
        jobs_body = (probe.get("jobs") or {}).get("body")
        jobs_txt = json.dumps(jobs_body, ensure_ascii=False).lower()
        schedule_evident = any(x in jobs_txt for x in ["schedule", "cron", "interval", "minute", "hour", "daily", "next_run"])
        assertions.append(_assertion("final.jobs.schedule", "Job schedules are visible/configured",
                                     "PASS" if schedule_evident else ("INCONCLUSIVE" if jnames else "FAIL"),
                                     expected=True, actual=schedule_evident,
                                     evidence=[json.dumps(jobs_body, ensure_ascii=False)[:1800]]))
        job_log_names = []
        job_log_values = []
        for call in jcalls:
            response = call.get("response") or {}
            if response.get("body") is not None:
                job_log_values.append(response.get("body"))
        jobs_after_runs = probe.get("jobs_after_runs") or {}
        if jobs_after_runs.get("body") is not None:
            job_log_values.append(jobs_after_runs.get("body"))
        for name in sorted(collections_after):
            if re.search(r"job.*log|log.*job|execution.*log|run.*log", name.lower()):
                try:
                    docs = list(db[name].find({}, {"_id": 0}).sort([("_id", -1)]).limit(10))
                    if docs:
                        job_log_names.append(name)
                        job_log_values.extend(docs)
                except Exception:
                    pass
        job_logging = job_log_compliance(job_log_values)
        assertions.append(_assertion(
            "final.jobs.logging",
            "Job execution logs include start time, end time, status, and result",
            "PASS" if job_logging.get("supported") else ("INCONCLUSIVE" if jcount >= 2 else "FAIL"),
            expected={"start_time": True, "end_time": True, "status": True, "result": True},
            actual=job_logging,
            evidence=[json.dumps({"collections": job_log_names, "normalization": job_logging}, ensure_ascii=False)[:2500]],
        ))

        readme_evidence = readme_contract(repo)
        readme_ok = bool(static.get("has_readme"))
        readme_topics_ok = (
            readme_evidence.get("covered_topics") == readme_evidence.get("required_topics")
        )
        github_readme_pass = bool(
            readme_ok
            and readme_topics_ok
            and readme_evidence.get("requirements")
            and readme_evidence.get("env_example")
        )
        assertions.append(_assertion(
            "final.github_readme",
            "README documents installation, execution, API, queries, indexes/Explain, aggregations, materialized views, and jobs",
            "PASS" if github_readme_pass else ("INCONCLUSIVE" if readme_ok else "FAIL"),
            expected={
                "all_required_topics": True,
                "requirements.txt": True,
                ".env.example_or_example.env": True,
            },
            actual=readme_evidence,
            evidence=[json.dumps(readme_evidence, ensure_ascii=False)[:3000]],
        ))
        deps_ok = bool(
            static.get("has_requirements")
            and static.get("fastapi_declared")
            and static.get("uvicorn_declared")
            and static.get("has_env_example")
        )
        assertions.append(_assertion(
            "final.dependencies",
            "Final API dependencies and environment example are declared",
            "PASS" if deps_ok else "FAIL",
            expected="requirements include FastAPI/Uvicorn and .env.example (or example.env) exists",
            actual={
                "requirements": static.get("has_requirements"),
                "fastapi": static.get("fastapi_declared"),
                "uvicorn": static.get("uvicorn_declared"),
                "env_example": static.get("has_env_example"),
            },
        ))

        assertions.append(_assertion("final.discussion", "Discussion / understanding", "INCONCLUSIVE",
                                     expected="Manual viva", actual="Not automated",
                                     note="0.25 remains manual and is not auto-scored."))

        host_evidence.update({
            "database": db_name, "validated_collection": validated_name,
            "active_database_resolution": host_evidence.get("active_database_resolution"),
            "indexes_before": indexes_before, "indexes_after": indexes_after,
            "collections_before": sorted(collections_before), "collections_after": sorted(collections_after),
            "mv_counts": mv_counts, "job_log_collections": job_log_names,
        })
        client.close()

    except Exception as exc:
        assertions.append(_assertion("final.runtime.exception", "Final runtime suite", "ERROR",
                                     expected="suite completes", actual=f"{type(exc).__name__}: {exc}"))
    finally:
        if not keep_sandbox:
            sb.cleanup()

    counts = {k: 0 for k in ["PASS", "FAIL", "INCONCLUSIVE", "ERROR"]}
    for a in assertions:
        if a["verdict"] in counts: counts[a["verdict"]] += 1
    status = "COMPLETED_WITH_ERRORS" if counts["ERROR"] else ("COMPLETED_WITH_FAILURES" if counts["FAIL"] else "COMPLETED")
    return {
        "status": status, "runtime_ready": True, "assertions": assertions, "assertion_counts": counts, "probe": probe,
        "service_run": {
            "returncode": service_run.get("returncode"), "elapsed_seconds": service_run.get("elapsed_seconds"),
            "timed_out": service_run.get("timed_out"),
            "stdout_tail": str(service_run.get("stdout") or "")[-7000:],
            "stderr_tail": str(service_run.get("stderr") or "")[-5000:],
        },
        "host_evidence": host_evidence, "sandbox": sb.metadata(),
    }
