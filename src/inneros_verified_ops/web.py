"""Stdlib HTTP web server for InnerOS Verified Operations v0.6.0.
Provides REST API and high-polish Judge Console for Vultr Agent Rush 2026.
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import platform
import socket
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .containment import LAB
from .engine import ENGINE, IncidentEngineError, InvalidStateTransitionError, UnauthorizedRemediationError
from . import bridge_client

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
REVOKED_TOKENS = frozenset({
    "inneros-ops-token-bellini-2026",
    "sec_ops_vultr_58085a2638f64246547b956c617e6492",
})


class VerifiedOpsHandler(BaseHTTPRequestHandler):
    server_version = "InnerOS-Verified-Ops/0.6.0"

    def _write_response(
        self,
        status: int,
        content: bytes,
        mime: str = "application/json; charset=utf-8",
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
        )
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, obj: dict | list) -> None:
        self._write_response(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        path = parts.path

        if path in ("", "/"):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/judge")
            self.end_headers()
            return

        if path == "/judge":
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_bytes()
                self._write_response(HTTPStatus.OK, content, mime="text/html; charset=utf-8")
                return
            self._write_response(HTTPStatus.NOT_FOUND, b"Judge console file not found", mime="text/plain")
            return

        if path.startswith("/static/"):
            rel_path = path[len("/static/") :]
            target = (STATIC_DIR / rel_path).resolve()
            if target.exists() and STATIC_DIR in target.parents:
                mime, _ = mimetypes.guess_type(str(target))
                self._write_response(
                    HTTPStatus.OK,
                    target.read_bytes(),
                    mime=mime or "application/octet-stream",
                )
                return
            self._write_response(HTTPStatus.NOT_FOUND, b"Asset not found", mime="text/plain")
            return

        if path == "/health":
            b_health = bridge_client.check_bridge_health()
            self._json(
                HTTPStatus.OK,
                {
                    "status": "HEALTHY",
                    "version": "0.6.0",
                    "service": "inneros-verified-operations",
                    "hostname": socket.gethostname(),
                    "platform": platform.platform(),
                    "python_version": sys.version.split()[0],
                    "total_incidents": len(ENGINE.list_incidents()),
                    "cloud_provider": "Vultr (Miami / Cloud Compute)",
                    "inneros_bridge": "ONLINE" if b_health.get("status") == "HEALTHY" else "STANDALONE",
                    "inference_engine": "Local SRE Model / Sandboxed Evaluator",
                },
            )
            return

        if path == "/api/live/status":
            auth_header = self.headers.get("Authorization", "")
            scheme, _, token_candidate = auth_header.partition(" ")
            token_candidate = token_candidate.strip()
            is_op = (
                bool(token_candidate)
                and token_candidate not in REVOKED_TOKENS
                and bool(bridge_client.INNEROS_OPS_TOKEN)
                and hmac.compare_digest(token_candidate, bridge_client.INNEROS_OPS_TOKEN)
            )
            b_health = bridge_client.check_bridge_health()
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "authenticated": is_op,
                    "mode": "authenticated_live_ops" if is_op else "public_demo",
                    "bridge": b_health if is_op else {"status": b_health.get("status", "UNAVAILABLE")},
                    "sites": {
                        "bellini": {"site_id": "bellini-i-ii", "targets": 14, "mode": "read_only_icmp_tcp"},
                        "home_pcdoctor_lab": {"site_id": "home_pcdoctor_lab", "devices": 92, "source": "home_assistant"},
                    } if is_op else {
                        "scenario_fiber": {"id": "scenario_fiber", "label": "Escenario A: Enlace SFP1 (Sandbox)", "type": "synthetic"},
                        "scenario_iot": {"id": "scenario_iot", "label": "Escenario B: Controladores IoT (Sandbox)", "type": "synthetic"}
                    },
                    "local_ai": {
                        "model": "QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ" if is_op else "Sandboxed Evaluator",
                        "status": "active_on_amd15" if is_op else "active",
                        "cost": "$0.00",
                    },
                },
            )
            return

        if path.startswith("/api/private/ops/ticket/"):
            auth_header = self.headers.get("Authorization", "")
            scheme, _, token_candidate = auth_header.partition(" ")
            token_candidate = token_candidate.strip()

            if token_candidate in REVOKED_TOKENS:
                self._json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "Token revoked: compromised credential rejected by security policy"},
                )
                return

            expected_token = bridge_client.INNEROS_OPS_TOKEN
            if (
                not expected_token
                or scheme.lower() != "bearer"
                or token_candidate != expected_token
            ):
                self._json(
                    HTTPStatus.UNAUTHORIZED,
                    {
                        "error": "Authentication required for private infrastructure topology",
                        "hint": "Provide valid operator credentials via Authorization: Bearer <token>",
                    },
                )
                return

            tkt_id = path.split("/")[5] if len(path.split("/")) > 5 else ""
            tkt_data = bridge_client.get_ticket(tkt_id)
            if tkt_data.get("ok"):
                self._json(HTTPStatus.OK, tkt_data)
            else:
                self._json(HTTPStatus.NOT_FOUND, tkt_data)
            return

        if path == "/api/incidents":
            incidents = [inc.to_dict() for inc in ENGINE.list_incidents()]
            self._json(HTTPStatus.OK, {"incidents": incidents})
            return

        if path.startswith("/api/incidents/"):
            inc_id = path.split("/")[3]
            try:
                inc = ENGINE.get_incident(inc_id)
                self._json(HTTPStatus.OK, inc.to_dict())
            except IncidentEngineError as exc:
                self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        if path.startswith("/api/evidence/verify/"):
            hash_val = path.split("/")[4]
            result = ENGINE.verify_hash(hash_val)
            self._json(HTTPStatus.OK, result)
            return

        self._json(HTTPStatus.NOT_FOUND, {"error": f"Path {path} not found"})

    def do_POST(self) -> None:
        parts = urlsplit(self.path)
        path = parts.path
        body = self._body_json()

        if path == "/api/incidents":
            title = body.get("title", "High Latency & Connection Pool Saturation")
            desc = body.get(
                "description",
                "Simulated operational degradation on Vultr Cloud Compute node: pool connections near capacity.",
            )
            sev = body.get("severity", "high")
            signals = body.get(
                "signals",
                {
                    "db_connection_pool_pct": 94.8,
                    "p99_latency_ms": 1420,
                    "active_threads": 64,
                    "error_rate_pct": 19.5,
                },
            )
            inc = ENGINE.create_incident(title, desc, sev, signals)
            self._json(HTTPStatus.CREATED, inc.to_dict())
            return

        if path.startswith("/api/incidents/") and path.endswith("/diagnose"):
            inc_id = path.split("/")[3]
            try:
                inc = ENGINE.diagnose_incident(inc_id)
                self._json(HTTPStatus.OK, inc.to_dict())
            except (IncidentEngineError, InvalidStateTransitionError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if path.startswith("/api/incidents/") and path.endswith("/plan"):
            inc_id = path.split("/")[3]
            try:
                inc = ENGINE.propose_plan(inc_id)
                self._json(HTTPStatus.OK, inc.to_dict())
            except (IncidentEngineError, InvalidStateTransitionError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if path.startswith("/api/incidents/") and path.endswith("/ticket"):
            inc_id = path.split("/")[3]
            assignee = body.get("assignee", "DevOps/SRE Autonomous OnCall")
            try:
                inc = ENGINE.create_ticket(inc_id, assignee)
                self._json(HTTPStatus.OK, inc.to_dict())
            except (IncidentEngineError, InvalidStateTransitionError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if path.startswith("/api/incidents/") and path.endswith("/acknowledge"):
            inc_id = path.split("/")[3]
            ref = body.get("approval_ref", "GRANT-VULTR-RUSH-2026")
            approver = body.get("approver", "Operator-Rafael")
            try:
                inc = ENGINE.acknowledge_plan(inc_id, ref, approver)
                self._json(HTTPStatus.OK, inc.to_dict())
            except (IncidentEngineError, UnauthorizedRemediationError, InvalidStateTransitionError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if path.startswith("/api/incidents/") and path.endswith("/resolve"):
            inc_id = path.split("/")[3]
            try:
                inc = ENGINE.resolve_incident(inc_id)
                self._json(HTTPStatus.OK, inc.to_dict())
            except (IncidentEngineError, UnauthorizedRemediationError, InvalidStateTransitionError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if path == "/api/live/sweep/bellini":
            sweep_data = bridge_client.sweep_bellini()
            if sweep_data.get("sanitized"):
                evidence_hash = sweep_data["sanitized"].get("evidence_sha256")
                if evidence_hash:
                    ENGINE.register_external_receipt(evidence_hash, {
                        "incident_id": "BELLINI-LIVE-SWEEP",
                        "ticket_id": "TKT-PENDING",
                    })
                self._json(HTTPStatus.OK, sweep_data["sanitized"])
            else:
                self._json(HTTPStatus.BAD_GATEWAY, sweep_data)
            return

        if path == "/api/live/sweep/home":
            home_data = bridge_client.sweep_home()
            if home_data.get("sanitized"):
                evidence_hash = home_data["sanitized"].get("evidence_sha256")
                if evidence_hash:
                    ENGINE.register_external_receipt(evidence_hash, {
                        "incident_id": "HOME-PCDOCTOR-LAB-SWEEP",
                        "ticket_id": "TKT-PENDING",
                    })
                self._json(HTTPStatus.OK, home_data["sanitized"])
            else:
                self._json(HTTPStatus.BAD_GATEWAY, home_data)
            return

        if path == "/api/live/diagnose":
            prompt = body.get("prompt", "Analyze network telemetry from Bellini sweep.")
            diag_res = bridge_client.diagnose_telemetry(prompt)
            self._json(HTTPStatus.OK, diag_res)
            return

        if path == "/api/live/ticket":
            site_id = body.get("site_id", "bellini-i-ii")
            client_id = body.get("client_id", "bellini")
            anomaly = body.get("anomaly", {})
            evidence_hash = body.get("evidence_hash", "")
            diagnosis = body.get("diagnosis", "")
            recs = body.get("recommendations", [])

            tkt_res = bridge_client.create_operational_ticket(
                site_id=site_id,
                client_id=client_id,
                anomaly=anomaly,
                evidence_hash=evidence_hash,
                diagnosis=diagnosis,
                recommendations=recs,
            )
            if tkt_res.get("ok"):
                tkt = tkt_res["ticket"]
                if evidence_hash:
                    ENGINE.register_external_receipt(evidence_hash, {
                        "incident_id": tkt.get("ticket_id"),
                        "ticket_id": tkt.get("ticket_id"),
                    })
                self._json(HTTPStatus.CREATED, tkt_res)
            else:
                self._json(HTTPStatus.BAD_GATEWAY, tkt_res)
            return

        if path.startswith("/api/live/ticket/") and path.endswith("/notify"):
            tkt_id = path.split("/")[4]
            notify_res = bridge_client.notify_oncall(tkt_id)
            self._json(HTTPStatus.OK if notify_res.get("ok") else HTTPStatus.BAD_GATEWAY, notify_res)
            return

        if path.startswith("/api/live/ticket/") and path.endswith("/ack"):
            tkt_id = path.split("/")[4]
            ack_res = bridge_client.acknowledge_ticket(tkt_id)
            self._json(HTTPStatus.OK if ack_res.get("ok") else HTTPStatus.BAD_GATEWAY, ack_res)
            return

        if path.startswith("/api/live/ticket/") and path.endswith("/recheck"):
            tkt_id = path.split("/")[4]
            recheck_res = bridge_client.recheck_ticket(tkt_id)
            self._json(HTTPStatus.OK if recheck_res.get("ok") else HTTPStatus.BAD_GATEWAY, recheck_res)
            return

        if path == "/api/containment/run":
            res = LAB.run_scenarios()
            self._json(HTTPStatus.OK, res)
            return

        self._json(HTTPStatus.NOT_FOUND, {"error": f"POST endpoint {path} not found"})


def create_server(host: str = "0.0.0.0", port: int = 8792) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), VerifiedOpsHandler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8792"))
    srv = create_server("0.0.0.0", port)
    print(f"InnerOS Verified Operations v0.6.0 running on http://0.0.0.0:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down cleanly...")
        srv.server_close()
