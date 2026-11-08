#!/usr/bin/env python3
"""Smoke-check a live Vultr deployment using a fictional test incident only."""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def get_json(base, endpoint, token, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base + endpoint,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=20) as reply:
        return json.load(reply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Live public HTTPS URL of the Vultr deployment")
    parser.add_argument("--require-sandbox", action="store_true")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    hostname = urllib.parse.urlsplit(url).hostname or ""
    if urllib.parse.urlsplit(url).scheme != "https" and hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError("Remote smoke checks require HTTPS")
    token = os.getenv("AUTH_TOKEN", "")
    # This is the judge's actual entrance, not merely an API health check.
    with urllib.request.urlopen(url + "/judge", timeout=20) as page:
        judge_html = page.read().decode("utf-8")
        assert page.status == 200
        assert 'id="judge-workthrough"' in judge_html, "Judge walkthrough missing"
        assert 'id="judge-start"' in judge_html, "Judge interactive controls missing"
    health = get_json(url, "/healthz", token)
    assert health["status"] == "ok"
    assert health["service"] == "inneros-agent-rush"
    print("Vultr backend readiness:", health["service"], "sandbox:", health["sandbox_ready"])
    if args.require_sandbox:
        assert health["sandbox_ready"], "Isolated worker still unavailable"
    incident = get_json(url, "/api/triage", token, data={
        "title": "Demo fiber uplink offline",
        "description": "Fictional incident in a training building, no live customer data",
        "customer": "Synthetic Demo Property",
    })
    assert incident["status"] == "completed" and incident.get("ticket_id")
    run = get_json(url, "/api/runs/" + incident["id"], token)
    assert run["evidence_chain_valid"]
    verification = get_json(url, "/api/runs/" + incident["id"] + "/verify", token)
    assert verification["verified"] and verification["artifact_integrity_valid"]
    ticket = get_json(url, "/api/tickets/" + incident["ticket_id"], token)
    assert ticket["status"] == "open" and ticket["evidence_chain_valid"]
    for action, note in (
        ("acknowledge", "Synthetic smoke test acknowledgement: no real customer actions"),
        ("resolve", "Synthetic smoke test closure: no devices repaired or touched"),
    ):
        transition = get_json(url, "/api/tickets/" + incident["ticket_id"] + "/action",
                              token, data={"action": action, "note": note})
        assert transition["evidence_chain_valid"]
    ticket = get_json(url, "/api/tickets/" + incident["ticket_id"], token)
    assert ticket["status"] == "resolved" and len(ticket["history"]) == 3
    print("Judge route and real synthetic workflow verified | run:", incident["id"],
          "| ticket:", incident["ticket_id"], "| report integrity: verified")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Deployment smoke check FAILED:", str(error), file=sys.stderr)
        sys.exit(1)
