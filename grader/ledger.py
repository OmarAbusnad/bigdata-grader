"""Master adjudication ledger: merge the immutable baseline with narrow overlays.

READ-ONLY with respect to students: no student code runs here and no hidden data
is touched. The ledger is keyed by (project_id, phase, assertion_key) under one
frozen commit per project.

Merge rules (deliberately conservative):
  R1  A PASS is never replaced. A contradicting later verdict is logged as a
      conflict for human review.
  R2  Every overlay must carry the project's frozen SHA when it states one;
      a mismatch rejects the whole change.
  R3  A later run that only yields INCONCLUSIVE/ERROR/SKIP does not erase an
      existing FAIL (a FAIL was student-attributed evidence). Only the
      count-policy evidence overlay and explicit rulings may downgrade a FAIL.
  R4  A later run may turn FAIL/INCONCLUSIVE/ERROR/SKIP/absent into PASS or
      FAIL (the grader defect that caused the old verdict was fixed).
  R5  Every change keeps its history (source, run, reason); nothing is lost.
  R6  Manual rulings are applied last, never overwrite PASS unless the ruling
      says override_pass explicitly (and then it is listed separately).
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterator

from .spark_recovery_overlay import spark_recovery_overlay

VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIP")
WEAK = {"INCONCLUSIVE", "ERROR", "SKIP"}
_CLIP = 400


def _clip(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= _CLIP else text[:_CLIP] + "…"


def _entry(raw: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": raw.get("verdict"),
        "expected": _clip(raw.get("expected")),
        "actual": _clip(raw.get("actual")),
        "note": _clip(raw.get("note")),
        "origin": source,
        "history": [],
        "flags": [],
    }


def iter_json(root: Path, *, strict: bool = False) -> Iterator[tuple[str, Any]]:
    """Yield JSON documents. Strict overlay mode never discards malformed evidence."""
    root = Path(root)
    for path in sorted(root.rglob("*.json")):
        try:
            yield str(path.relative_to(root)), json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            if strict:
                raise ValueError(f"Cannot parse overlay evidence: {path}: {exc}") from exc
    for archive in sorted(root.rglob("*.zip")):
        try:
            with zipfile.ZipFile(archive) as z:
                for name in sorted(z.namelist()):
                    if name.endswith(".json"):
                        try:
                            yield f"{archive.name}!{name}", json.loads(z.read(name))
                        except (ValueError, OSError) as exc:
                            if strict:
                                raise ValueError(f"Cannot parse zipped evidence: {archive}!{name}: {exc}") from exc
        except (zipfile.BadZipFile, OSError) as exc:
            if strict:
                raise ValueError(f"Corrupt evidence ZIP: {archive}: {exc}") from exc


def _authoritative(report: dict[str, Any]) -> bool:
    """Reports produced by the format-tolerant grader (>= 4.4 / final >= 1.3)."""
    v = str(report.get("grader_version") or "")
    m = re.match(r"^(?:final-v)?(\d+)\.(\d+)", v)
    if not m:
        return False
    major, minor = int(m.group(1)), int(m.group(2))
    return (major, minor) >= ((1, 3) if v.startswith("final-v") else (4, 4))


def _is_midterm_report(name: str, obj: Any) -> bool:
    """A midterm report keeps its path under reports/, or sits at an artifact root
    (single-path uploads strip the prefix) carrying the midterm plan fields."""
    if not (isinstance(obj, dict) and "project_id" in obj and "commit_sha" in obj
            and isinstance(obj.get("runtime"), dict)):
        return False
    norm = name.replace("\\", "/").replace("!", "/")
    if "reports_final/" in norm or "final_plan" in obj:
        return False
    return "/reports/" in "/" + norm or "execution_plan" in obj or "plan_resolution" in obj


def _is_final_report(name: str, obj: Any) -> bool:
    return (isinstance(obj, dict) and "project_id" in obj and "commit_sha" in obj
            and isinstance(obj.get("runtime"), dict)
            and ("reports_final/" in name.replace("\\", "/") or "final_plan" in obj))


class Ledger:
    def __init__(self) -> None:
        self.projects: dict[str, dict[str, Any]] = {}
        self.rejected: list[dict[str, Any]] = []
        self.conflicts: list[dict[str, Any]] = []
        self.pass_overrides: list[dict[str, Any]] = []
        self.evidence_refreshes: list[dict[str, Any]] = []
        self.sources: list[dict[str, Any]] = []
        self._base_assertions: dict[str, dict[str, dict[str, Any]]] = {}
        self._base_probes: dict[str, dict[str, Any]] = {}
        self._base_pass: set[tuple[str, str, str]] = set()

    # ------------------------------------------------------------------ base
    def load_base(self, root: Path, *, run_id: int) -> None:
        source = {"type": "base", "run_id": run_id}
        mids: dict[str, dict] = {}
        fins: dict[str, dict] = {}
        for name, obj in iter_json(root):
            if _is_final_report(name, obj):
                target = fins
            elif _is_midterm_report(name, obj):
                target = mids
            else:
                continue
            pid = obj["project_id"]
            if pid in target:
                raise ValueError(f"Duplicate base report for {pid} ({name})")
            target[pid] = obj
        if not mids and not fins:
            raise ValueError(f"No base reports found under {root}")
        for pid in sorted(set(mids) | set(fins)):
            shas = {r.get("commit_sha") for r in (mids.get(pid), fins.get(pid)) if r and r.get("commit_sha")}
            if len(shas) > 1:
                raise ValueError(f"{pid}: midterm and final base reports disagree on commit: {shas}")
            proj = {
                "frozen_sha": next(iter(shas), None),
                "students": (mids.get(pid) or fins.get(pid) or {}).get("students", ""),
                "phases": {"midterm": {"status": None, "entries": {}},
                           "final": {"status": None, "entries": {}}},
            }
            self.projects[pid] = proj
            self._base_probes[pid] = ((fins.get(pid) or {}).get("runtime") or {}).get("probe") or {}
            self._load_phase(pid, "midterm", (mids.get(pid) or {}).get("runtime"), source)
            self._load_phase(pid, "final", (fins.get(pid) or {}).get("runtime"), source)
        self.sources.append({**source, "projects": len(self.projects)})

    def _load_phase(self, pid: str, phase: str, runtime: dict | None, source: dict) -> None:
        ph = self.projects[pid]["phases"][phase]
        if not isinstance(runtime, dict):
            ph["status"] = "NOT_PRESENT"
            return
        ph["status"] = runtime.get("status")
        raw = runtime.get("assertions") or {}
        if isinstance(raw, list):
            items: list[tuple[str, dict]] = []
            for a in raw:
                if isinstance(a, dict) and a.get("key"):
                    items.append((a["key"], a))
        elif isinstance(raw, dict):
            items = [(k, v) for k, v in raw.items() if isinstance(v, dict)]
        else:
            items = []
        for key, a in items:
            if a.get("verdict") not in VERDICTS:
                continue
            if key in ph["entries"]:
                ph["entries"][key]["flags"].append("duplicate_key_in_source_first_kept")
                continue
            ph["entries"][key] = _entry(a, source)
            if a["verdict"] == "PASS":
                self._base_pass.add((pid, phase, key))
        self._base_assertions.setdefault(pid, {})[phase] = {
            k: {"verdict": e["verdict"], "expected": e["expected"]}
            for k, e in ph["entries"].items()}

    # --------------------------------------------------------------- changes
    def _reject(self, reason: str, **ctx: Any) -> None:
        self.rejected.append({"reason": reason, **ctx})

    def apply_change(self, pid: str, phase: str, key: str, to: str, source: dict[str, Any], *,
                     sha: str | None = None, allowed_from: set[str] | None = None,
                     detail: dict[str, Any] | None = None,
                     may_downgrade_fail: bool = False, override_pass: bool = False) -> str:
        ctx = {"project_id": pid, "phase": phase, "key": key, "to": to, "source": source}
        proj = self.projects.get(pid)
        if proj is None:
            self._reject("unknown_project", **ctx)
            return "rejected"
        if to not in VERDICTS:
            self._reject("invalid_verdict", **ctx)
            return "rejected"
        if sha and proj["frozen_sha"] and sha != proj["frozen_sha"]:
            self._reject("sha_mismatch", expected_sha=proj["frozen_sha"], got_sha=sha, **ctx)
            return "rejected"
        entries = proj["phases"][phase]["entries"]
        cur = entries.get(key)
        record = {"from": cur["verdict"] if cur else None, "to": to, "source": source, **(detail or {})}
        if cur is None:
            entries[key] = {"verdict": to, "expected": _clip((detail or {}).get("expected")),
                            "actual": _clip((detail or {}).get("observed")),
                            "note": _clip((detail or {}).get("reason")), "origin": source,
                            "history": [], "flags": ["added_by_overlay"]}
            return "added"
        if cur["verdict"] == to:
            event = {**record, "kind": "corroborated"}
            # A newer complete rerun can retain FAIL/INCONCLUSIVE yet demonstrate
            # a different actual count. Never display the old observed=0 when
            # the saved latest proof says observed=18250.
            if cur["verdict"] != "PASS" and source.get("type") in {
                "midterm_full", "final_full", "spark_recovery",
            }:
                updates = {
                    "expected": (detail or {}).get("expected"),
                    "actual": (detail or {}).get("observed"),
                    "note": (detail or {}).get("reason"),
                }
                changed_fields = {}
                for field, raw_value in updates.items():
                    if raw_value is not None:
                        latest = _clip(raw_value)
                        if latest != cur.get(field):
                            changed_fields[field] = cur.get(field)
                            cur[field] = latest
                if changed_fields:
                    event["previous_values"] = changed_fields
                    event["previous_origin"] = cur["origin"]
                    cur["origin"] = source
                    self.evidence_refreshes.append({"project_id": pid, "phase": phase,
                                                     "key": key, "fields": sorted(changed_fields),
                                                     "source": source})
            cur["history"].append(event)
            return "same"
        if allowed_from is not None and cur["verdict"] not in allowed_from:
            self.conflicts.append({"reason": "precondition_mismatch", "current": cur["verdict"],
                                   "allowed_from": sorted(allowed_from), **ctx})
            return "conflict"
        if cur["verdict"] == "PASS":
            if override_pass:
                self.pass_overrides.append({**ctx, "from": "PASS", "detail": detail})
            else:
                self.conflicts.append({"reason": "would_overwrite_pass", "current": "PASS", **ctx})
                return "conflict"
        elif cur["verdict"] == "FAIL" and to in WEAK and not may_downgrade_fail:
            cur["flags"].append(f"later_run_{to.lower()}_did_not_override_fail")
            cur["history"].append({**record, "kind": "ignored_weak_downgrade"})
            return "kept_fail"
        cur["history"].append({**record, "kind": "replaced",
                               "previous_origin": cur["origin"]})
        cur["verdict"] = to
        cur["origin"] = source
        if detail:
            cur["expected"] = _clip(detail.get("expected", cur["expected"]))
            cur["actual"] = _clip(detail.get("observed", cur["actual"]))
            cur["note"] = _clip(detail.get("reason", cur["note"]))
        return "replaced"

    # -------------------------------------------------------------- overlays
    def apply_overlay_dir(self, root: Path, *, run_id: int) -> dict[str, Any]:
        """Strictly consume a requested run, never silently ignore unknown verdict files.

        Extraction proof is explicitly recognized as metadata, NOT a student grade.
        """
        root = Path(root)
        if not root.is_dir():
            raise ValueError(f"Requested overlay run {run_id} is missing: {root}")
        refresh_start = len(self.evidence_refreshes)
        stats: dict[str, Any] = {
            "midterm_reports": 0, "final_reports": 0, "evidence_overlays": 0, "spark_proofs": 0,
            "final_proofs": 0, "metadata_files": 0, "ignored_files": 0,
            "files_seen": 0, "recognized_files": 0, "changes": 0,
            "files": [],
        }
        for name, obj in iter_json(root, strict=True):
            stats["files_seen"] += 1
            source = {"type": "unknown", "run_id": run_id, "file": name}
            kind = "unknown"
            changed = 0
            if _is_midterm_report(name, obj):
                kind = "midterm_full"
                stats["midterm_reports"] += 1
                changed = self._midterm_full(obj, {**source, "type": kind})
            elif _is_final_report(name, obj):
                stats["final_reports"] = stats.get("final_reports", 0) + 1
                changed = self._final_full(obj, {**source, "type": "final_full"})
                kind = "final_full"
            elif isinstance(obj, dict) and isinstance(obj.get("projects"), dict) \
                    and obj.get("student_tests_reexecuted") == 0:
                kind = "evidence_overlay"
                stats["evidence_overlays"] += 1
                changed = self._evidence_overlay(obj, {**source, "type": kind})
            elif isinstance(obj, dict) and obj.get("only_test") == "spark_pipeline.command":
                kind = "spark_recovery"
                stats["spark_proofs"] += 1
                changed = self._spark_proof(obj, {**source, "type": kind}, run_id)
            elif isinstance(obj, dict) and (obj.get("scope") == "only_final.api.ingest"
                                            or isinstance(obj.get("scope"), list)):
                kind = "final_proof"
                stats["final_proofs"] += 1
                changed = self._final_proof(obj, {**source, "type": kind})
            elif (isinstance(obj, dict) and "project_id" in obj and "mode" in obj and "runtime" not in obj
                  and ("midterm" in obj or "final" in obj) and "unified" in name):
                kind = "unified_summary"  # per-project summary; the graded evidence is in reports/ and reports_final/
                stats["metadata_files"] += 1
            elif (isinstance(obj, dict) and obj.get("container") in {"rar", "zip"}
                  and obj.get("student_code_executed_during_extraction") is False
                  and obj.get("official_result_modified") is False
                  and obj.get("frozen_archive") and obj.get("source_root")
                  and "extraction_proof" in name):
                kind = "safe_extraction_metadata"
                stats["metadata_files"] += 1
            else:
                stats["ignored_files"] += 1
            if kind != "unknown":
                stats["recognized_files"] += 1
            stats["changes"] += changed
            stats["files"].append({"path": name, "kind": kind, "changes": changed})
        if not stats["files_seen"]:
            raise ValueError(f"Overlay run {run_id} contains no JSON evidence: {root}")
        if stats["ignored_files"]:
            unknown = [x["path"] for x in stats["files"] if x["kind"] == "unknown"]
            raise ValueError(f"Overlay run {run_id} has {len(unknown)} unrecognized evidence files: {unknown[:10]}")
        if stats["recognized_files"] == stats["metadata_files"]:
            raise ValueError(f"Overlay run {run_id} contains only metadata, no grading evidence")
        stats["evidence_refreshes"] = len(self.evidence_refreshes) - refresh_start
        self.sources.append({"type": "overlay_dir", "run_id": run_id, **stats})
        return stats

    @staticmethod
    def _changed(result: str) -> int:
        return 1 if result in {"added", "replaced"} else 0

    def _midterm_full(self, report: dict, source: dict) -> int:
        pid = report["project_id"]
        proj = self.projects.get(pid)
        if proj is None:
            self._reject("unknown_project", project_id=pid, source=source)
            return 0
        runtime = report["runtime"]
        sha = report.get("commit_sha")
        if sha and proj["frozen_sha"] and sha != proj["frozen_sha"]:
            self._reject("sha_mismatch", project_id=pid, phase="midterm", source=source,
                         expected_sha=proj["frozen_sha"], got_sha=sha)
            return 0
        ph = proj["phases"]["midterm"]
        # Track the latest attempt even if the environment produced no assertions.
        latest_status = runtime.get("status")
        if latest_status is not None and latest_status != ph["status"]:
            ph.setdefault("status_history", []).append({
                "from": ph["status"], "to": latest_status, "source": source,
                "informational": bool(ph["entries"]),
            })
            ph["status"] = latest_status
        raw = runtime.get("assertions")
        if not isinstance(raw, dict) or not raw:
            return 0
        if not ph["entries"] and runtime.get("status") != ph["status"]:
            ph.setdefault("status_history", []).append({"from": ph["status"], "to": runtime.get("status"),
                                                       "source": source})
            ph["status"] = runtime.get("status")
        elif runtime.get("status") != ph["status"]:
            ph.setdefault("status_history", []).append({"from": ph["status"], "to": runtime.get("status"),
                                                       "source": source, "informational": True})
        n = 0
        for key, a in raw.items():
            if isinstance(a, dict) and a.get("verdict") in VERDICTS:
                n += self._changed(self.apply_change(
                    pid, "midterm", key, a["verdict"], source, sha=sha,
                    may_downgrade_fail=_authoritative(report),
                    detail={"expected": a.get("expected"), "observed": a.get("actual"),
                            "reason": a.get("note") or "narrow midterm rerun after grader fix"}))
        return n

    def _final_full(self, report: dict, source: dict) -> int:
        pid = report["project_id"]
        proj = self.projects.get(pid)
        if proj is None:
            self._reject("unknown_project", project_id=pid, source=source)
            return 0
        sha = report.get("commit_sha")
        if sha and proj["frozen_sha"] and sha != proj["frozen_sha"]:
            self._reject("sha_mismatch", project_id=pid, phase="final", source=source,
                         expected_sha=proj["frozen_sha"], got_sha=sha)
            return 0
        runtime = report["runtime"]
        raw = runtime.get("assertions") or []
        items = ([(a["key"], a) for a in raw if isinstance(a, dict) and a.get("key")]
                 if isinstance(raw, list) else list(raw.items()))
        ph = proj["phases"]["final"]
        if runtime.get("status") != ph["status"]:
            ph.setdefault("status_history", []).append({"from": ph["status"], "to": runtime.get("status"), "source": source})
            ph["status"] = runtime.get("status")
        n = 0
        for key, a in items:
            if isinstance(a, dict) and a.get("verdict") in VERDICTS:
                n += self._changed(self.apply_change(
                    pid, "final", key, a["verdict"], source, sha=sha,
                    may_downgrade_fail=_authoritative(report),
                    detail={"expected": a.get("expected"), "observed": a.get("actual"),
                            "reason": a.get("note") or "final rerun after grader fix"}))
        return n

    def _evidence_overlay(self, obj: dict, source: dict) -> int:
        n = 0
        for pid, ov in obj["projects"].items():
            for key, change in (ov.get("overrides") or {}).items():
                n += self._changed(self.apply_change(
                    pid, "midterm", key, change["new"], source, sha=ov.get("student_commit"),
                    allowed_from={change["previous"]}, may_downgrade_fail=True,
                    detail={"expected": change.get("expected"), "observed": change.get("observed"),
                            "reason": change.get("reason"), "scope": change.get("scope")}))
        return n

    def _spark_proof(self, proof: dict, source: dict, run_id: int) -> int:
        pid = proof.get("project_id")
        proj = self.projects.get(pid or "")
        if proj is None:
            self._reject("unknown_project", project_id=pid, source=source)
            return 0
        base = self._base_assertions.get(pid, {}).get("midterm", {})
        original = {"project_id": pid, "commit_sha": proj["frozen_sha"],
                    "runtime": {"assertions": base}}
        try:
            overlay = spark_recovery_overlay(original, proof, proof_run_id=run_id)
        except ValueError as exc:
            self._reject("spark_overlay_refused", project_id=pid, source=source, message=str(exc))
            return 0
        n = 0
        for key, ov in overlay["overrides"].items():
            n += self._changed(self.apply_change(
                pid, "midterm", key, ov["to"], source, sha=proof.get("frozen_commit"),
                allowed_from={ov["from"]},
                detail={"observed": ov.get("observed"), "reason": ov.get("reason"),
                        "scope": ov.get("scope")}))
        return n

    def _final_proof(self, proof: dict, source: dict) -> int:
        pid = proof.get("project") or proof.get("project_id")
        pairs: list[tuple[str, str | None]] = []
        if proof.get("scope") == "only_final.api.ingest":
            pairs = [("final.api.ingest", proof.get("verdict"))]
        elif isinstance(proof.get("scope"), list):
            if "final.mv.refresh" in proof["scope"]:
                pairs.append(("final.mv.refresh", proof.get("verdict_refresh")))
            if "final.mv.incremental" in proof["scope"]:
                pairs.append(("final.mv.incremental", proof.get("verdict_incremental")))
        n = 0
        for key, verdict in pairs:
            if verdict not in VERDICTS:
                continue
            n += self._changed(self.apply_change(
                pid or "", "final", key, verdict, source, sha=None,
                detail={"reason": proof.get("reason") or "targeted final probe",
                        "scope": proof.get("scope")}))
            entry = (self.projects.get(pid or "") or {}).get("phases", {}).get("final", {}).get("entries", {}).get(key)
            if entry is not None and "sha_not_in_proof" not in entry["flags"]:
                entry["flags"].append("sha_not_in_proof")
        return n

    @staticmethod
    def _http_transport_timeout(response: Any) -> bool:
        """Distinguish no-response timeout from HTTP 4xx/5xx application failure."""
        if not isinstance(response, dict) or response.get("status") is not None:
            return False
        error = str(response.get("error") or "").lower()
        return ("timeout" in error or "timed out" in error) and response.get("ok") is not True

    def apply_frozen_transport_preconditions(self, *, base_run_id: int) -> dict[str, Any]:
        """Adjudicate only provably uncompleted HTTP probes in frozen FINAL evidence.

        Never infer an endpoint PASS, never downgrade a real HTTP error, never
        rewrite a later PASS. No student reruns or human grade approvals.
        """
        checked = 0
        changes = []
        source = {"type": "frozen_http_timeout_precondition",
                  "run_id": base_run_id}
        for pid, proj in sorted(self.projects.items()):
            checked += 1
            probe = self._base_probes.get(pid) or {}
            tests: dict[str, Any] = {
                "final.mv.refresh": probe.get("refresh_mv_first"),
                "final.mv.incremental": probe.get("refresh_mv_second"),
            }
            attempts = probe.get("ingest_attempts") or []
            if (isinstance(attempts, list) and attempts
                    and all(self._http_transport_timeout(a.get("response")) for a in attempts
                            if isinstance(a, dict))
                    and all(isinstance(a, dict) for a in attempts)):
                tests["final.api.ingest"] = attempts[0].get("response")
            for key, response in tests.items():
                if not self._http_transport_timeout(response):
                    continue
                existing = proj["phases"]["final"]["entries"].get(key)
                if not existing or existing.get("verdict") != "FAIL":
                    continue
                base_entry = self._base_assertions.get(pid, {}).get("final", {}).get(key) or {}
                if base_entry.get("verdict") != "FAIL":
                    continue
                verdict = self.apply_change(
                    pid, "final", key, "INCONCLUSIVE", source,
                    allowed_from={"FAIL"}, may_downgrade_fail=True,
                    detail={
                        "reason": "Frozen HTTP request timed out without an HTTP status; functionality not proven or disproven",
                        "observed": {"http_status": None, "transport_error": response.get("error")},
                        "scope": "original_final_probe_only",
                    },
                )
                if verdict == "replaced":
                    changes.append({"project_id": pid, "phase": "final",
                                    "key": key, "from": "FAIL", "to": "INCONCLUSIVE",
                                    "source_run": base_run_id,
                                    "evidence": str(response.get("error"))[:200]})
        stats = {"type": "frozen_http_timeout_precondition", "run_id": base_run_id,
                 "projects_checked": checked, "changes": len(changes), "cases": changes}
        self.sources.append(stats)
        return stats

    def apply_final_explain_rule(self, *, base_run_id: int) -> dict[str, Any]:
        """Re-adjudicate final.indexes.explain INCONCLUSIVE from saved evidence only.

        The static scanner (`supported`) can under-count explain() call sites. When the saved
        evidence shows executionStats + before/after + rationale AND >= 3 distinct runtime IXSCAN
        queries, the requirement is met. Never touches PASS/FAIL, never runs student code.
        """
        source = {"type": "evidence_rule_final_explain", "run_id": base_run_id}
        changes = []
        for pid, proj in sorted(self.projects.items()):
            e = proj["phases"]["final"]["entries"].get("final.indexes.explain")
            if not e or e["verdict"] != "INCONCLUSIVE" or e["origin"].get("type") != "base":
                continue
            try:
                doc = json.loads(e["actual"]) if isinstance(e["actual"], str) else dict(e["actual"] or {})
            except (TypeError, ValueError):
                continue
            if (doc.get("execution_stats") and doc.get("before_after") and doc.get("rationale")
                    and int(doc.get("runtime_ixscan_hits") or 0) >= 3):
                r = self.apply_change(
                    pid, "final", "final.indexes.explain", "PASS", source, allowed_from={"INCONCLUSIVE"},
                    detail={"reason": "executionStats + before/after + rationale documented and >=3 runtime IXSCAN queries; static call-site count was incomplete",
                            "observed": {"runtime_ixscan_hits": doc.get("runtime_ixscan_hits")}})
                if r == "replaced":
                    changes.append({"project_id": pid, "key": "final.indexes.explain"})
        stats = {"type": "evidence_rule_final_explain", "run_id": base_run_id, "changes": len(changes), "cases": changes}
        self.sources.append(stats)
        return stats

    def apply_rulings(self, rulings: list[dict[str, Any]]) -> int:
        n = 0
        for r in rulings:
            for field in ("project_id", "phase", "key", "to", "reason", "decided_by"):
                if not r.get(field):
                    self._reject("ruling_missing_field", field=field, ruling=r)
                    break
            else:
                source = {"type": "ruling", "decided_by": r["decided_by"]}
                n += self._changed(self.apply_change(
                    r["project_id"], r["phase"], r["key"], r["to"], source,
                    may_downgrade_fail=True, override_pass=bool(r.get("override_pass")),
                    detail={"reason": r["reason"], "evidence": r.get("evidence")}))
        self.sources.append({"type": "rulings", "count": len(rulings), "changes": n})
        return n

    # ---------------------------------------------------------------- output
    def counts(self, pid: str, phase: str) -> dict[str, int]:
        out = {v: 0 for v in VERDICTS}
        for e in self.projects[pid]["phases"][phase]["entries"].values():
            out[e["verdict"]] += 1
        return out

    def verify(self, *, expected_projects: int | None = None) -> dict[str, Any]:
        problems: list[str] = []
        if expected_projects is not None and len(self.projects) != expected_projects:
            problems.append(f"expected {expected_projects} projects, found {len(self.projects)}")
        overridden = {(o["project_id"], o["phase"], o["key"]) for o in self.pass_overrides}
        lost = []
        for pid, phase, key in sorted(self._base_pass - overridden):
            e = self.projects[pid]["phases"][phase]["entries"].get(key)
            if not e or e["verdict"] != "PASS":
                lost.append(f"{pid}/{phase}/{key}")
        if lost:
            problems.append(f"{len(lost)} baseline PASS verdicts were lost: {lost[:10]}")
        total = sum(sum(self.counts(p, ph).values()) for p in self.projects for ph in ("midterm", "final"))
        listed = sum(len(self.projects[p]["phases"][ph]["entries"]) for p in self.projects for ph in ("midterm", "final"))
        if total != listed:
            problems.append("count mismatch between verdict tally and entries")
        return {"ok": not problems, "problems": problems, "baseline_pass_preserved": len(self._base_pass) - len(lost),
                "baseline_pass_total": len(self._base_pass), "pass_overrides": len(self.pass_overrides)}

    def to_dict(self, *, expected_projects: int | None = None) -> dict[str, Any]:
        return {
            "formal_grade": False,
            "student_code_executed": False,
            "sources": self.sources,
            "invariants": self.verify(expected_projects=expected_projects),
            "projects": self.projects,
            "conflicts": self.conflicts,
            "rejected": self.rejected,
            "pass_overrides": self.pass_overrides,
            "evidence_refreshes": self.evidence_refreshes,
        }


_HINTS = (
    ("timeouterror", "candidate_transport_timeout_no_http_status"),
    ("timed out", "candidate_transport_timeout_no_http_status"),
    ("unresolved dependencies", "candidate_dependency_resolution"),
    ("modulenotfounderror", "candidate_student_missing_dependency"),
    ("syntaxerror", "candidate_student_syntax_error"),
)


def review_hint(entry: dict[str, Any]) -> str:
    text = " ".join(str(entry.get(k) or "") for k in ("actual", "note")).lower()
    for needle, hint in _HINTS:
        if needle in text:
            return hint
    if entry["verdict"] in WEAK:
        return "needs_cause"
    return "needs_student_evidence_check"
