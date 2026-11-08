"""Tests make a distinction between real execution and safe refusal."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from inneros_agent_rush.core import Ledger, WorkflowEngine, event_chain_valid, CASES
from inneros_agent_rush.main import create_app
from inneros_agent_rush.runner import ExecutionResult, SandboxUnavailable


class UnavailableRunner:
    def ready(self):
        return False

    def run(self, code, tests):
        raise SandboxUnavailable("Docker image unavailable")


class MockSandbox:
    """TEST-ONLY interface stand-in, not displayed to end users as a real run."""
    def __init__(self):
        self.calls = []

    def ready(self):
        return True

    def run(self, code, tests):
        self.calls.append((code, tests))
        if "while True" in code:
            return ExecutionResult(False, None, "", "deadline hit", True, cleanup_verified=True)
        if "minutes <= 5" in code or "return target - actual" in code:
            return ExecutionResult(False, 2, "", "AssertionError", False, cleanup_verified=True)
        return ExecutionResult(True, 0, "ASSERTIONS_PASSED", "", False, cleanup_verified=True)


class NoModel:
    enabled = False
    label = "deterministic_rules"


def new_engine(tmp_path, runner=None):
    return WorkflowEngine(Ledger(tmp_path / "run.sqlite"),
                          runner=runner or UnavailableRunner(), model=NoModel())


def test_triage_persists_real_report_and_chain(tmp_path):
    engine = new_engine(tmp_path)
    job = engine.run_triage("Fiber uplink SFP offline", "Fiber link is down at the control room", "Bellini demo")
    assert job["status"] == "completed"
    assert [ev["step"] for ev in job["events"]] == ["receive", "classify", "plan", "create_report", "open_ticket", "verify"]
    assert event_chain_valid(job["events"])
    assert "P1" in job["artifact"]["content"]
    assert "SFP optical signal" in job["artifact"]["content"]
    assert engine.store.one(job["id"]) == job
    assert len(engine.store.recent()) == 1


def test_tampered_event_chain_fails(tmp_path):
    engine = new_engine(tmp_path)
    job = engine.run_triage("Switch error reported", "Intermittent connection to upstream", "Demo")
    job["events"][1]["details"]["priority"] = "P9"
    assert not event_chain_valid(job["events"])


def test_sandbox_unavailable_fails_closed(tmp_path):
    job = new_engine(tmp_path).run_repair("uptime_boundary")
    assert job["status"] == "blocked"
    assert job["execution"] is None
    assert job["events"][-1]["details"]["host_execution_fallback"] is False
    assert event_chain_valid(job["events"])


@pytest.mark.parametrize("case", ["uptime_boundary", "sla_sign"])
def test_repair_control_flow_uses_runner_twice(tmp_path, case):
    sandbox = MockSandbox()
    engine = new_engine(tmp_path, sandbox)
    run = engine.run_repair(case)
    assert run["status"] == "completed"
    assert len(sandbox.calls) == 2
    assert sandbox.calls[0][1] == sandbox.calls[1][1]
    assert run["execution"]["candidate"]["passed"] is True
    assert run["artifact"]["origin"] == "deterministic_demo_fallback"
    from inneros_agent_rush.core import verify_run_integrity
    proof = verify_run_integrity(run)
    assert proof["verified"] is True, "Candidate source hash must validate"
    assert proof["artifact_integrity_valid"] is True
    assert run["execution"]["candidate"]["cleanup_verified"] is True
    assert event_chain_valid(run["events"])


def test_timeout_control_flow_stops_without_patch(tmp_path):
    runner = MockSandbox()
    record = new_engine(tmp_path, runner).run_repair("runaway_loop")
    assert record["status"] == "contained"
    assert len(runner.calls) == 1
    assert record["execution"]["baseline"]["timeout"] is True
    assert record["artifact"] is None


def test_http_triage_and_audit_api(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="", public_demo=True)
    with TestClient(app) as client:
        health = client.get("/healthz")
        assert health.status_code == 200 and not health.json()["sandbox_ready"]
        response = client.post("/api/triage", json={"title":"Network offline switch A",
                     "description":"Connection is down and requires verification", "customer":"Demo"})
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "completed"
        detail = client.get("/api/runs/" + run["id"])
        assert detail.status_code == 200 and detail.json()["evidence_chain_valid"]
        artifact = client.get("/api/runs/" + run["id"] + "/artifact")
        assert artifact.status_code == 200 and "Service Action Plan" in artifact.text
        assert len(client.get("/api/runs").json()) == 1
        assert client.get("/").status_code == 200


def test_public_demo_refuses_custom_code(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="secret", public_demo=True)
    with TestClient(app) as client:
        assert client.post("/api/repair", json={"case_id":"custom","title":"Custom code check",
                     "description":"Test custom code in sandbox", "code":"print('hi')", "tests":"assert True"}).status_code == 401
        assert client.post("/api/repair", json={"case_id":"uptime_boundary"}).json()["status"] == "blocked"
        assert client.post("/api/triage", json={"title":"Network switch offline",
                     "description":"Office network is down"}).status_code == 200
        assert client.get("/api/runs").status_code == 200


def test_default_private_protects_all_run_endpoints(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="s3cret", public_demo=False)
    with TestClient(app) as client:
        assert client.get("/api/runs").status_code == 401
        assert client.post("/api/triage", json={"title":"Fiber uplink offline",
                     "description":"Fiber link appears down"}).status_code == 401
        response = client.post("/api/triage", headers={"Authorization":"Bearer s3cret"},
             json={"title":"Fiber uplink offline", "description":"Fiber link appears down"})
        assert response.status_code == 200
        assert client.get("/api/runs", headers={"Authorization":"Bearer s3cret"}).status_code == 200


def test_public_demo_cannot_read_private_operator_records(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="operator-secret", public_demo=True)
    with TestClient(app) as client:
        public = client.post("/api/triage", json={"title":"Demo port offline",
            "description":"A public demo switch is offline", "customer":"Demo"}).json()
        private = client.post("/api/triage", headers={"Authorization":"Bearer operator-secret"},
            json={"title":"Private production incident",
                  "description":"Never disclose this private incident", "customer":"Confidential"}).json()
        assert public["public_demo"] is True
        assert private["public_demo"] is False
        public_list = client.get("/api/runs").json()
        assert [record["id"] for record in public_list] == [public["id"]]
        assert client.get(f"/api/runs/{private['id']}").status_code == 404
        assert client.get(f"/api/runs/{private['id']}/artifact").status_code == 404
        assert client.get(f"/api/runs/{public['id']}").status_code == 200
        headers={"Authorization":"Bearer operator-secret"}
        assert len(client.get("/api/runs", headers=headers).json()) == 2
        assert client.get(f"/api/runs/{private['id']}", headers=headers).status_code == 200
        assert client.get(f"/api/runs/{private['id']}/artifact", headers=headers).status_code == 200


def test_ticket_lifecycle_persistent_and_hash_chain(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="", public_demo=True)
    with TestClient(app) as client:
        run = client.post("/api/triage", json={"title": "Fiber backbone offline",
            "description": "The public demo link is offline", "customer": "Example property"}).json()
        ticket_id = run["ticket_id"]
        ticket = client.get(f"/api/tickets/{ticket_id}").json()
        assert ticket["status"] == "open" and ticket["priority"] == "P1"
        assert ticket["evidence_chain_valid"]
        first = client.post(f"/api/tickets/{ticket_id}/action", json={
            "action": "acknowledge", "note": "Technician accepted the call and checked port state"})
        assert first.status_code == 200
        assert first.json()["status"] == "in_progress" and first.json()["evidence_chain_valid"]
        assert client.post(f"/api/tickets/{ticket_id}/action", json={
            "action": "acknowledge", "note": "This repeated action must be blocked"}).status_code == 409
        resolved = client.post(f"/api/tickets/{ticket_id}/action", json={
            "action": "resolve", "note": "Operator attests link recovery after optical check"})
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved" and resolved.json()["evidence_chain_valid"]
        assert len(resolved.json()["history"]) == 3
        assert resolved.json()["history"][-1]["details"]["verification"] == "operator_attested"
        reopened = client.post(f"/api/tickets/{ticket_id}/action", json={
            "action": "reopen", "note": "Link is intermittent and needs further review"})
        assert reopened.status_code == 200 and reopened.json()["evidence_chain_valid"]
        assert reopened.json()["status"] == "open"
        board = client.get("/api/tickets").json()
        assert board[0]["id"] == ticket_id and board[0]["status"] == "open"
        assert board[0]["run_id"] == run["id"]


def test_private_tickets_are_hidden_from_public_demo(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="operator-secret", public_demo=True)
    with TestClient(app) as client:
        public = client.post("/api/triage", json={"title": "Demo uplink offline",
            "description": "The demo is entirely synthetic"}).json()
        private = client.post("/api/triage", headers={"Authorization":"Bearer operator-secret"},
            json={"title": "Sensitive backhaul offline", "description": "Customer private router secrets"}).json()
        public_board = client.get("/api/tickets").json()
        assert [ticket["id"] for ticket in public_board] == [public["ticket_id"]]
        assert client.get(f"/api/tickets/{private['ticket_id']}").status_code == 404
        assert client.post(f"/api/tickets/{private['ticket_id']}/action", json={
            "action":"acknowledge", "note":"Unauthorized public update attempt"}).status_code == 404
        headers={"Authorization":"Bearer operator-secret"}
        assert len(client.get("/api/tickets", headers=headers).json()) == 2
        assert client.get(f"/api/tickets/{private['ticket_id']}", headers=headers).status_code == 200
        assert client.post(f"/api/tickets/{private['ticket_id']}/action", headers=headers,
            json={"action":"acknowledge", "note":"Operator privately acknowledged the incident"}).status_code == 200


def test_independent_run_verification_detects_artifact_tamper(tmp_path):
    from inneros_agent_rush.core import verify_run_integrity
    engine = new_engine(tmp_path)
    record = engine.run_triage("Uplink SFP offline", "Fiber switch port lost optical signal", "Fictional demo")
    verification = verify_run_integrity(record)
    assert verification["verified"]
    assert verification["artifact_integrity_valid"] is True
    record["artifact"]["content"] = "maliciously altered report"
    broken = verify_run_integrity(record)
    assert broken["evidence_chain_valid"] is True
    assert broken["artifact_integrity_valid"] is False
    assert broken["verified"] is False


def test_verification_endpoint_respects_tenant_visibility(tmp_path):
    app = create_app(new_engine(tmp_path), auth_token="operator-secret", public_demo=True)
    with TestClient(app) as client:
        private = client.post("/api/triage", headers={"Authorization": "Bearer operator-secret"}, json={
            "title": "Private router offline", "description": "Confidential customer network down"}).json()
        public = client.post("/api/triage", json={
            "title": "Demo router offline", "description": "Synthetic demo router network is down"}).json()
        assert client.get(f"/api/runs/{private['id']}/verify").status_code == 404
        data = client.get(f"/api/runs/{public['id']}/verify").json()
        assert data["verified"] is True
        assert data["event_count"] == 6
        assert data["final_evidence_hash"] == public["events"][-1]["hash"]
        assert client.get(f"/api/runs/{private['id']}/verify", headers={
            "Authorization": "Bearer operator-secret"}).status_code == 200


def test_code_repair_cannot_be_marked_completed_without_cleanup(tmp_path):
    from inneros_agent_rush.runner import ExecutionResult
    class MissingCleanup:
        def ready(self): return True
        def run(self, code, assertions):
            return ExecutionResult(False, 2, "", "AssertionError", False,
                                   cleanup_verified=None) if "minutes <= 5" in code else \
                   ExecutionResult(True, 0, "ASSERTIONS_PASSED", "", False,
                                   cleanup_verified=None)
    report = new_engine(tmp_path, MissingCleanup()).run_repair("uptime_boundary")
    assert report["status"] == "needs_review"
    assert report["execution"]["candidate"]["passed"] is True
    assert report["execution"]["candidate"]["cleanup_verified"] is None
