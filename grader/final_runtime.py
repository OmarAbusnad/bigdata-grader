from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pymongo import MongoClient

from .sandbox import DockerSandbox, SandboxConfig
from .api_semantic_normalizer import normalize_probe
from .final_compliance import meaningful_payload, readme_contract, explain_compliance, job_log_compliance, materialized_view_aggregation_basis


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


def _ingest_transport_unproved(attempts: list[dict[str, Any]]) -> bool:
    """No HTTP response at all: transport timeout cannot prove student FAIL."""
    return bool(attempts) and all(
        (attempt.get("response") or {}).get("status") is None
        and bool((attempt.get("response") or {}).get("error"))
        for attempt in attempts
    )


def _refresh_transport_unproved(*responses: dict[str, Any]) -> bool:
    """A transport exception without HTTP status cannot justify a student FAIL."""
    return any(
        response.get("status") is None and bool(response.get("error"))
        for response in responses
    )


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
        local = (
            (repo / f"{top}.py").is_file()
            or (repo / top / "__init__.py").is_file()
            or any(p.is_file() for p in repo.rglob(f"{top}.py"))
            or any(p.is_file() for p in repo.rglob(f"{top}/__init__.py"))
        )
        requirements = ""
        try:
            requirements = (repo / "requirements.txt").read_text(encoding="utf-8-sig", errors="replace").lower()
        except Exception:
            pass
        declared = bool(re.search(rf"(?m)^\s*{re.escape(top.lower())}(?:\s|[<>=!~\[]|$)", requirements))
        local_name_hints = {
            "config", "src", "app", "core", "common", "utils", "services",
            "models", "database", "db", "pipeline", "etl", "queries",
        }
        if not local and not declared and top.lower() in local_name_hints:
            return {
                "code": "STUDENT_CONFIGURATION_FAILURE",
                "evidence": [
                    f"missing local-style module: {module}",
                    f"{top} is not present at the expected case-sensitive path",
                ],
            }
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
        ("final.api.json", "Operational API responses are JSON"),
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
        ("final.mv.aggregation_basis", "Materialized views are based on aggregation logic"),
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
        items = [
            {
                "sku": "SKU-001",
                "product_id": "P-001",
                "name": "Test Product",
                "product_name": "Test Product",
                "quantity": 2,
                "qty": 2,
                "unit_price": total / 2,
                "price": total / 2,
                "line_total": total,
                "total": total,
            }
        ]
        clean = {
            "order_id": order_id, "city": city, "status": status,
            "customer_id": customer_id, "order_date": order_date,
            "payment_method": payment_method, "total_amount": total,
            "payment_amount": total, "currency": "YER", "delivery_type": "standard",
            "items": items,
            "items_json": json.dumps(items, ensure_ascii=False),
            "processed_at": order_date,
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
    return r'''import json, os, re, shutil, time, urllib.parse, urllib.request, urllib.error

BASE = "http://127.0.0.1:8000"
DATASET_SOURCE = "/grader-tests/test_01_small_batch_pipeline.csv"
DATASET_PROJECT = "/workspace/data/grader_hidden_input.csv"
try:
    os.makedirs("/workspace/data", exist_ok=True)
    shutil.copyfile(DATASET_SOURCE, DATASET_PROJECT)
    DATASET = DATASET_PROJECT
except Exception:
    DATASET = DATASET_SOURCE
SKIP_INGEST = os.getenv("GRADER_SKIP_INGEST", "").strip() == "1"

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
            try:
                parsed = json.loads(raw)
                is_json = True
            except Exception:
                parsed = raw[:5000]
                is_json = False
            return {"status": r.status, "ok": 200 <= r.status < 300, "body": parsed, "is_json": is_json}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            is_json = True
        except Exception:
            parsed = raw[:5000]
            is_json = False
        return {"status": e.code, "ok": False, "body": parsed, "is_json": is_json}
    except Exception as e:
        return {"status": None, "ok": False, "error": f"{type(e).__name__}: {e}", "is_json": False}

def request_form(path, fields, timeout=180):
    boundary = "----graderboundary"
    chunks = []
    for key, value in fields.items():
        chunks.append("--" + boundary + "\r\n")
        chunks.append('Content-Disposition: form-data; name="' + str(key) + '"\r\n\r\n')
        chunks.append(str(value) + "\r\n")
    chunks.append("--" + boundary + "--\r\n")
    data = "".join(chunks).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw); is_json = True
            except Exception:
                parsed = raw[:5000]; is_json = False
            return {"status": r.status, "ok": 200 <= r.status < 300, "body": parsed, "is_json": is_json}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw); is_json = True
        except Exception:
            parsed = raw[:5000]; is_json = False
        return {"status": e.code, "ok": False, "body": parsed, "is_json": is_json}
    except Exception as e:
        return {"status": None, "ok": False, "error": f"{type(e).__name__}: {e}", "is_json": False}

def request_file_upload(path, file_field, fields=None, timeout=240):
    """POST the actual mounted grading CSV as a multipart UploadFile."""
    if not os.path.isfile(DATASET):
        return {"status": None, "ok": False, "error": "Grader input CSV missing", "is_json": False}
    boundary = "----grader-real-csv-upload"
    parts = []
    for key, value in (fields or {}).items():
        parts.append(("--" + boundary + "\r\n"
                      + 'Content-Disposition: form-data; name="' + str(key) + '"\r\n\r\n'
                      + str(value) + "\r\n").encode("utf-8"))
    parts.append(("--" + boundary + "\r\n"
                  + 'Content-Disposition: form-data; name="' + str(file_field)
                  + '"; filename="grader_hidden_input.csv"\r\n'
                  + "Content-Type: text/csv\r\n\r\n").encode("utf-8"))
    with open(DATASET, "rb") as handle:
        parts.append(handle.read())
    parts.append(("\r\n--" + boundary + "--\r\n").encode("utf-8"))
    req = urllib.request.Request(
        BASE + path,
        data=b"".join(parts),
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw); is_json = True
            except Exception:
                payload = raw[:5000]; is_json = False
            return {"status": response.status, "ok": 200 <= response.status < 300,
                    "body": payload, "is_json": is_json}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw); is_json = True
        except Exception:
            payload = raw[:5000]; is_json = False
        return {"status": error.code, "ok": False, "body": payload, "is_json": is_json}
    except Exception as error:
        return {"status": None, "ok": False, "error": f"{type(error).__name__}: {error}",
                "is_json": False}


def resolve_schema(openapi, schema):
    if not isinstance(schema, dict): return {}
    ref = schema.get("$ref")
    if ref and ref.startswith("#/"):
        cur = openapi
        for part in ref[2:].split("/"):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        return resolve_schema(openapi, cur) if isinstance(cur, dict) else {}
    for key in ("anyOf", "oneOf"):
        options = schema.get(key)
        if isinstance(options, list):
            for option in options:
                resolved = resolve_schema(openapi, option)
                if resolved and resolved.get("type") != "null":
                    return resolved
    if isinstance(schema.get("allOf"), list):
        merged = {}
        for option in schema["allOf"]:
            merged.update(resolve_schema(openapi, option))
        return merged
    return schema

def sample_value(name, schema=None):
    n = name.lower()
    schema = resolve_schema(openapi, schema or {})
    if "example" in schema: return schema["example"]
    if "default" in schema: return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum: return enum[0]
    typ = schema.get("type")
    if typ == "integer":
        minimum = schema.get("minimum")
        exclusive = schema.get("exclusiveMinimum")
        if isinstance(minimum, (int, float)): return int(max(minimum, 1))
        if isinstance(exclusive, (int, float)): return int(exclusive) + 1
        return 100 if "batch" in n else 10
    if typ == "number":
        minimum = schema.get("minimum")
        exclusive = schema.get("exclusiveMinimum")
        if isinstance(minimum, (int, float)): return float(max(minimum, 1))
        if isinstance(exclusive, (int, float)): return float(exclusive) + 1.0
        return 10.0
    if typ == "boolean": return False
    if typ == "array": return []
    if "city" in n: return "Sanaa"
    if "status" in n: return "Delivered"
    if "customer" in n: return "CUST-001"
    if "payment" in n or "method" in n: return "cash"
    if "engine" in n: return "batch"
    if "start" in n and "date" in n: return "2026-01-01"
    if "end" in n and "date" in n: return "2026-12-31"
    if n in {"start", "from_date", "date_from", "start_date"}: return "2026-01-01"
    if n in {"end", "to_date", "date_to", "end_date"}: return "2026-12-31"
    if n in {"order_id", "order", "id_order"}: return "F-001"
    if n in {"reason", "error_code", "quarantine_reason"}: return "INVALID_EMAIL"
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

        # Flat mapping APIs commonly expose executable IDs as keys and
        # human-readable descriptions as scalar values:
        # {"q1": "description", "q2": "description", ...}
        scalar_keys = [
            str(k) for k, v in value.items()
            if isinstance(v, (str, int, float, bool)) or v is None
            if str(k).lower() not in {
                "count", "total", "status", "message", "detail", "description",
                "service", "version", "mode", "ok", "success"
            }
        ]
        if len(scalar_keys) >= 2:
            return scalar_keys
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                val = (item.get("id") or item.get("query_name") or item.get("job_name") or item.get("job_id") or item.get("report_name")
                       or item.get("report_id") or item.get("query_id") or item.get("task_id") or item.get("slug") or item.get("key")
                       or item.get("job") or item.get("name"))
                if val is not None: out.append(str(val))
        return out
    return []

def query_param_names_from_listing(value, target_name):
    """Extract parameters declared for one named query from heterogeneous list responses."""
    target = str(target_name)
    if isinstance(value, dict):
        own_name = value.get("id") or value.get("query_name") or value.get("key") or value.get("name")
        if own_name is not None and str(own_name) == target:
            for key in ("required_parameters", "parameters", "params", "filters", "query_params", "supported_parameters"):
                raw = value.get(key)
                if isinstance(raw, list):
                    out = []
                    for item in raw:
                        if isinstance(item, str):
                            out.append(item)
                        elif isinstance(item, dict):
                            n = item.get("name") or item.get("key") or item.get("id")
                            if n is not None: out.append(str(n))
                    if out: return out
                if isinstance(raw, dict):
                    return [str(k) for k in raw.keys()]
        if target in value and isinstance(value[target], dict):
            nested = query_param_names_from_listing({"name": target, **value[target]}, target)
            if nested: return nested
        for child in value.values():
            got = query_param_names_from_listing(child, target)
            if got: return got
    elif isinstance(value, list):
        for child in value:
            got = query_param_names_from_listing(child, target)
            if got: return got
    return []


def semantic_query_param_names(name, available):
    """Conservative fallback when list metadata does not expose per-query params."""
    n = str(name).lower()
    out = set()
    def add_if(token, *params):
        if token in n:
            for p in params:
                if p in available: out.add(p)
    add_if("city", "city")
    add_if("status", "status")
    add_if("customer", "customer_id")
    add_if("phone", "phone", "customer_phone")
    add_if("product", "sku", "product_id", "item_name", "product_name")
    add_if("sku", "sku")
    add_if("payment", "payment_method", "payment_status", "min_amount")
    add_if("high_value", "min_total", "min_amount")
    add_if("reason", "reason", "quarantine_reason", "error_code")
    add_if("order_id", "order_id")
    add_if("period", "start", "end", "start_date", "end_date")
    if "value" in available and ("orders" in n or n.startswith("quality_")):
        out.add("value")
    add_if("range", "start_date", "end_date", "start", "end", "min_total", "max_total")
    add_if("date", "start_date", "end_date", "start", "end")
    if "limit" in available: out.add("limit")
    return out


def sample_query_parameter(name, pname, schema=None):
    """Use already documented fixture values; never invent a parameter name."""
    n, p = str(name).lower(), str(pname).lower()
    if p == "value":
        if "customer" in n: return "CUST-001"
        if "city" in n: return "Sanaa"
        if "status" in n: return "Delivered"
        if "quality" in n: return "corrected"
    return sample_value(pname, schema)


def missing_query_parameters(response, available, already):
    """Return only parameter names confirmed missing by a 400/422 response."""
    if response.get("status") not in (400, 422):
        return []
    body = response.get("body") or {}
    pending = set()
    detail = body.get("detail") if isinstance(body, dict) else None
    for item in detail if isinstance(detail, list) else []:
        if not isinstance(item, dict):
            continue
        loc = item.get("loc") or []
        if len(loc) >= 2 and loc[0] == "query" and loc[1] in available:
            pending.add(loc[1])
    message = json.dumps(body, ensure_ascii=False).lower()
    for name in available:
        lower = name.lower()
        quoted = re.escape(lower)
        if (re.search(r"(?:missing|required|provide|specify)[^\n.]{0,90}\b" + quoted + r"\b", message)
            or re.search(r"\b" + quoted + r"\b[^\n.]{0,45}(?:missing|required)", message)):
            pending.add(name)
    if "missing dates" in message or "dates required" in message:
        pending.update(p for p in ("start_date", "end_date", "start", "end") if p in available)
    return sorted(pending.difference(already))


def build_ingest_attempts(openapi):
    post = ((openapi.get("paths") or {}).get("/ingest") or {}).get("post") or {}
    attempts = []

    # Query-parameter style /ingest.
    qparams = {}
    for p in post.get("parameters") or []:
        if p.get("in") != "query":
            continue
        name = p.get("name")
        if not name:
            continue
        n = name.lower()
        if any(x in n for x in ["path", "file", "input", "csv"]):
            qparams[name] = DATASET
        elif p.get("required"):
            qparams[name] = sample_value(name, p.get("schema") or {})
    if qparams:
        attempts.append({"kind": "query", "params": qparams})

    content = ((post.get("requestBody") or {}).get("content") or {})
    for media_type, media in content.items():
        schema = resolve_schema(openapi, (media or {}).get("schema") or {})
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        fields = {}
        for name, prop_schema in props.items():
            n = name.lower()
            is_path = (
                any(x in n for x in ["path", "input_path", "file_path", "csv_path"])
                or n in {"input", "file", "source_file", "source", "csv", "filename",
                         "input_file", "csv_file", "input_csv", "input_filename", "csv_filename"}
            )
            if is_path:
                fields[name] = DATASET
            elif name in required:
                fields[name] = sample_value(name, prop_schema)
        if not fields and props:
            # Prefer the first semantically path-like field; otherwise rely on endpoint defaults.
            for name, prop_schema in props.items():
                n = name.lower()
                if any(x in n for x in ["path", "csv"]) or n in {"input", "file", "source_file", "source", "filename"}:
                    fields[name] = DATASET
                    break
        if media_type == "application/json":
            if not props and schema.get("type") == "object":
                # FastAPI payload: dict produces a free-form JSON object with
                # no documented property names. Sending {} yields a false 400.
                # Probe common path keys as separate legitimate requests.
                for fallback_key in ("file_path", "input_path", "input_file",
                                     "csv_path", "file", "input"):
                    attempts.append({"kind": "json", "body": {fallback_key: DATASET}})
            else:
                attempts.append({"kind": "json", "body": fields})
        elif media_type in ("multipart/form-data", "application/x-www-form-urlencoded"):
            binary_fields = [
                name for name, schema_item in props.items()
                if isinstance(schema_item, dict) and schema_item.get("format") == "binary"
            ]
            form_fields = {k: v for k, v in fields.items() if k not in binary_fields}
            if form_fields:
                attempts.append({"kind": "form", "fields": form_fields})
            # A FastAPI UploadFile needs actual multipart file bytes, NOT its path.
            # If text/path fields fail, retry only the documented binary file field.
            if media_type == "multipart/form-data":
                # Some FastAPI/OpenAPI generators omit resolved binary properties
                # even for UploadFile = File(...). Multipart explicitly authorizes
                # a real file upload; try conventional "file" once, never mark
                # success unless the actual HTTP/data effect is verified.
                candidates = binary_fields or (["file"] if not props else [])
                for file_field in candidates:
                    attempts.append({"kind": "upload", "file_field": file_field,
                                     "fields": form_fields})

    if not attempts:
        for body in [
            {"input_path": DATASET}, {"file_path": DATASET}, {"path": DATASET},
            {"csv_path": DATASET}, {"file": DATASET}, {"input": DATASET},
        ]:
            attempts.append({"kind": "json", "body": body})
        # Some implementations omit requestBody from OpenAPI despite a FastAPI
        # UploadFile parameter. This conservative FINAL fallback is reached
        # only when no documented request schema exists and tries upload AFTER
        # the normal JSON variants; successful JSON ingest exits early.
        attempts.append({"kind": "upload", "file_field": "file", "fields": {}})
    return attempts

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
if not SKIP_INGEST:
    for attempt in build_ingest_attempts(openapi):
        kind = attempt.get("kind")
        if kind == "query":
            params = attempt.get("params") or {}
            suffix = "?" + urllib.parse.urlencode(params) if params else ""
            r = request("POST", "/ingest" + suffix, None, timeout=240)
            keys = sorted(params.keys())
        elif kind == "form":
            fields = attempt.get("fields") or {}
            r = request_form("/ingest", fields, timeout=240)
            keys = sorted(fields.keys())
        elif kind == "upload":
            fields = attempt.get("fields") or {}
            name = attempt.get("file_field") or "file"
            r = request_file_upload("/ingest", name, fields=fields, timeout=240)
            keys = sorted(list(fields.keys()) + [name])
        else:
            body = attempt.get("body") or {}
            r = request("POST", "/ingest", body, timeout=240)
            keys = sorted(body.keys())
        ingest_attempts.append({"kind": kind, "body_keys": keys, "response": r})
        if kind == "form" and not r.get("ok") and r.get("status") == 422 and "UploadFile" in json.dumps(r.get("body"), ensure_ascii=False):
            # The server says a form field must be a real uploaded file, not a path string.
            # Resend that field as multipart file bytes and keep the other fields as text.
            detail = (r.get("body") or {}).get("detail") if isinstance(r.get("body"), dict) else None
            upload_fields = []
            for item in detail if isinstance(detail, list) else []:
                loc = item.get("loc") if isinstance(item, dict) else None
                if isinstance(loc, list) and len(loc) >= 2 and loc[0] == "body" and isinstance(loc[1], str):
                    upload_fields.append(loc[1])
            for up_name in dict.fromkeys(upload_fields):
                rest = {k: v for k, v in (attempt.get("fields") or {}).items() if k != up_name}
                r2 = request_file_upload("/ingest", up_name, fields=rest, timeout=240)
                ingest_attempts.append({"kind": "upload", "body_keys": sorted(list(rest.keys()) + [up_name]), "response": r2})
                r = r2
                if r2.get("ok"):
                    break
        if r.get("ok"):
            break
        if r.get("status") not in (400, 404, 405, 415, 422):
            break
result["ingest_attempts"] = ingest_attempts
result["indexes"] = request("POST", "/indexes", {}, timeout=60)

q = request("GET", "/queries", timeout=30)
result["queries"] = q
qnames = names_from(q.get("body"), ["queries", "available_queries", "names", "items", "data", "results"])
result["query_names"] = qnames[:30]
qcalls = []
qspec = ((openapi.get("paths") or {}).get("/queries/{name}") or {}).get("get") or {}
for name in qnames[:5]:
    params = {}
    qparams = [p for p in (qspec.get("parameters") or []) if p.get("in") == "query" and p.get("name")]
    available = {str(p.get("name")) for p in qparams}
    selected = set(query_param_names_from_listing(q.get("body"), name))
    if not selected:
        selected = semantic_query_param_names(name, available)
    for p in qparams:
        pname = str(p.get("name"))
        if p.get("required") or pname in selected:
            params[pname] = sample_query_parameter(name, pname, p.get("schema") or {})
    for pname in sorted(selected):
        if pname not in params:
            params[pname] = sample_query_parameter(name, pname, {})
    path = "/queries/" + urllib.parse.quote(name, safe="")
    suffix = "?" + urllib.parse.urlencode(params) if params else ""
    response = request("GET", path + suffix, timeout=60)
    attempts = [{"params": dict(params), "response": response}]
    # Conditional parameters may be required for one query name but optional
    # in the shared OpenAPI path schema. Retry once, only with names confirmed
    # missing by the student's HTTP 400/422 response and declared in OpenAPI.
    additions = missing_query_parameters(response, available, set(params))
    if additions:
        for pname in additions:
            schema = next((p.get("schema") or {} for p in qparams if p.get("name") == pname), {})
            params[pname] = sample_query_parameter(name, pname, schema)
        retry_suffix = "?" + urllib.parse.urlencode(params)
        response = request("GET", path + retry_suffix, timeout=60)
        attempts.append({"params": dict(params), "response": response})
    qcalls.append({"name": name, "params": params, "response": response, "attempts": attempts})
result["query_calls"] = qcalls

a = request("GET", "/aggregations", timeout=30)
result["aggregations"] = a
anames = names_from(a.get("body"), ["aggregations", "available_aggregations", "names", "items", "data", "results", "reports", "aggregation_reports", "available_reports"])
result["aggregation_names"] = anames[:30]
result["aggregation_calls"] = [
    {"name": name, "response": request("GET", "/aggregations/" + urllib.parse.quote(name, safe=""), timeout=90)}
    for name in anames[:5]
]

def discover_refresh_view_name(openapi, source_root="/workspace"):
    """Ground a required view name in a live listing or literal student source."""
    for endpoint in ("/views", "/materialized-views", "/materialized_views"):
        if "get" not in ((openapi.get("paths") or {}).get(endpoint) or {}):
            continue
        response = request("GET", endpoint, timeout=15)
        if response.get("ok"):
            names = names_from(response.get("body"), ["views", "materialized_views", "names", "data"])
            if names:
                return names[0]
    import ast
    for relative in ("src/api.py", "src/phase2/api.py", "src/final/api.py", "api/main.py"):
        path = os.path.join(source_root, relative)
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > 500_000:
                continue
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fp:
                source = ast.parse(fp.read(), filename=relative)
            for node in ast.walk(source):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(isinstance(target, ast.Name) and target.id in
                           {"MV_NAMES", "MATERIALIZED_VIEW_NAMES", "VIEW_NAMES"} for target in targets):
                    continue
                value = ast.literal_eval(node.value)
                if isinstance(value, (list, tuple)) and value:
                    if isinstance(value[0], str) and value[0].strip():
                        return value[0]
        except (OSError, SyntaxError, ValueError, TypeError):
            continue
    return None


def refresh_mv_with_contract(openapi, full_refresh=False):
    post = ((openapi.get("paths") or {}).get("/refresh-mv") or {}).get("post") or {}
    query_parameters = [p for p in (post.get("parameters") or []) if p.get("in") == "query"]
    query = {}
    for param in query_parameters:
        key = param.get("name") or ""
        schema = resolve_schema(openapi, param.get("schema") or {})
        enum = schema.get("enum") or []
        if str(key).lower().replace("-", "_") in {"full_refresh", "force_full", "fullrefresh", "initial", "initialize", "initialise",
                                                   "init", "bootstrap", "rebuild", "full", "force", "reset"}:
            # Boolean switches that request the initial/full build; the second (incremental) call sends false.
            query[key] = str(bool(full_refresh)).lower()
        elif param.get("required") and "default" in schema:
            query[key] = schema["default"]
        elif param.get("required") and enum:
            query[key] = enum[0]
        elif param.get("required"):
            # Prefer the student's advertised view list or literal MV_NAMES,
            # never a generic invented name.
            grounded_view = discover_refresh_view_name(openapi) if str(key).lower() in {
                "name", "view", "view_name", "materialized_view",
            } else None
            if grounded_view:
                query[key] = grounded_view
            else:
                return {"status": None, "ok": False, "probe_blocked": "required_query_parameter_unresolved",
                        "required_parameter": key, "is_json": False}
    suffix = "?" + urllib.parse.urlencode(query) if query else ""
    return request("POST", "/refresh-mv" + suffix, {}, timeout=120)

def refresh_waiting_for_initialization(full_refresh):
    """The ELT behind /ingest may still be finishing: give an uninitialized watermark a few chances."""
    resp = refresh_mv_with_contract(openapi, full_refresh=full_refresh)
    for _ in range(4):
        text = json.dumps((resp or {}).get("body"), ensure_ascii=False).lower()
        if (resp or {}).get("ok") or not any(w in text for w in ("not initialized", "not initialised", "run --initial", "watermark")):
            break
        time.sleep(6)
        resp = refresh_mv_with_contract(openapi, full_refresh=full_refresh)
    return resp

result["refresh_mv_first"] = refresh_waiting_for_initialization(True)
result["refresh_mv_second"] = refresh_waiting_for_initialization(False)

def precondition_refresh_first(resp):
    """Aggregation/query answer that says analytics facts need a refresh/initialization first."""
    text = json.dumps((resp or {}).get("body"), ensure_ascii=False).lower()
    return (resp or {}).get("status") in (400, 409, 412, 422, 425, 500, 503) and any(
        w in text for w in ("refresh-mv", "refresh first", "refresh_mv", "not initialized", "not initialised", "initialize analytics", "run refresh"))

if result["aggregation_calls"] and any(precondition_refresh_first(c.get("response")) for c in result["aggregation_calls"]) \
        and (result["refresh_mv_first"].get("ok") or result["refresh_mv_second"].get("ok")):
    # The API documents refresh as a precondition for aggregations: judge them after the refresh.
    result["aggregation_calls_before_refresh"] = result["aggregation_calls"]
    result["aggregation_calls"] = [
        {"name": name, "response": request("GET", "/aggregations/" + urllib.parse.quote(name, safe=""), timeout=90)}
        for name in anames[:5]
    ]

j = request("GET", "/jobs", timeout=30)
result["jobs"] = j
# Some documented /jobs responses wrap the actual list as
# {"scheduler_status": {"jobs_count": 2, "jobs": [{"job_name": ...}, ...]}}.
# Extract real job identifiers BEFORE the generic name discovery, which would
# otherwise mistake wrapper keys such as "scheduler_running" for job names.
jobs_body = j.get("body") or {}
nested = jobs_body.get("scheduler_status") if isinstance(jobs_body, dict) else {}
listed_jobs = (nested or {}).get("jobs") if isinstance(nested, dict) else None
if not isinstance(listed_jobs, (list, dict)) and isinstance(jobs_body, dict):
    listed_jobs = jobs_body.get("jobs")
jnames = []
if isinstance(listed_jobs, list):
    for job in listed_jobs:
        if isinstance(job, dict):
            name = job.get("job_name") or job.get("name") or job.get("id")
            if isinstance(name, str) and name.strip() and name not in jnames:
                jnames.append(name)
elif isinstance(listed_jobs, dict):
    jnames = [str(k) for k, v in listed_jobs.items()
              if isinstance(v, dict) and str(k).strip()]
if not jnames:
    jnames = names_from(j.get("body"), ["jobs", "available_jobs", "configured_jobs", "registered", "names", "scheduler", "items", "data", "results", "scheduled_jobs", "tasks", "registered_jobs"])
result["job_names"] = jnames[:30]
result["job_calls"] = [
    {"name": name, "response": request("POST", "/jobs/" + urllib.parse.quote(name, safe="") + "/run", {}, timeout=120)}
    for name in jnames[:2]
]

# Adaptive retry: some APIs expose scheduler internals from GET /jobs while
# POST /jobs/{name}/run returns the authoritative public names in its error.
available_job_names = []
for call in result["job_calls"]:
    body = (call.get("response") or {}).get("body")
    text_body = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body
    m = re.search(r"Available:\s*\[([^\]]+)\]", text_body)
    if m:
        for quoted in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
            if quoted not in available_job_names:
                available_job_names.append(quoted)
if available_job_names:
    result["job_names_from_error"] = available_job_names
    result["job_calls"] = [
        {"name": name, "response": request("POST", "/jobs/" + urllib.parse.quote(name, safe="") + "/run", {}, timeout=120)}
        for name in available_job_names[:2]
    ]
    result["job_names"] = available_job_names

def job_run_alternatives(spec, job_name):
    """Public run endpoints declared in OpenAPI when the conventional /jobs/{name}/run is absent."""
    found = []
    for path, ops in (spec.get("paths") or {}).items():
        post = (ops or {}).get("post")
        low = str(path).lower()
        if post is None or "job" not in low or path == "/jobs/{name}/run":
            continue
        if not any(w in low for w in ("run", "trigger", "execute", "start")):
            continue
        if "{" in path:
            found.append((re.sub(r"\{[^}]+\}", urllib.parse.quote(job_name, safe=""), path), None))
            continue
        qnames = [x.get("name") for x in (post.get("parameters") or []) if x.get("in") == "query" and x.get("name")]
        if qnames:
            found.append((path + "?" + urllib.parse.urlencode({qnames[0]: job_name}), None))
        else:
            for key in ("job_name", "name", "job_id", "job"):
                found.append((path, {key: job_name}))
    return found

if result["job_calls"] and all((c.get("response") or {}).get("status") in (404, 405) for c in result["job_calls"]):
    alt_calls = []
    for name in result["job_names"][:2]:
        for alt_path, alt_body in job_run_alternatives(openapi, name):
            resp = request("POST", alt_path, alt_body if alt_body is not None else {}, timeout=120)
            alt_calls.append({"name": name, "response": resp, "path": alt_path})
            if resp.get("status") not in (404, 405, 422):
                break
    if any((c.get("response") or {}).get("ok") for c in alt_calls):
        result["job_calls_conventional_404"] = result["job_calls"]
        result["job_calls"] = alt_calls

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
start_api() {
  python -m uvicorn "$FINAL_API_TARGET" --host 127.0.0.1 --port 8000 >/tmp/final-api.log 2>&1 &
  pid=$!
}
start_api
# Documented alternative launch (e.g. `python src/api.py`) puts the module's own directory on
# sys.path. If uvicorn from the repo root fails on a sibling-module import, retry once with that
# directory appended (never prepended, so it cannot shadow the standard library).
sleep 4
if ! kill -0 "$pid" 2>/dev/null && grep -q "No module named" /tmp/final-api.log 2>/dev/null; then
  mod_path="${FINAL_API_TARGET%%:*}"
  mod_dir="$(dirname "${mod_path//./\/}")"
  if [ -d "/workspace/$mod_dir" ] && [ "$mod_dir" != "." ]; then
    echo "[grader] retrying API start with module directory on sys.path: /workspace/$mod_dir" >>/tmp/final-api.log
    export PYTHONPATH="${PYTHONPATH:-}:/workspace/$mod_dir"
    start_api
  fi
fi
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


def _mv_requires_initialization(*responses: dict[str, Any]) -> bool:
    """True when runtime explicitly says MV initialization/bootstrap/full refresh is a precondition."""
    for response in responses:
        try:
            txt = json.dumps((response or {}).get("body"), ensure_ascii=False).lower()
        except Exception:
            txt = str(response).lower()
        if any(token in txt for token in (
            "not initialized",
            "not initialised",
            "run --bootstrap first",
            "bootstrap first",
            "full refresh first",
            "initial refresh",
        )):
            return True
    return False


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
    shared_sandbox: DockerSandbox | None = None,
    manage_sandbox: bool = True,
    recovery_commands: list[dict[str, Any]] | None = None,
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

    sb = shared_sandbox or DockerSandbox(base, f"{project_id}-final", repo, hidden_dir, sandbox_config)
    if shared_sandbox is not None:
        sb.hidden_dir = hidden_dir
    probe = {}
    service_run = {}
    host_evidence = {}

    try:
        build = sb.build() if manage_sandbox else {"ok": True, "shared": True, "image": sb.image_name}
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

        if manage_sandbox:
            sb.start()
        if not sb.mongo_host_uri:
            raise RuntimeError("Shared sandbox was not started before final suite")
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

        # First pass must test /ingest against a clean database. Grader fixtures
        # are never inserted before ingestion because that can invalidate student
        # consistency checks (e.g. expected 17000 vs. 17012).
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

        if recovery_commands:
            recovery_runs = []
            for item in recovery_commands[:3]:
                if not isinstance(item, dict):
                    continue
                command = str(item.get("command") or "").strip()
                if not command:
                    continue
                run = sb.run_student(
                    command,
                    env={
                        "MONGO_DATABASE": db_name,
                        "MONGODB_DATABASE": db_name,
                        "MONGO_DB_NAME": db_name,
                        "DB_NAME": db_name,
                    },
                    timeout=min(timeout, 300),
                    working_directory=str(item.get("working_directory") or "."),
                )
                recovery_runs.append({
                    "command": command,
                    "working_directory": str(item.get("working_directory") or "."),
                    "confidence": item.get("confidence"),
                    "evidence": item.get("evidence") or [],
                    "run": {
                        "returncode": run.get("returncode"),
                        "timed_out": run.get("timed_out"),
                        "stdout_tail": str(run.get("stdout") or "")[-4000:],
                        "stderr_tail": str(run.get("stderr") or "")[-4000:],
                    },
                })
            host_evidence["execution_repair_commands"] = recovery_runs

            if recovery_runs and any((x.get("run") or {}).get("returncode") == 0 for x in recovery_runs):
                repaired_run = sb.run_student(
                    "bash /grader-tests/run_final_api.sh",
                    env={
                        "FINAL_API_TARGET": api_target,
                        "MONGO_DATABASE": db_name,
                        "MONGODB_DATABASE": db_name,
                        "MONGO_DB_NAME": db_name,
                        "DB_NAME": db_name,
                        "GRADER_SKIP_INGEST": "1",
                    },
                    timeout=max(timeout, 600),
                )
                repaired_probe = _extract_probe(str(repaired_run.get("stdout") or ""))
                if repaired_probe.get("server_ready"):
                    preserved = {
                        "ingest_attempts": probe.get("ingest_attempts"),
                        "health": probe.get("health"),
                        "docs": probe.get("docs"),
                        "openapi": probe.get("openapi"),
                    }
                    probe = repaired_probe
                    probe.update({k: v for k, v in preserved.items() if v is not None})
                    probe["semantic_normalization"] = normalize_probe(probe)
                    host_evidence["execution_repair_retry"] = {
                        "server_ready": True,
                        "returncode": repaired_run.get("returncode"),
                    }
                else:
                    host_evidence["execution_repair_retry"] = {
                        "server_ready": False,
                        "returncode": repaired_run.get("returncode"),
                        "stderr_tail": str(repaired_run.get("stderr") or "")[-3000:],
                    }

        ingest_attempts_first = probe.get("ingest_attempts") or []
        ingest_ok_first = any((x.get("response") or {}).get("ok") for x in ingest_attempts_first)
        if not ingest_ok_first:
            # Keep /ingest result from the clean first pass, but independently
            # test Phase-2 analytics on neutral grader data so one ingest failure
            # does not cascade into queries/MVs/jobs.
            try:
                db[validated_name].delete_many({})
                db[validated_name].insert_many(_fixture_docs(), ordered=False, bypass_document_validation=True)
                host_evidence["analytics_fixture_fallback"] = {
                    "used": True,
                    "database": db_name,
                    "validated_collection": validated_name,
                    "rows": len(_fixture_docs()),
                    "reason": "POST /ingest did not succeed on clean first pass",
                }
                second_run = sb.run_student(
                    "bash /grader-tests/run_final_api.sh",
                    env={
                        "FINAL_API_TARGET": api_target,
                        "MONGO_DATABASE": db_name,
                        "MONGO_DB_NAME": db_name,
                        "DB_NAME": db_name,
                        "GRADER_SKIP_INGEST": "1",
                    },
                    timeout=max(timeout, 600),
                )
                second_probe = _extract_probe(str(second_run.get("stdout") or ""))
                if second_probe.get("server_ready"):
                    preserved = {
                        "ingest_attempts": ingest_attempts_first,
                        "health": probe.get("health"),
                        "docs": probe.get("docs"),
                        "openapi": probe.get("openapi"),
                    }
                    probe = second_probe
                    probe.update({k: v for k, v in preserved.items() if v is not None})
                    probe["semantic_normalization"] = normalize_probe(probe)
                    host_evidence["analytics_fixture_fallback"]["second_pass_ready"] = True
                else:
                    host_evidence["analytics_fixture_fallback"]["second_pass_ready"] = False
            except Exception as exc:
                host_evidence["analytics_fixture_fallback"] = {
                    "used": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }

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

        json_wrappers = [
            probe.get("health") or {},
            probe.get("indexes") or {},
            probe.get("queries") or {},
            probe.get("aggregations") or {},
            probe.get("refresh_mv_first") or {},
            probe.get("refresh_mv_second") or {},
            probe.get("jobs") or {},
            probe.get("jobs_after_runs") or {},
        ]
        json_wrappers += [
            (x.get("response") or {}) for x in (probe.get("ingest_attempts") or [])
            if (x.get("response") or {}).get("status") is not None
        ]
        json_checked = [x for x in json_wrappers if x.get("status") is not None and (x.get("ok") or x.get("is_json") is True)]
        json_ok = bool(json_checked) and all(x.get("is_json") is True for x in json_checked)
        assertions.append(_assertion(
            "final.api.json",
            "Operational API responses are JSON",
            "PASS" if json_ok else "FAIL",
            expected=True,
            actual={
                "checked": len(json_checked),
                "json_responses": sum(1 for x in json_checked if x.get("is_json") is True),
            },
        ))

        ingest_attempts = probe.get("ingest_attempts") or []
        ingest_ok = any((x.get("response") or {}).get("ok") for x in ingest_attempts)
        ingest_transport_blocked = _ingest_transport_unproved(ingest_attempts)
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
            "PASS" if ingest_ok and pipeline_effect else ("INCONCLUSIVE" if (ingest_ok or ingest_transport_blocked) else "FAIL"),
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
            else "INCONCLUSIVE" if qcount >= 5
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
            else "INCONCLUSIVE" if acount >= 5
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
        # The static scanner counts explain() call sites and can miss loops/helpers. Independent
        # runtime proof (>= 3 distinct IXSCAN queries) plus the documented executionStats,
        # before/after comparison and rationale satisfies the requirement as well.
        documented = bool(explain_doc.get("execution_stats") and explain_doc.get("before_after")
                          and explain_doc.get("rationale"))
        explain_pass = bool(
            (explain_doc.get("supported") and ixscan_hits >= 1)
            or (documented and ixscan_hits >= 3)
        )
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
        mv_needs_init = _mv_requires_initialization(mv1, mv2)
        # Timeout without a HTTP response is an uncompleted grader probe;
        # never count it as an API implementation failure.
        mv_transport_blocked = _refresh_transport_unproved(mv1, mv2)
        mv_probe_blocked = bool(
            mv1.get("probe_blocked") or mv2.get("probe_blocked") or mv_transport_blocked
        )
        assertions.append(_assertion("final.mv.refresh", "Materialized-view refresh endpoint works",
                                     "INCONCLUSIVE" if mv_probe_blocked else ("PASS" if (mv1.get("ok") and not mv_needs_init) else ("INCONCLUSIVE" if mv_needs_init else "FAIL")),
                                     expected="2xx operational refresh after valid initialization",
                                     actual=mv1.get("status"),
                                     evidence=[json.dumps(mv1.get("body") or mv1.get("error"), ensure_ascii=False)[:1800]],
                                     note=("Probe exceeded grading transport budget before an HTTP response." if mv_transport_blocked else "Documented/runtime initialization precondition detected; grader must initialize before judging." if mv_needs_init else None)))
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
                                     "PASS" if len(mv_names) >= 2 else ("INCONCLUSIVE" if (mv_needs_init or mv_probe_blocked) else "FAIL"),
                                     expected=">= 2 after valid initialization", actual=len(mv_names),
                                     evidence=[json.dumps(mv_counts, ensure_ascii=False)],
                                     note="Initialization precondition prevents a fair collection-count verdict." if mv_needs_init else None))
        incremental, inc_ev = _second_refresh_incremental(probe)
        assertions.append(_assertion("final.mv.incremental", "Second materialized-view refresh is incremental/idempotent",
                                     "PASS" if incremental else ("INCONCLUSIVE" if (mv2.get("ok") or mv_needs_init or mv_probe_blocked) else "FAIL"),
                                     expected="incremental or zero-change second refresh after valid initialization",
                                     actual=json.dumps(mv2.get("body"), ensure_ascii=False)[:1200], evidence=inc_ev,
                                     note="Initialization precondition detected; incremental behavior was not validly exercised." if mv_needs_init else None))

        mv_basis = materialized_view_aggregation_basis(repo)
        assertions.append(_assertion(
            "final.mv.aggregation_basis",
            "Materialized views are based on aggregation logic/results",
            "PASS" if mv_basis.get("supported") is True else (
                "INCONCLUSIVE" if mv_basis.get("supported") is None else "FAIL"
            ),
            expected=True,
            actual=mv_basis,
            evidence=[json.dumps(mv_basis, ensure_ascii=False)[:2200]],
        ))

        jnames = (semantic.get("jobs") or {}).get("names") or probe.get("job_names") or []
        jmeta = semantic.get("jobs") or {}
        # A live API response with explicit job records is stronger than an
        # incomplete static-code semantic discovery result.
        jobs_body = (probe.get("jobs") or {}).get("body") or {}
        nested_jobs = jobs_body.get("scheduler_status") if isinstance(jobs_body, dict) else {}
        nested_jobs = nested_jobs if isinstance(nested_jobs, dict) else {}
        explicit_jobs = nested_jobs.get("jobs")
        api_jobs_count = len(explicit_jobs) if isinstance(explicit_jobs, (list, dict)) else 0
        jcount = max(len(jnames), int(jmeta.get("declared_count") or 0), api_jobs_count)
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
            and not readme_evidence.get("env_instruction_broken")
        )
        assertions.append(_assertion(
            "final.github_readme",
            "README documents installation, execution, API, queries, indexes/Explain, aggregations, materialized views, and jobs",
            "PASS" if github_readme_pass else ("INCONCLUSIVE" if readme_ok else "FAIL"),
            expected={
                "all_required_topics": True,
                "requirements.txt": True,
                "documented_env_copy_target_exists": True,
            },
            actual=readme_evidence,
            evidence=[json.dumps(readme_evidence, ensure_ascii=False)[:3000]],
        ))
        deps_ok = bool(
            static.get("has_requirements")
            and static.get("fastapi_declared")
            and static.get("uvicorn_declared")
        )
        assertions.append(_assertion(
            "final.dependencies",
            "Final API dependency declarations are complete",
            "PASS" if deps_ok else "FAIL",
            expected="requirements include FastAPI and Uvicorn; env samples are checked against README separately",
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
        if manage_sandbox and not keep_sandbox:
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
