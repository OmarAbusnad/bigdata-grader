from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any, Literal

Verdict = Literal['PASS', 'FAIL', 'INCONCLUSIVE', 'ERROR', 'SKIP']

@dataclass
class ExecutionPlan:
    repo_path: str
    install_command: str = "pip install -r requirements.txt"
    setup_command: str | None = None
    entrypoint: str | None = None
    ingest_command: str | None = None
    reset_command: str | None = None
    database_name: str | None = None
    database_configurable: bool = False
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_uri_configurable: bool = False
    collections: dict[str, str] = field(default_factory=lambda: {
        "raw": "orders_raw",
        "validated": "orders_validated",
        "quarantine": "orders_quarantine",
    })
    business_key: str = "order_id"
    threshold_mb: float | None = None
    threshold_configurable: bool = False
    spark_master: str | None = None
    spark_master_configurable: bool = False
    advanced_track: str | None = None
    confidence: float = 0.0
    source: str = "heuristic"
    warnings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class AssertionResult:
    key: str
    label: str
    verdict: Verdict
    expected: Any = None
    actual: Any = None
    evidence: list[str] = field(default_factory=list)
    note: str | None = None

    @property
    def passed(self) -> bool:
        return self.verdict == 'PASS'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class RuntimeCaseResult:
    name: str
    command: str | None = None
    command_result: CommandResult | None = None
    snapshot_before: dict[str, Any] | None = None
    snapshot_after: dict[str, Any] | None = None
    engine: str | None = None
    engine_evidence: list[str] = field(default_factory=list)
    metrics: dict[str, Any] | None = None
    assertions: list[AssertionResult] = field(default_factory=list)

    @property
    def verdict(self) -> Verdict:
        if any(a.verdict == 'ERROR' for a in self.assertions):
            return 'ERROR'
        if any(a.verdict == 'FAIL' for a in self.assertions):
            return 'FAIL'
        if any(a.verdict == 'INCONCLUSIVE' for a in self.assertions):
            return 'INCONCLUSIVE'
        if self.assertions and all(a.verdict in {'PASS', 'SKIP'} for a in self.assertions):
            return 'PASS'
        return 'INCONCLUSIVE'

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'command': self.command,
            'command_result': self.command_result.to_dict() if self.command_result else None,
            'snapshot_before': self.snapshot_before,
            'snapshot_after': self.snapshot_after,
            'engine': self.engine,
            'engine_evidence': self.engine_evidence,
            'metrics': self.metrics,
            'verdict': self.verdict,
            'assertions': [a.to_dict() for a in self.assertions],
        }
