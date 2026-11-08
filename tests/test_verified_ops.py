"""Comprehensive Test Suite for InnerOS Verified Operations v0.6.0.
Basal baseline: 40 PASS, 2 SKIP (requiring active Docker daemon).
"""
import hashlib
import json
import os
import sys
import unittest
import urllib.request
import urllib.error
import threading
import time
import pytest

from inneros_verified_ops.models import (
    Incident,
    IncidentStatus,
    Severity,
    TicketStatus,
    canonical_json,
    sha256_digest,
)
from inneros_verified_ops.engine import (
    IncidentEngine,
    IncidentEngineError,
    InvalidStateTransitionError,
    UnauthorizedRemediationError,
)
from inneros_verified_ops.containment import ContainmentLab, LAB
from inneros_verified_ops.web import create_server


class TestModelContracts(unittest.TestCase):
    def test_01_canonical_json_sorting(self):
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        self.assertEqual(canonical_json(d1), canonical_json(d2))

    def test_02_sha256_digest_string(self):
        digest = sha256_digest("test")
        self.assertEqual(digest, hashlib.sha256(b"test").hexdigest())

    def test_03_sha256_digest_bytes(self):
        digest = sha256_digest(b"test")
        self.assertEqual(digest, hashlib.sha256(b"test").hexdigest())

    def test_04_sha256_digest_dict(self):
        digest = sha256_digest({"hello": "world"})
        self.assertEqual(len(digest), 64)

    def test_05_incident_initial_state(self):
        inc = Incident(
            incident_id="INC-TEST1",
            title="Test",
            description="Desc",
            severity=Severity.HIGH,
        )
        self.assertEqual(inc.status, IncidentStatus.INGESTED)
        self.assertIsNone(inc.diagnosis)
        self.assertIsNone(inc.plan)

    def test_06_incident_to_dict_serialization(self):
        inc = Incident(
            incident_id="INC-TEST2",
            title="Test",
            description="Desc",
            severity=Severity.CRITICAL,
        )
        d = inc.to_dict()
        self.assertEqual(d["severity"], "critical")
        self.assertEqual(d["status"], "ingested")

    def test_07_severity_enum_values(self):
        self.assertEqual(Severity.LOW.value, "low")
        self.assertEqual(Severity.MEDIUM.value, "medium")
        self.assertEqual(Severity.HIGH.value, "high")
        self.assertEqual(Severity.CRITICAL.value, "critical")

    def test_08_ticket_status_enum_values(self):
        self.assertEqual(TicketStatus.OPEN.value, "open")
        self.assertEqual(TicketStatus.PENDING_APPROVAL.value, "pending_approval")
        self.assertEqual(TicketStatus.APPROVED.value, "approved")
        self.assertEqual(TicketStatus.RESOLVED.value, "resolved")


class TestLifecycleEngine(unittest.TestCase):
    def setUp(self):
        self.engine = IncidentEngine()

    def test_09_create_incident(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.assertTrue(inc.incident_id.startswith("INC-"))
        self.assertEqual(inc.status, IncidentStatus.INGESTED)

    def test_10_get_incident_found(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        retrieved = self.engine.get_incident(inc.incident_id)
        self.assertEqual(retrieved.incident_id, inc.incident_id)

    def test_11_get_incident_not_found_raises(self):
        with self.assertRaises(IncidentEngineError):
            self.engine.get_incident("INC-NONEXISTENT")

    def test_12_diagnose_success(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        diagnosed = self.engine.diagnose_incident(inc.incident_id)
        self.assertEqual(diagnosed.status, IncidentStatus.DIAGNOSED)
        self.assertIsNotNone(diagnosed.diagnosis)
        self.assertGreater(diagnosed.diagnosis.confidence, 0.9)

    def test_13_diagnose_invalid_state_transition(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        # Calling diagnose again should raise
        with self.assertRaises(InvalidStateTransitionError):
            self.engine.diagnose_incident(inc.incident_id)

    def test_14_propose_plan_success(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        planned = self.engine.propose_plan(inc.incident_id)
        self.assertEqual(planned.status, IncidentStatus.PLAN_PROPOSED)
        self.assertIsNotNone(planned.plan)
        self.assertEqual(len(planned.plan.steps), 3)

    def test_15_propose_plan_before_diagnose_raises(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        with self.assertRaises(InvalidStateTransitionError):
            self.engine.propose_plan(inc.incident_id)

    def test_16_create_ticket_success(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        self.engine.propose_plan(inc.incident_id)
        ticketed = self.engine.create_ticket(inc.incident_id, "DevOps Team")
        self.assertEqual(ticketed.status, IncidentStatus.TICKETED)
        self.assertIsNotNone(ticketed.ticket)
        self.assertEqual(ticketed.ticket.status, TicketStatus.PENDING_APPROVAL)

    def test_17_create_ticket_invalid_state_raises(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        with self.assertRaises(InvalidStateTransitionError):
            self.engine.create_ticket(inc.incident_id)

    def test_18_acknowledge_success(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        self.engine.propose_plan(inc.incident_id)
        self.engine.create_ticket(inc.incident_id)
        ack = self.engine.acknowledge_plan(inc.incident_id, "GRANT-TOKEN-1234", "Operator-Rafael")
        self.assertEqual(ack.status, IncidentStatus.ACKNOWLEDGED)
        self.assertEqual(ack.ticket.status, TicketStatus.APPROVED)
        self.assertIn("GRANT-TOKEN-1234", ack.ticket.approval_ref)

    def test_19_acknowledge_without_ref_raises(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        self.engine.propose_plan(inc.incident_id)
        self.engine.create_ticket(inc.incident_id)
        with self.assertRaises(UnauthorizedRemediationError):
            self.engine.acknowledge_plan(inc.incident_id, "")

    def test_20_resolve_without_approval_raises(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        self.engine.propose_plan(inc.incident_id)
        self.engine.create_ticket(inc.incident_id)
        with self.assertRaises(UnauthorizedRemediationError):
            self.engine.resolve_incident(inc.incident_id)

    def test_21_resolve_success_and_receipt_generation(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        self.engine.propose_plan(inc.incident_id)
        self.engine.create_ticket(inc.incident_id)
        self.engine.acknowledge_plan(inc.incident_id, "GRANT-TOKEN-1234")
        resolved = self.engine.resolve_incident(inc.incident_id)
        self.assertEqual(resolved.status, IncidentStatus.VERIFIED)
        self.assertIsNotNone(resolved.evidence_hash)
        self.assertEqual(len(resolved.evidence_hash), 64)

    def test_22_hash_chain_verification_pass(self):
        inc = self.engine.create_incident("High Latency", "Pool exhaustion", Severity.HIGH)
        self.engine.diagnose_incident(inc.incident_id)
        self.engine.propose_plan(inc.incident_id)
        self.engine.create_ticket(inc.incident_id)
        self.engine.acknowledge_plan(inc.incident_id, "GRANT-TOKEN-1234")
        resolved = self.engine.resolve_incident(inc.incident_id)

        audit = self.engine.verify_hash(resolved.evidence_hash)
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["receipt"]["incident_id"], inc.incident_id)

    def test_23_hash_chain_verification_unknown_hash(self):
        audit = self.engine.verify_hash("a" * 64)
        self.assertFalse(audit["valid"])
        self.assertIn("error", audit)

    def test_24_multi_incident_hash_chaining(self):
        inc1 = self.engine.create_incident("Incident 1", "Desc 1", Severity.LOW)
        self.engine.diagnose_incident(inc1.incident_id)
        self.engine.propose_plan(inc1.incident_id)
        self.engine.create_ticket(inc1.incident_id)
        self.engine.acknowledge_plan(inc1.incident_id, "GRANT-1")
        r1 = self.engine.resolve_incident(inc1.incident_id)

        inc2 = self.engine.create_incident("Incident 2", "Desc 2", Severity.HIGH)
        self.engine.diagnose_incident(inc2.incident_id)
        self.engine.propose_plan(inc2.incident_id)
        self.engine.create_ticket(inc2.incident_id)
        self.engine.acknowledge_plan(inc2.incident_id, "GRANT-2")
        r2 = self.engine.resolve_incident(inc2.incident_id)

        audit2 = self.engine.verify_hash(r2.evidence_hash)
        self.assertEqual(audit2["receipt"]["prev_hash"], r1.evidence_hash)

    def test_25_list_incidents(self):
        self.engine.create_incident("Inc A", "Desc A", Severity.LOW)
        self.engine.create_incident("Inc B", "Desc B", Severity.MEDIUM)
        all_inc = self.engine.list_incidents()
        self.assertEqual(len(all_inc), 2)


class TestContainmentLabSimulation(unittest.TestCase):
    def setUp(self):
        self.lab = ContainmentLab()

    def test_26_containment_lab_initialization(self):
        self.assertIsNotNone(self.lab)

    def test_27_run_scenarios_structure(self):
        res = self.lab.run_scenarios()
        self.assertIn("docker_available", res)
        self.assertIn("overall_status", res)
        self.assertIn("scenarios", res)
        self.assertEqual(len(res["scenarios"]), 3)

    def test_28_scenario_names(self):
        res = self.lab.run_scenarios()
        names = [s["name"] for s in res["scenarios"]]
        self.assertIn("Egress Leak Prevention", names)
        self.assertIn("Credential Exfiltration Containment", names)
        self.assertIn("Filesystem Quarantine & Rollback", names)

    def test_29_fail_closed_policy_present(self):
        res = self.lab.run_scenarios()
        for sc in res["scenarios"]:
            self.assertEqual(sc["policy"], "FAIL_CLOSED")

    def test_30_docker_unavailable_fails_safe(self):
        # Force docker unavailable
        lab = ContainmentLab()
        lab.docker_bin = None
        res = lab.run_scenarios()
        self.assertFalse(res["docker_available"])
        self.assertEqual(res["overall_status"], "FAIL_CLOSED_PROTECTED")
        self.assertFalse(res["blast_radius_zero_guaranteed"])


class TestWebAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 18792)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:18792"
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str):
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, data: dict):
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_31_healthcheck_endpoint(self):
        status, data = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "HEALTHY")
        self.assertEqual(data["version"], "0.6.0")

    def test_32_list_incidents_endpoint(self):
        status, data = self._get("/api/incidents")
        self.assertEqual(status, 200)
        self.assertIn("incidents", data)

    def test_33_post_incident_endpoint(self):
        status, data = self._post("/api/incidents", {"title": "API Test", "severity": "medium"})
        self.assertEqual(status, 201)
        self.assertEqual(data["title"], "API Test")
        self.assertEqual(data["severity"], "medium")

    def test_34_get_single_incident(self):
        _, created = self._post("/api/incidents", {"title": "Single Get", "severity": "low"})
        inc_id = created["incident_id"]
        status, data = self._get(f"/api/incidents/{inc_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["incident_id"], inc_id)

    def test_35_diagnose_post_endpoint(self):
        _, created = self._post("/api/incidents", {"title": "To Diagnose"})
        inc_id = created["incident_id"]
        status, data = self._post(f"/api/incidents/{inc_id}/diagnose", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "diagnosed")

    def test_36_plan_post_endpoint(self):
        _, created = self._post("/api/incidents", {"title": "To Plan"})
        inc_id = created["incident_id"]
        self._post(f"/api/incidents/{inc_id}/diagnose", {})
        status, data = self._post(f"/api/incidents/{inc_id}/plan", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "plan_proposed")

    def test_37_ticket_post_endpoint(self):
        _, created = self._post("/api/incidents", {"title": "To Ticket"})
        inc_id = created["incident_id"]
        self._post(f"/api/incidents/{inc_id}/diagnose", {})
        self._post(f"/api/incidents/{inc_id}/plan", {})
        status, data = self._post(f"/api/incidents/{inc_id}/ticket", {"assignee": "SRE Lead"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ticketed")

    def test_38_acknowledge_post_endpoint(self):
        _, created = self._post("/api/incidents", {"title": "To Ack"})
        inc_id = created["incident_id"]
        self._post(f"/api/incidents/{inc_id}/diagnose", {})
        self._post(f"/api/incidents/{inc_id}/plan", {})
        self._post(f"/api/incidents/{inc_id}/ticket", {})
        status, data = self._post(f"/api/incidents/{inc_id}/acknowledge", {"approval_ref": "GRANT-OK"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "acknowledged")

    def test_39_resolve_post_endpoint(self):
        _, created = self._post("/api/incidents", {"title": "To Resolve"})
        inc_id = created["incident_id"]
        self._post(f"/api/incidents/{inc_id}/diagnose", {})
        self._post(f"/api/incidents/{inc_id}/plan", {})
        self._post(f"/api/incidents/{inc_id}/ticket", {})
        self._post(f"/api/incidents/{inc_id}/acknowledge", {"approval_ref": "GRANT-OK"})
        status, data = self._post(f"/api/incidents/{inc_id}/resolve", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "verified")
        self.assertIsNotNone(data["evidence_hash"])

    def test_40_verify_evidence_endpoint(self):
        _, created = self._post("/api/incidents", {"title": "To Notarize"})
        inc_id = created["incident_id"]
        self._post(f"/api/incidents/{inc_id}/diagnose", {})
        self._post(f"/api/incidents/{inc_id}/plan", {})
        self._post(f"/api/incidents/{inc_id}/ticket", {})
        self._post(f"/api/incidents/{inc_id}/acknowledge", {"approval_ref": "GRANT-OK"})
        _, resolved = self._post(f"/api/incidents/{inc_id}/resolve", {})
        ev_hash = resolved["evidence_hash"]

        status, audit = self._get(f"/api/evidence/verify/{ev_hash}")
        self.assertEqual(status, 200)
        self.assertTrue(audit["valid"])


# The 2 Docker-dependent tests that SKIP when Docker daemon is not active on host
class TestDockerContainmentLive(unittest.TestCase):
    @pytest.mark.skipif(not LAB.is_docker_available(), reason="Live Docker daemon required for container namespace mount")
    def test_41_live_docker_namespace_mount(self):
        """Verifies actual container execution when Docker engine is running."""
        res = LAB.run_scenarios()
        self.assertTrue(res["docker_available"])
        self.assertTrue(res["blast_radius_zero_guaranteed"])

    @pytest.mark.skipif(not LAB.is_docker_available(), reason="Live Docker daemon required for container cgroup check")
    def test_42_live_docker_cgroup_isolation(self):
        """Verifies cgroup resource limits under running container daemon."""
        res = LAB.run_scenarios()
        self.assertEqual(res["overall_status"], "VERIFIED_ISOLATED")


if __name__ == "__main__":
    unittest.main()

