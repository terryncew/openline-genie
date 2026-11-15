#!/usr/bin/env python3
"""One-off verification: live UI against the REAL model-built bakery
(project genie-model-hearth-crumb-bakery-planner) on port 8798, plus a
real-browser exercise of the exported app. Writes evidence screenshots
and a JSON summary. Not part of the unit suite (it needs the demo state).
"""
import json
import os
import sys
from pathlib import Path

BASE = "http://127.0.0.1:8798"
# Evidence output: override with GENIE_VERIFY_EVIDENCE_DIR; the default
# stays inside this tree (tests/evidence_live).
EV = Path(os.environ.get("GENIE_VERIFY_EVIDENCE_DIR", "") or Path(__file__).resolve().parent / "evidence_live")
EV.mkdir(parents=True, exist_ok=True)

from playwright.sync_api import sync_playwright

summary = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/", wait_until="networkidle")
    page.locator("#wishBakeryBtn").click()
    page.wait_for_selector("#wishScreen", state="hidden", timeout=10000)
    page.wait_for_timeout(500)
    diag = page.evaluate("window.__genieVisualDiagnostics()")
    summary["world"] = {
        "projectId": diag["projectId"],
        "verificationStatus": diag["verificationStatus"],
        "receiverAttested": diag["receiverAttested"],
        "throughput": diag["constraintResonance"]["system_throughput"],
        "bottleneck": diag["constraintResonance"]["bottleneck_id"],
        "opportunities": [(o["id"], o["kind"]) for o in diag["opportunities"]],
    }
    assert diag["verificationStatus"] == "RECEIVER_VERIFIED", diag
    assert diag["constraintResonance"]["system_throughput"] == 174
    page.screenshot(path=str(EV / "rc6_real_bakery_390_world.png"))
    # Explore + accept through the UI.
    page.locator("#quickMoveBtn").click()
    page.wait_for_timeout(600)
    diag = page.evaluate("window.__genieVisualDiagnostics()")
    summary["preview_after_explore"] = diag["constraintResonance"]["system_throughput"]
    assert summary["preview_after_explore"] == 240, diag
    page.locator("#accept").click()
    page.wait_for_timeout(900)
    diag = page.evaluate("window.__genieVisualDiagnostics()")
    summary["baseline_after_accept"] = diag["constraintResonance"]["baseline_throughput"]
    assert summary["baseline_after_accept"] == 240, diag
    page.screenshot(path=str(EV / "rc6_real_bakery_390_accepted.png"))
    assert not errors, errors
    page.close()

    # Exercise the exported runnable app in a real browser.
    app = browser.new_page(viewport={"width": 390, "height": 844})
    app_errors = []
    app.on("pageerror", lambda e: app_errors.append(str(e)))
    app.goto("file:///tmp/rc6_bakery_app.html", wait_until="load")
    app.wait_for_timeout(400)
    title = app.title()
    summary["exported_app_title"] = title
    # Fill the add form completely (the app validates all fields).
    # Date the batch to the app's own default day: the list filters by day.
    today = app.locator("#day").input_value()
    app.locator("#fp").fill("Test Batch")
    app.locator("#fd").fill(today)
    app.locator("#fq").fill("24")
    app.locator("#fo").fill("50")
    app.locator("#ab").click()
    app.wait_for_timeout(300)
    body1 = app.locator("body").inner_text()
    summary["exported_app_shows_new_record"] = "Test Batch" in body1
    app.reload(wait_until="load")
    app.wait_for_timeout(300)
    body2 = app.locator("body").inner_text()
    summary["exported_app_record_persists_after_reload"] = "Test Batch" in body2
    app.screenshot(path=str(EV / "rc6_real_bakery_exported_app.png"))
    assert not app_errors, app_errors
    browser.close()

(EV / "rc6_real_bakery_verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
print("OK")
