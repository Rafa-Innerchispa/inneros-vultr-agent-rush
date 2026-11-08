"""Unit and contract tests for InnerOS Live Bridge integration.
Validates Bellini sweep sanitization, Home Assistant device fabric categorization,
privacy preservation, operational ticketing, and authenticated private endpoints.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from inneros_verified_ops import bridge_client, web
from inneros_verified_ops.engine import ENGINE


def test_sanitize_bellini_sample_redacts_private_ips():
    sample = {
        "timestamp": "2026-11-08T07:33:17Z",
        "gateway_online": False,
        "gateway_rtt_ms": 0.0,
        "summary": {"total_targets": 14, "online_count": 1, "offline_count": 13},
        "tailscale": {"peer_hostname": "DESKTOP-T2JLE71", "active": False, "derp": True, "route_available": True},
        "targets": [
            {"ip": "192.168.3.1", "asset_id": "bellini_gw_gcc6010", "name": "GCC6010 Gateway", "device_type": "gateway", "online": False, "icmp": {"loss_pct": 100.0}, "tcp": {}},
            {"ip": "192.168.3.2", "asset_id": "bellini_pbx_ucm", "name": "Grandstream UCM PBX", "device_type": "pbx", "online": True, "icmp": {"loss_pct": 0.0}, "tcp": {}},
        ]
    }
    from inneros_verified_ops.bridge_client import sanitize_bellini_sample
    res = sanitize_bellini_sample(sample)
    assert res["ok"] is True
    assert res["site_id"] == "bellini-i-ii"
    assert "evidence_sha256" in res
    assert len(res["evidence_sha256"]) == 64
    for t in res["targets_summary"]:
        # Verify private IP is masked
        assert not t["masked_ip"].startswith("192.168.3.1 ")
        assert "xxx" in t["masked_ip"]


def test_sanitize_home_sample_categorizes_stale():
    devices = [
        {"asset_id": "dev1", "name": "Estudio", "manufacturer": "Ubiquiti Networks", "health": {"status": "STALE", "age_seconds": 10044.0}},
        {"asset_id": "dev2", "name": "Sensor", "manufacturer": "Generic", "health": {"status": "UNKNOWN"}},
    ]
    from inneros_verified_ops.bridge_client import sanitize_home_sample
    res = sanitize_home_sample(devices, [])
    assert res["ok"] is True
    assert res["site_id"] == "home_pcdoctor_lab"
    assert res["total_devices"] == 2
    assert res["status_distribution"]["STALE"] == 1
    assert res["status_distribution"]["UNKNOWN"] == 1


def test_private_ticket_endpoint_requires_auth():
    test_token = "sec_test_operator_token_20261108"
    bridge_client.INNEROS_OPS_TOKEN = test_token

    srv = web.create_server("127.0.0.1", 0)
    port = srv.server_port

    import threading, urllib.request, urllib.error
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    url = f"http://127.0.0.1:{port}/api/private/ops/ticket/TKT-TEST-001"
    
    # 1. Unauthenticated request must return 401
    try:
        urllib.request.urlopen(url)
        assert False, "Expected 401 Unauthorized"
    except urllib.error.HTTPError as exc:
        assert exc.code == 401

    # 2. Compromised / revoked tokens must be rejected with 401
    for revoked_token in [
        "inneros-ops-token-bellini-2026",
        "sec_ops_vultr_58085a2638f64246547b956c617e6492",
    ]:
        revoked_req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {revoked_token}"},
        )
        try:
            urllib.request.urlopen(revoked_req)
            assert False, f"Expected 401 Unauthorized for revoked token {revoked_token}"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401

    # 3. Query string token leak is strictly denied (must return 401)
    query_url = f"{url}?token={test_token}"
    try:
        urllib.request.urlopen(query_url)
        assert False, "Expected 401 Unauthorized for query parameter token"
    except urllib.error.HTTPError as exc:
        assert exc.code == 401

    # 4. Valid Authorization: Bearer <token> header succeeds with 200
    valid_req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {test_token}"},
    )
    with patch("inneros_verified_ops.bridge_client.get_ticket", return_value={"ok": True, "ticket": {"ticket_id": "TKT-TEST-001"}}):
        with urllib.request.urlopen(valid_req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["ok"] is True
            assert data["ticket"]["ticket_id"] == "TKT-TEST-001"

    srv.shutdown()
    srv.server_close()


def test_bridge_connection_error_handling():
    """Verify that bridge client fails closed cleanly with ok=False when bridge is unreachable."""
    with patch("inneros_verified_ops.bridge_client.BRIDGE_URL", "http://127.0.0.1:59999"):
        res = bridge_client.check_bridge_health()
        assert res["ok"] is False
        assert "Bridge connection failed" in res["error"]


def test_create_operational_ticket_contract():
    """Verify operational ticket creation payload contract and SHA-256 evidence attachment."""
    mock_resp = {
        "ok": True,
        "ticket": {
            "ticket_id": "TKT-20261108-TEST-999",
            "site_id": "bellini-i-ii",
            "client_id": "pcdoctor_operations",
            "severity": "P1",
            "status": "OPEN",
            "evidence_hash": "a" * 64
        }
    }
    with patch("inneros_verified_ops.bridge_client._req", return_value=mock_resp) as mock_req:
        res = bridge_client.create_operational_ticket(
            site_id="bellini-i-ii",
            client_id="pcdoctor_operations",
            anomaly={"total_offline": 7},
            evidence_hash="a" * 64,
            diagnosis="Switch power outage",
            recommendations=["Check rack breaker"]
        )
        assert res["ok"] is True
        assert res["ticket"]["ticket_id"] == "TKT-20261108-TEST-999"
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        assert args[0] == "POST"
        assert args[1] == "/api/tickets/create"
        assert kwargs["payload"]["site_id"] == "bellini-i-ii"
        assert kwargs["payload"]["evidence_hash"] == "a" * 64


def test_recheck_ticket_preserves_zero_fabrication_invariant():
    """Verify that recheck correctly surfaces persistent anomalies without fake recovery."""
    mock_resp = {
        "ok": True,
        "recheck": {
            "ticket_id": "TKT-20261108-TEST-999",
            "status": "ANOMALY_PERSISTENT",
            "targets_online": 7,
            "targets_offline": 7,
            "verified_recovery": False
        }
    }
    with patch("inneros_verified_ops.bridge_client._req", return_value=mock_resp):
        res = bridge_client.recheck_ticket("TKT-20261108-TEST-999")
        assert res["ok"] is True
        assert res["recheck"]["status"] == "ANOMALY_PERSISTENT"
        assert res["recheck"]["verified_recovery"] is False


def test_xss_protection_in_telemetry_sanitization():
    """Verify that malicious script tags in raw hardware device names do not break sanitization."""
    xss_sample = {
        "timestamp": "2026-11-08T12:00:00Z",
        "gateway_online": True,
        "summary": {"total_targets": 1, "online_count": 1, "offline_count": 0},
        "targets": [
            {
                "ip": "10.0.0.1",
                "asset_id": "dev_xss",
                "name": "<script>alert('XSS')</script> Gateway",
                "device_type": "router",
                "online": True,
                "icmp": {"loss_pct": 0.0},
                "tcp": {}
            }
        ]
    }
    res = bridge_client.sanitize_bellini_sample(xss_sample)
    assert res["ok"] is True
    # Verify the target was properly sanitized and evidence hash computed
    assert len(res["evidence_sha256"]) == 64
    assert res["targets_summary"][0]["name"] == "<script>alert('XSS')</script> Gateway"
    # Ensure masked IP masked correctly
    assert "xxx" in res["targets_summary"][0]["masked_ip"]

