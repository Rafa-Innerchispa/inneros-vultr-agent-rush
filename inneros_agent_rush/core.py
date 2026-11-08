"""Real multi-step workflow, persistent records, and tamper-evident event chain."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import DockerRunner, SandboxUnavailable
from .llm import ModelError, OpenAICompatibleModel
from .containment import SCENARIOS, classify_scenario_result


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_run_integrity(record: dict) -> dict:
    """Independent integrity summary over persisted evidence and report bytes.

    A chained ledger proves consistency of its current contents; it does not
    independently establish who wrote them or prove any physical device changed.
    """
    events = record.get("events") or []
    chain_valid = event_chain_valid(events)
    artifact = record.get("artifact")
    artifact_present = artifact is not None
    if artifact_present:
        content = artifact.get("content") or artifact.get("candidate_code")
        artifact_valid = (isinstance(content, str) and
                          isinstance(artifact.get("sha256"), str) and
                          digest(content) == artifact["sha256"])
    else:
        artifact_valid = None
    return {
        "run_id": record["id"],
        "run_status": record["status"],
        "event_count": len(events),
        "evidence_chain_valid": chain_valid,
        "artifact_present": artifact_present,
        "artifact_integrity_valid": artifact_valid,
        "final_evidence_hash": events[-1]["hash"] if events else None,
        "verified": chain_valid and artifact_valid is not False,
        "limitations": "Hash consistency only; not an external signature or proof of physical remediation"
    }


def event_chain_valid(events: list[dict]) -> bool:
    previous = "0" * 64
    for event in events:
        content = {k: v for k, v in event.items() if k != "hash"}
        expected = digest(previous + json.dumps(content, sort_keys=True, separators=(",", ":")))
        if event.get("previous_hash") != previous or event.get("hash") != expected:
            return False
        previous = expected
    return True


class Ledger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                kind TEXT NOT NULL, status TEXT NOT NULL, record TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, record TEXT NOT NULL
            )""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, record: dict) -> None:
        with self.lock, self._connect() as con:
            con.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                        (record["id"], record["created_at"], record["kind"],
                         record["status"], json.dumps(record)))

    def one(self, run_id: str) -> dict | None:
        with self.lock, self._connect() as con:
            row = con.execute("SELECT record FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def recent(self, limit=20, *, public_only=False) -> list[dict]:
        # The public dashboard must never reveal runs performed by an operator.
        # Store only curated public demo inputs in a shared demonstration deployment.
        with self.lock, self._connect() as con:
            rows = con.execute("SELECT record FROM runs ORDER BY rowid DESC LIMIT 500").fetchall()
        records = [json.loads(row[0]) for row in rows]
        if public_only:
            records = [r for r in records if r.get("public_demo") is True]
        return records[:max(0, min(limit, 100))]


    def save_operation(self, record: dict, ticket: dict) -> None:
        """Persist the triage run and new service ticket in one DB transaction."""
        with self.lock, self._connect() as con:
            con.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                        (record["id"], record["created_at"], record["kind"],
                         record["status"], json.dumps(record)))
            con.execute("INSERT INTO tickets VALUES (?, ?, ?)",
                        (ticket["id"], ticket["created_at"], json.dumps(ticket)))

    def save_ticket(self, ticket: dict) -> None:
        with self.lock, self._connect() as con:
            con.execute("INSERT INTO tickets VALUES (?, ?, ?)",
                        (ticket["id"], ticket["created_at"], json.dumps(ticket)))

    def one_ticket(self, ticket_id: str) -> dict | None:
        with self.lock, self._connect() as con:
            row = con.execute("SELECT record FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def recent_tickets(self, limit: int = 25, *, public_only: bool = False) -> list[dict]:
        with self.lock, self._connect() as con:
            rows = con.execute("SELECT record FROM tickets ORDER BY rowid DESC LIMIT 500").fetchall()
        tickets = [json.loads(row[0]) for row in rows]
        if public_only:
            tickets = [t for t in tickets if t.get("public_demo") is True]
        return tickets[:max(0, min(limit, 100))]

    def transition_ticket(self, ticket_id: str, action: str, note: str, actor: str) -> dict:
        transitions = {("open", "acknowledge"): "in_progress",
                       ("in_progress", "resolve"): "resolved",
                       ("resolved", "reopen"): "open"}
        with self.lock, self._connect() as con:
            # Serialize across workers: no duplicate or out-of-order transitions.
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT record FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if row is None:
                raise KeyError("Ticket not found")
            ticket = json.loads(row[0])
            new_status = transitions.get((ticket["status"], action))
            if new_status is None:
                raise ValueError("Invalid workflow state transition")
            previous = ticket["history"][-1]["hash"]
            event = {"index": len(ticket["history"]) + 1, "at": utcnow(),
                     "step": action, "status": new_status, "details": {
                        "note": note, "actor": actor, "verification": "operator_attested"},
                     "previous_hash": previous}
            event["hash"] = digest(previous + json.dumps(event, sort_keys=True, separators=(",", ":")))
            ticket["history"].append(event)
            ticket["status"] = new_status
            ticket["updated_at"] = event["at"]
            con.execute("UPDATE tickets SET record=? WHERE id=?", (json.dumps(ticket), ticket_id))
        return ticket


CASES = {
    "uptime_boundary": {
        "title": "Customer uptime SLA classification is wrong at threshold",
        "description": "A production service is marked down at exactly 5 healthy minutes.",
        "code": "def classify_uptime(minutes):\n    return 'down' if minutes <= 5 else 'healthy'\n",
        "tests": "assert classify_uptime(0) == 'down'\nassert classify_uptime(4) == 'down'\nassert classify_uptime(5) == 'healthy'\n",
    },
    "sla_sign": {
        "title": "SLA report shows negative delay after deadline",
        "description": "A helpdesk reporting function reverses the sign of minutes late.",
        "code": "def minutes_late(actual, target):\n    return target - actual\n",
        "tests": "assert minutes_late(11, 9) == 2\nassert minutes_late(8, 9) == -1\n",
    },
    "runaway_loop": {
        "title": "Safety proof: an agent creates an infinite loop",
        "description": "Containment demonstration. The runner must enforce timeout and destroy sandbox.",
        "code": "while True:\n    pass\n",
        "tests": "assert True\n",
    },
}


def deterministic_patch(case_id: str, code: str) -> str | None:
    if case_id == "uptime_boundary":
        return code.replace("minutes <= 5", "minutes < 5", 1)
    if case_id == "sla_sign":
        return code.replace("return target - actual", "return actual - target", 1)
    return None


class WorkflowEngine:
    def __init__(self, store: Ledger, *, runner=None, model=None):
        self.store = store
        self.runner = runner if runner is not None else DockerRunner()
        self.model = model if model is not None else OpenAICompatibleModel()

    def _new(self, kind: str, title: str, *, public_demo: bool = False) -> dict:
        return {"id": str(uuid.uuid4()), "kind": kind, "title": title,
                "status": "running", "public_demo": public_demo, "created_at": utcnow(),
                "events": [], "artifact": None, "execution": None}

    def _event(self, record: dict, step: str, status: str, details: dict[str, Any]) -> None:
        prev = record["events"][-1]["hash"] if record["events"] else "0" * 64
        event = {"index": len(record["events"]) + 1, "at": utcnow(),
                 "step": step, "status": status, "details": details, "previous_hash": prev}
        event["hash"] = digest(prev + json.dumps(event, sort_keys=True, separators=(",", ":")))
        record["events"].append(event)

    def run_containment(self, scenario_id: str, *, public_demo: bool = False) -> dict:
        """Execute one curated isolation challenge; never run arbitrary browser code.

        A signed Vultr attestation is not produced: this is a repeatable runtime
        self-test with a locally consistent evidence chain and content hash.
        """
        scenario = SCENARIOS[scenario_id]
        record = self._new("containment_lab", scenario.title, public_demo=public_demo)
        record["scenario_id"] = scenario.id
        self._event(record, "define_boundary", "completed", {
            "scenario_id": scenario.id,
            "objective": scenario.objective,
            "expected": scenario.expected,
            "candidate_sha256": digest(scenario.code),
            "assertions_sha256": digest(scenario.assertions),
            "no_host_fallback": True,
        })
        try:
            execution = self.runner.run(scenario.code, scenario.assertions)
        except SandboxUnavailable as exc:
            record["status"] = "blocked"
            self._event(record, "isolation_test", "blocked", {
                "reason": str(exc), "no_host_fallback": True,
                "sandbox_claim": "NOT VERIFIED",
            })
            self.store.save(record)
            return record
        passed, summary = classify_scenario_result(scenario, execution)
        record["execution"] = {"containment": execution.public()}
        record["status"] = "contained" if passed else "failed"
        self._event(record, "isolation_test", "passed" if passed else "failed", {
            "scenario_id": scenario.id, "outcome": summary,
            "runner_reported_pass": execution.passed,
            "runner_reported_timeout": execution.timeout,
            "exit_code": execution.exit_code,
            "execution_mode": execution.execution_mode,
            "container_cleanup_verified": execution.cleanup_verified,
        })
        evidence = {
            "scenario_id": scenario.id,
            "objective": scenario.objective,
            "expected": scenario.expected,
            "outcome": summary,
            "verified_containment": passed,
            "execution": execution.public(),
            "limitations": "Docker runtime self-test; no independent Vultr or kernel attestation",
        }
        content = json.dumps(evidence, sort_keys=True, indent=2)
        record["artifact"] = {"type": "containment_evidence", "content": content,
                              "sha256": digest(content)}
        self._event(record, "persist_evidence", "completed", {
            "artifact_sha256": record["artifact"]["sha256"],
            "evidence_kind": "docker_runtime_self_test",
        })
        self.store.save(record)
        return record

    def run_triage(self, title: str, description: str, customer: str = "Demo customer",
                   *, public_demo: bool = False) -> dict:
        record = self._new("customer_support", title, public_demo=public_demo)
        self._event(record, "receive", "completed", {"customer": customer,
                     "input_sha256": digest(title + "\n" + description)})
        source = (title + " " + description).lower()
        priority = "P1" if any(t in source for t in ("offline", "down", "outage", "caído", "caida", "caída", "intrusion", "intrusión")) else (
            "P2" if any(t in source for t in ("intermittent", "slow", "error", "lent", "inestable", "fallo")) else "P3")
        category = "connectivity" if any(t in source for t in ("network", "switch", "sfp", "fiber", "fibra", "internet", "router")) else (
            "access_control" if any(t in source for t in ("door", "puerta", "zkteco", "portero")) else "technical_support")
        self._event(record, "classify", "completed", {"priority": priority, "category": category,
                    "decision_origin": "deterministic_policy", "confidence": "rule_match"})
        checks = {
            "connectivity": ["Verify power and port status", "Check uplink and SFP optical signal",
                             "Collect interface counters and logs", "Escalate failed hardware replacement"],
            "access_control": ["Verify controller availability", "Check door state and power",
                               "Validate access logs and authorized credentials", "Schedule controlled field test"],
            "technical_support": ["Collect exact symptoms and timestamps", "Run non-invasive diagnostics",
                                  "Document findings", "Escalate unresolved fault with evidence"],
        }[category]
        self._event(record, "plan", "completed", {"tasks": checks,
                    "approval_required_for": ["device_reboot", "credential_change", "production_write"]})
        sla = {"P1": "15 minutes", "P2": "2 hours", "P3": "next business day"}[priority]
        advisory_text = ""
        if self.model.enabled:
            try:
                advice = self.model.incident_advice(
                    title=title, description=description, priority=priority,
                    category=category, checks=checks,
                )
                hypotheses = advice["hypotheses"]
                advisory_text = (
                    "\n\n## Optional AI advisory (non-binding)\n"
                    "Model origin: " + str(advice["origin"]) + "\n\n" +
                    str(advice["summary"]) + "\n\n" +
                    "\n".join("- Possible cause: " + str(item) for item in hypotheses) +
                    "\n\nAI suggestions are not verified facts, do not alter fixed priorities, "
                    "and do not authorize production changes.\n"
                )
                self._event(record, "ai_advisory", "completed", {
                    "origin": str(advice["origin"]),
                    "decision_authority": "deterministic_policy",
                    "advisory_sha256": digest(advisory_text),
                })
            except ModelError as exc:
                self._event(record, "ai_advisory", "unavailable", {
                    "reason": str(exc), "fallback": "deterministic_policy",
                    "policy_unchanged": True,
                })
        report = (f"# Service Action Plan | {record['id'][:8]}\n\n"
                  f"**Customer:** {customer}\n\n**Incident:** {title}\n\n"
                  f"**Priority:** {priority} | **Category:** {category} | **Response target:** {sla}\n\n"
                  f"## Reported symptoms\n{description}\n\n## Next actions\n" +
                  "\n".join(f"- [ ] {s}" for s in checks) +
                  "\n\n## Governance\nProduction changes require separate authorization. "
                  "No hardware was changed by this workflow.\n" + advisory_text)
        record["artifact"] = {"type": "markdown", "content": report,
                              "sha256": digest(report), "origin": "deterministic_policy"}
        self._event(record, "create_report", "completed", {"artifact_sha256": digest(report),
                    "format": "markdown", "side_effects": "none"})
        ticket_id = str(uuid.uuid4())
        record["ticket_id"] = ticket_id
        self._event(record, "open_ticket", "completed", {"ticket_id": ticket_id,
                    "action": "persist_service_ticket"})
        self._event(record, "verify", "completed", {"artifact_integrity": digest(report) == record["artifact"]["sha256"],
                    "all_steps_completed": True, "ticket_opened": True})
        record["status"] = "completed"
        ticket = {"id": ticket_id, "run_id": record["id"], "title": title,
                  "customer": customer, "priority": priority, "category": category,
                  "response_target": sla, "status": "open", "public_demo": public_demo,
                  "created_at": utcnow(), "updated_at": utcnow(), "history": []}
        event = {"index": 1, "at": utcnow(), "step": "ticket_opened", "status": "open",
                 "details": {"triage_run_sha256": record["events"][-1]["hash"],
                             "decision_origin": "deterministic_policy"},
                 "previous_hash": "0" * 64}
        event["hash"] = digest(event["previous_hash"] + json.dumps(event, sort_keys=True, separators=(",", ":")))
        ticket["history"].append(event)
        self.store.save_operation(record, ticket)
        return record

    def run_repair(self, case_id: str, *, title: str | None = None,
                   code: str | None = None, tests: str | None = None,
                   description: str | None = None,
                   public_demo: bool = False) -> dict:
        if case_id in CASES and code is None and tests is None:
            item = CASES[case_id]
            title, description, code, tests = item["title"], item["description"], item["code"], item["tests"]
        elif not (title and description and code and tests):
            raise ValueError("Custom repair must supply title, description, code and assertions")
        assert title is not None and description is not None and code is not None and tests is not None
        record = self._new("verified_code_repair", title, public_demo=public_demo)
        record["input"] = {"case_id": case_id, "original_sha256": digest(code),
                           "assertions_sha256": digest(tests)}
        self._event(record, "intake", "completed", {"code_sha256": digest(code),
                    "assertions_sha256": digest(tests)})
        self._event(record, "plan", "completed", {"sequence": ["baseline", "propose_patch", "verify", "evidence"],
                    "execution_policy": "disposable Docker container; no network; no host execution"})
        try:
            baseline = self.runner.run(code, tests)
        except SandboxUnavailable as exc:
            record["status"] = "blocked"
            self._event(record, "baseline", "blocked", {"reason": str(exc),
                        "host_execution_fallback": False})
            self.store.save(record)
            return record
        record["execution"] = {"baseline": baseline.public(), "candidate": None}
        self._event(record, "baseline", "completed" if baseline.passed else "failed_as_expected",
                    {"passed": baseline.passed, "timeout": baseline.timeout,
                     "exit_code": baseline.exit_code, "stderr_excerpt": baseline.stderr[-600:]})
        if baseline.timeout:
            cleanup_ok = baseline.cleanup_verified is True
            record["status"] = "contained" if cleanup_ok else "needs_review"
            self._event(record, "containment", "completed" if cleanup_ok else "unverified", {
                "infinite_loop_killed": True,
                "container_cleanup_verified": baseline.cleanup_verified,
                "network_disabled_by_docker_policy": True,
                "claim_limit": "No independent kernel attestation",
            })
            self.store.save(record)
            return record
        if baseline.passed:
            clean = baseline.cleanup_verified is True
            record["status"] = "completed" if clean else "needs_review"
            self._event(record, "verify", "completed" if clean else "unverified", {
                "no_patch_required": True,
                "container_cleanup_verified": baseline.cleanup_verified,
            })
            self.store.save(record)
            return record
        candidate = None
        origin = "none"
        if self.model.enabled:
            try:
                candidate = self.model.propose(description=description, code=code, tests=tests,
                                               failure=baseline.stderr)
                origin = self.model.label
            except ModelError as exc:
                self._event(record, "propose_patch", "failed", {"model_error": str(exc)})
        if candidate is None and case_id in CASES:
            candidate = deterministic_patch(case_id, code)
            origin = "deterministic_demo_fallback"
        if not candidate or candidate == code:
            record["status"] = "needs_review"
            self._event(record, "propose_patch", "blocked", {"reason": "No acceptable patch generated"})
            self.store.save(record)
            return record
        try:
            compile(candidate, "<proposed>", "exec")  # parse only, NEVER execute on host
        except SyntaxError as exc:
            record["status"] = "needs_review"
            self._event(record, "propose_patch", "failed", {"reason": "Invalid candidate syntax", "line": exc.lineno})
            self.store.save(record)
            return record
        self._event(record, "propose_patch", "completed", {"origin": origin,
                    "candidate_sha256": digest(candidate), "changed": candidate != code})
        try:
            result = self.runner.run(candidate, tests)
        except SandboxUnavailable as exc:
            record["status"] = "blocked"
            self._event(record, "verify", "blocked", {"reason": str(exc)})
            self.store.save(record)
            return record
        record["execution"]["candidate"] = result.public()
        record["artifact"] = {"type": "code_patch", "original_code": code,
                              "candidate_code": candidate, "assertions": tests,
                              "origin": origin, "original_sha256": digest(code),
                              "candidate_sha256": digest(candidate),
                              "sha256": digest(candidate)}
        self._event(record, "verify", "completed" if result.passed else "failed",
                    {"tests_passed": result.passed, "exit_code": result.exit_code,
                     "timed_out": result.timeout, "candidate_sha256": digest(candidate),
                     "container_cleanup_verified": result.cleanup_verified})
        record["status"] = "completed" if result.passed and result.cleanup_verified is True else "needs_review"
        self.store.save(record)
        return record
