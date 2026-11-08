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
    srv = web.create_server("127.0.0.1", 0)
    port = srv.server_port

    import threading, urllib.request, urllib.error
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    url = f"http://127.0.0.1:{port}/api/private/ops/ticket/TKT-TEST-001"
    # Unauthenticated request must return 401
    try:
        urllib.request.urlopen(url)
        assert False, "Expected 401 Unauthorized"
    except urllib.error.HTTPError as exc:
        assert exc.code == 401

    # Authenticated request with token query param
    auth_url = f"{url}?token={bridge_client.INNEROS_OPS_TOKEN}"
    with patch("inneros_verified_ops.bridge_client.get_ticket", return_value={"ok": True, "ticket": {"ticket_id": "TKT-TEST-001"}}):
        with urllib.request.urlopen(auth_url) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["ok"] is True
            assert data["ticket"]["ticket_id"] == "TKT-TEST-001"

    srv.shutdown()
    srv.server_close()
