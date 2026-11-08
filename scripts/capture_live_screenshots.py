#!/usr/bin/env python3
"""Capture high-resolution screenshots of InnerOS Verified Operations on Vultr
Desktop (1440x900) and Mobile (390x844).
"""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://45.77.164.161.sslip.io/judge"
TOKEN = "sec_ops_vultr_58085a2638f64246547b956c617e6492"
OUT_DIR = Path("/tmp/vultr-screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # 1. Desktop - Public Demo Mode
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT_DIR / "01_desktop_public_demo.png"), full_page=True)
    print("Captured 01_desktop_public_demo.png")

    # 2. Desktop - Authenticated Real Operations Mode
    # Enter token in session
    page.evaluate(f"""() => {{
        sessionStorage.setItem("inneros_operator_token", "{TOKEN}");
        location.reload();
    }}""")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT_DIR / "02_desktop_operator_authenticated.png"), full_page=True)
    print("Captured 02_desktop_operator_authenticated.png")

    # 3. Desktop - Execute Full 5-Step Real Hardware Walkthrough
    print("Executing Step 1: Live Sweep...")
    page.locator("#judge-start").click()
    page.wait_for_selector("#judge-step-one.pass", timeout=30000)
    page.wait_for_timeout(1000)

    print("Executing Step 2: Qwen 30B Diagnosis...")
    page.locator("#judge-verify").click()
    page.wait_for_selector("#judge-step-two.pass", timeout=40000)
    page.wait_for_timeout(1000)

    print("Executing Step 3: Create Ticket in MongoDB...")
    page.locator("#judge-complete").click()
    page.wait_for_selector("#judge-step-three.pass", timeout=15000)
    page.wait_for_timeout(1000)

    print("Executing Step 4A: Notify On-Call...")
    page.locator("#judge-notify").click()
    page.wait_for_timeout(2000)

    print("Executing Step 4B: Register Human ACK...")
    page.locator("#judge-ack-btn").click()
    page.wait_for_timeout(2000)

    print("Executing Step 5: Physical Hardware Recheck...")
    page.locator("#judge-recheck").click()
    page.wait_for_selector("#judge-step-four.pass", timeout=30000)
    page.wait_for_timeout(1500)

    page.screenshot(path=str(OUT_DIR / "03_desktop_full_ops_pipeline_executed.png"), full_page=True)
    print("Captured 03_desktop_full_ops_pipeline_executed.png")

    # 4. Open Private Topology Modal
    page.locator("#btn-view-topology").click()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT_DIR / "04_desktop_private_topology_modal.png"))
    print("Captured 04_desktop_private_topology_modal.png")
    page.locator("#modal-close").click()
    page.wait_for_timeout(500)

    # 5. Mobile (390x844) Viewport Check
    mobile_page = browser.new_page(viewport={"width": 390, "height": 844})
    mobile_page.goto(URL, wait_until="networkidle")
    mobile_page.evaluate(f"""() => {{
        sessionStorage.setItem("inneros_operator_token", "{TOKEN}");
        location.reload();
    }}""")
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(2000)
    doc_width = mobile_page.evaluate("document.documentElement.scrollWidth")
    print(f"Mobile Document Width: {doc_width}px (Target <= 390px)")
    assert doc_width <= 390, f"Mobile horizontal overflow: {doc_width} > 390"

    mobile_page.screenshot(path=str(OUT_DIR / "05_mobile_operator_dashboard.png"), full_page=True)
    print("Captured 05_mobile_operator_dashboard.png")

    browser.close()
    print("All screenshots successfully captured!")
