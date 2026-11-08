#!/usr/bin/env python3
"""Exercise the actual judge UI, service ticket controls, and browser states.

Optional dependency: pip install playwright && playwright install chromium.
A local FastAPI backend is started and stopped by this script. No Vultr
hosting is asserted by this check; run the separate public smoke test on Vultr.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


def random_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_service(base: str, process: subprocess.Popen, seconds: float = 20) -> None:
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited prematurely ({process.returncode})")
        try:
            with urlopen(f"{base}/healthz", timeout=1) as response:
                if json.load(response)["status"] == "ok":
                    return
        except Exception:
            time.sleep(0.15)
    raise TimeoutError("FastAPI did not become healthy")


def run_browser_qa(base: str, screenshots: Path | None) -> None:
    from playwright.sync_api import sync_playwright, expect

    with sync_playwright() as playwright:
        chromium_executable = shutil.which("chromium") or shutil.which("chromium-browser")
        options = {"headless": True}
        if chromium_executable:
            options["executable_path"] = chromium_executable
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(f"{base}/judge", wait_until="networkidle")
            expect(page.locator("#judge-workthrough")).to_be_visible()
            expect(page.locator("#judge-mode")).to_contain_text("Live backend")
            expect(page.locator("#run-count")).to_have_text("0")
            expect(page.locator("#judge-verify")).to_be_disabled()
            expect(page.locator("#judge-complete")).to_be_disabled()
            page.locator("#judge-start").click()
            expect(page.locator("#judge-step-one")).to_contain_text("SIMULATED", timeout=15000)
            expect(page.locator("#judge-verify")).to_be_enabled()
            page.locator("#judge-verify").click()
            expect(page.locator("#judge-step-two")).to_contain_text("SIMULATED", timeout=15000)
            expect(page.locator("#judge-proof")).to_contain_text("Verified SHA-256")
            page.locator("#judge-complete").click()
            expect(page.locator("#judge-step-three")).to_contain_text("SIMULATED", timeout=15000)
            # Ticket in board is in OPEN state (no artificial auto-resolve)
            expect(page.locator("#ticket-board .ticket-state").first).to_have_text("open")
            
            # Step 4A: Notify On-Call (simulated channel)
            expect(page.locator("#judge-notify")).to_be_enabled()
            page.locator("#judge-notify").click()
            expect(page.locator("#judge-step-notify-ack")).to_contain_text("SIMULATED", timeout=15000)

            # Step 4B: Technical ACK
            expect(page.locator("#judge-ack-btn")).to_be_enabled()
            page.locator("#judge-ack-btn").click()
            expect(page.locator("#judge-step-notify-ack")).to_contain_text("IN_PROGRESS", timeout=15000)
            expect(page.locator("#ticket-board .ticket-state").first).to_have_text("in progress")

            # Step 5: Recheck (Zero-Fabrication invariant: persistent failure confirmed)
            expect(page.locator("#judge-recheck")).to_be_enabled()
            page.locator("#judge-recheck").click()
            expect(page.locator("#judge-step-four")).to_contain_text("SIMULATED", timeout=15000)
            expect(page.locator("#judge-step-four")).to_contain_text("ANOMALÍA PERSISTENTE")
            expect(page.locator("#ticket-board .ticket-state").first).to_have_text("in progress")

            # Export Report button enabled and verified
            expect(page.locator("#btn-export-report")).to_be_enabled()
            # Probe the new safety front. With no Docker worker in the public web
            # container this must be BLOCKED rather than a fabricated success.
            expect(page.locator("#containment")).to_be_visible()
            page.locator("#containment-case").select_option("network_egress")
            page.locator("#containment-btn").click()
            expect(page.locator("#containment-result")).to_contain_text("BLOCKED", timeout=15000)
            expect(page.locator("#containment-result")).to_contain_text("NOT VERIFIED")
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots / "judge-desktop.png"), full_page=True)

            # Exercise the ticket workflow through the regular UI, not the API.
            page.goto(base, wait_until="networkidle")
            page.locator("#triage-btn").click()
            expect(page.locator("#result-status")).to_have_text("COMPLETED", timeout=15000)
            expect(page.locator("#result-integrity")).to_contain_text("confirmed", timeout=15000)
            ticket = page.locator("#ticket-board .ticket-card").first
            expect(ticket.locator(".ticket-state")).to_have_text("open")
            ticket.locator(".ticket-actions button").click()
            expect(ticket.locator(".ticket-editor")).to_be_visible()
            ticket.locator(".ticket-editor textarea").fill("Operator acknowledged the fictional demonstration scenario")
            ticket.locator(".ticket-editor button[type=submit]").click()
            expect(page.locator("#ticket-board .ticket-state").first).to_have_text("in progress", timeout=15000)
            if screenshots:
                page.screenshot(path=str(screenshots / "workspace-desktop.png"), full_page=True)

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(f"{base}/judge", wait_until="networkidle")
            expect(page.locator("#judge-workthrough")).to_be_visible()
            width = page.evaluate("document.documentElement.scrollWidth")
            assert width <= 390, f"Mobile horizontal overflow: document width {width} > 390"
            if screenshots:
                page.screenshot(path=str(screenshots / "judge-mobile.png"), full_page=True)
            assert not errors, f"Browser JavaScript exceptions: {errors}"
            print("PASS: judge 3-stage workflow, ticket UI, containment fail-closed, integrity, desktop+mobile, no JS exceptions")
        finally:
            browser.close()


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--screenshots", type=Path, help="Optional output folder for QA screenshots")
    parsed = args.parse_args()
    with tempfile.TemporaryDirectory(prefix="inneros-judge-qa-") as temporary:
        port = random_port()
        base = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update({"PUBLIC_DEMO": "1", "AUTH_TOKEN": "", "DB_PATH": str(Path(temporary) / "qa.sqlite")})
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "inneros_agent_rush.main:app",
                                 "--host", "127.0.0.1", "--port", str(port)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
        try:
            wait_for_service(base, proc)
            run_browser_qa(base, parsed.screenshots)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=2)


if __name__ == "__main__":
    main()
