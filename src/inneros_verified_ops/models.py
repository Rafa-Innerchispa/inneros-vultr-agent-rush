"""Data models and invariants for InnerOS Verified Operations v0.6.0.
Governed incident lifecycle: Ingest -> Diagnose -> Plan -> Ticket -> Acknowledge -> Resolve -> Hash.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    INGESTED = "ingested"
    DIAGNOSED = "diagnosed"
    PLAN_PROPOSED = "plan_proposed"
    TICKETED = "ticketed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    FAILED_CLOSED = "failed_closed"


class TicketStatus(str, Enum):
    OPEN = "open"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RESOLVED = "resolved"
    CLOSED = "closed"


def canonical_json(data: Any) -> str:
    """Deterministic canonical JSON serialization for cryptographic integrity."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(data: Any) -> str:
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = canonical_json(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class DiagnosticResult:
    root_cause: str
    confidence: float
    affected_components: List[str]
    telemetry_signals: Dict[str, Any]
    summary: str
    diagnosed_at: float = field(default_factory=time.time)


@dataclass
class ActionStep:
    step_id: str
    action: str
    target: str
    params: Dict[str, Any]
    reversible: bool = True
    estimated_duration_sec: int = 30


@dataclass
class RemediationPlan:
    plan_id: str
    incident_id: str
    steps: List[ActionStep]
    blast_radius: str
    safety_invariants: List[str]
    requires_human_approval: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class ITSMTicket:
    ticket_id: str
    incident_id: str
    title: str
    severity: Severity
    status: TicketStatus
    assignee: str
    approval_ref: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None


@dataclass
class Incident:
    incident_id: str
    title: str
    description: str
    severity: Severity
    status: IncidentStatus = IncidentStatus.INGESTED
    source_service: str = "vultr-cloud-runtime"
    signals: Dict[str, Any] = field(default_factory=dict)
    diagnosis: Optional[DiagnosticResult] = None
    plan: Optional[RemediationPlan] = None
    ticket: Optional[ITSMTicket] = None
    resolution_details: Optional[Dict[str, Any]] = None
    evidence_hash: Optional[str] = None
    receipt_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["status"] = self.status.value
        if self.ticket:
            d["ticket"]["status"] = self.ticket.status.value
            d["ticket"]["severity"] = self.ticket.severity.value
        return d


@dataclass
class CryptographicReceipt:
    receipt_id: str
    incident_id: str
    ticket_id: str
    initial_digest: str
    diagnosis_digest: str
    plan_digest: str
    execution_digest: str
    final_evidence_hash: str
    prev_hash: str
    timestamp_iso: str
    notary: str = "InnerOS-Cryptographic-Notary/0.6.0"

    def verify_integrity(self) -> bool:
        expected = sha256_digest(
            f"{self.receipt_id}:{self.incident_id}:{self.initial_digest}:{self.diagnosis_digest}:{self.plan_digest}:{self.execution_digest}:{self.prev_hash}"
        )
        return self.final_evidence_hash == expected

