"""Bridge Client for InnerOS Verified Operations on Vultr.
Connects the Vultr FastAPI web runtime to the InnerOS local bridge socket (127.0.0.1:8795)
tunnelled from AMD 1.5. Provides live Bellini sweeps, Home Assistant inventory,
Qwen 30B LLM diagnosis, MongoDB operational ticketing, and internal agent messaging.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

BRIDGE_URL = os.environ.get("INNEROS_BRIDGE_URL", "http://127.0.0.1:8795")
INNEROS_OPS_TOKEN = os.environ.get("INNEROS_OPS_TOKEN", "")


def sanitize_bellini_sample(sample: dict) -> dict:
    """Sanitizes Bellini network sweep for public view: redacts private IPs & internal topology."""
    import hashlib
    redacted_targets = []
    for t in sample.get("targets", []):
        masked_ip = f"192.168.3.xxx (Device #{t.get('asset_id', '')[-3:]})"
        redacted_targets.append({
            "asset_id": t.get("asset_id"),
            "role": t.get("device_type", "host").upper(),
            "name": t.get("name"),
            "segment": t.get("segment"),
            "online": t.get("online", False),
            "icmp_loss_pct": t.get("icmp", {}).get("loss_pct"),
            "tcp_responding": any(v.get("open") for v in t.get("tcp", {}).values()),
            "masked_ip": masked_ip
        })

    raw_json = json.dumps(sample, sort_keys=True)
    evidence_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    return {
        "ok": True,
        "site_id": "bellini-i-ii",
        "site_label": "Bellini Campus Core & Access Fabric",
        "timestamp": sample.get("timestamp"),
        "gateway_online": sample.get("gateway_online", False),
        "gateway_rtt_ms": sample.get("gateway_rtt_ms", 0.0),
        "summary": sample.get("summary", {}),
        "tailscale_status": {
            "peer_hostname": "DESKTOP-T2JLE71",
            "active": sample.get("tailscale", {}).get("active", False),
            "derp_relay": sample.get("tailscale", {}).get("derp", False),
            "route_available": sample.get("tailscale", {}).get("route_available", True),
        },
        "evidence_sha256": evidence_hash,
        "targets_count": len(redacted_targets),
        "targets_summary": redacted_targets,
    }


def sanitize_home_sample(devices: list[dict], blockers: list[dict]) -> dict:
    """Sanitizes Home Assistant device fabric inventory."""
    import hashlib, datetime
    status_counts = {"UNKNOWN": 0, "STALE": 0, "ONLINE": 0, "OFFLINE": 0}
    unifi_list = []
    for d in devices:
        st = d.get("health", {}).get("status", "UNKNOWN")
        status_counts[st] = status_counts.get(st, 0) + 1
        mfr = str(d.get("manufacturer") or "").lower()
        if "ubiquiti" in mfr or "unifi" in str(d.get("name") or "").lower():
            unifi_list.append({
                "asset_id": d.get("asset_id"),
                "name": d.get("name"),
                "model": d.get("model"),
                "status": st,
                "age_seconds": d.get("health", {}).get("age_seconds"),
                "observed_at": d.get("health", {}).get("observed_at"),
            })

    raw_json = json.dumps({"devices": devices, "blockers": blockers}, sort_keys=True, default=str)
    evidence_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    return {
        "ok": True,
        "site_id": "home_pcdoctor_lab",
        "site_label": "Casa / PC Doctor Lab",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_devices": len(devices),
        "status_distribution": status_counts,
        "unifi_monitored_devices": unifi_list,
        "blockers": blockers,
        "evidence_sha256": evidence_hash,
    }


def _req(method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 35.0) -> Dict[str, Any]:
    url = f"{BRIDGE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
            return {"ok": False, "status_code": exc.code, "error": err_body}
        except Exception:
            return {"ok": False, "status_code": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"Bridge connection failed ({BRIDGE_URL}): {str(exc)}"}


def check_bridge_health() -> Dict[str, Any]:
    return _req("GET", "/health", timeout=5.0)


def sweep_bellini() -> Dict[str, Any]:
    """Triggers a real live ICMP/TCP/Tailscale sweep across all 14 Bellini targets."""
    return _req("POST", "/api/sweep/bellini", timeout=35.0)


def sweep_home() -> Dict[str, Any]:
    """Triggers a real live inventory of Home Assistant (92 devices) at Casa / PC Doctor Lab."""
    return _req("POST", "/api/sweep/home", timeout=15.0)


def diagnose_telemetry(prompt: str) -> Dict[str, Any]:
    """Executes local LLM reasoning via Qwen 30B vLLM on AMD 1.5."""
    return _req("POST", "/api/diagnose", payload={"prompt": prompt}, timeout=30.0)


def create_operational_ticket(
    site_id: str,
    client_id: str,
    anomaly: Dict[str, Any],
    evidence_hash: str,
    diagnosis: str,
    recommendations: list[str],
) -> Dict[str, Any]:
    """Creates a real private operational ticket in InnerOS MongoDB."""
    payload = {
        "site_id": site_id,
        "client_id": client_id,
        "anomaly": anomaly,
        "evidence_hash": evidence_hash,
        "diagnosis": diagnosis,
        "recommendations": recommendations,
    }
    return _req("POST", "/api/tickets/create", payload=payload, timeout=10.0)


def notify_oncall(ticket_id: str) -> Dict[str, Any]:
    """Dispatches a real internal alert to PC Doctor on-call (rafael) via agent messaging."""
    return _req("POST", f"/api/tickets/{ticket_id}/notify", timeout=10.0)


def acknowledge_ticket(ticket_id: str) -> Dict[str, Any]:
    """Registers operator ACK for the operational ticket in MongoDB."""
    return _req("POST", f"/api/tickets/{ticket_id}/ack", timeout=10.0)


def recheck_ticket(ticket_id: str) -> Dict[str, Any]:
    """Executes a real follow-up sweep to verify if the incident persists or recovered."""
    return _req("POST", f"/api/tickets/{ticket_id}/recheck", timeout=35.0)


def get_ticket(ticket_id: str) -> Dict[str, Any]:
    """Fetches full private ticket details from InnerOS MongoDB."""
    return _req("GET", f"/api/tickets/{ticket_id}", timeout=10.0)
