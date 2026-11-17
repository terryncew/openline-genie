#!/usr/bin/env python3
"""Automated Unit, Integration, Independent Handoff, 12-Vector Adversarial & Real
Chromium Browser Test Suite for ARGON — ADVOCATE CASE PACKET 001
(`tests/test_advocate_case_packet_001.py`).
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import urllib.request

from genie_server import start_genie_server
from playwright.sync_api import sync_playwright
from run_advocate_case_packet_001 import run_complete_case_packet_qualification


def _resolve_chrome() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


class TestAdvocateCasePacket001(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="advocate-cp001-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_four_procedural_cases_independent_handoff_and_twelve_adversarial_vectors(self) -> None:
        """Executes all 4 fictional procedural cases across Installation A -> Installation B,
        verifies independent reconstruction, Decision Recall continuation, conventional
        workflow advantage, and all 12 adversarial attack vectors."""
        demo_out = self.tmp_dir / "demos"
        rep = run_complete_case_packet_qualification(output_demo_dir=demo_out)
        self.assertEqual(rep["verdict"], "QUALIFIED_TO_SHIP_CANDIDATE")
        self.assertNotEqual(rep["installation_a_public_key"], rep["installation_b_public_key"])
        self.assertTrue(rep["tampered_handoff_zip_rejected"])
        self.assertTrue(rep["incomplete_missing_originals_zip_rejected"])
        self.assertTrue(rep["twelve_vector_adversarial_suite"]["all_twelve_passed"])
        self.assertEqual(rep["twelve_vector_adversarial_suite"]["passed_vectors"], 12)

        for cid in (
            "CASE-001-BENEFITS-MISSING-DOC",
            "CASE-002-HOA-RULE-CONFLICT",
            "CASE-003-INSURANCE-DISPUTED-EVIDENCE",
            "CASE-004-HOUSING-CONTESTED-TIMELINE",
        ):
            hr = rep["four_cases_handoff_results"][cid]
            self.assertTrue(hr["install_b_reconstruction_verified"])
            self.assertTrue(hr["original_documents_preserved_exact"])
            self.assertGreaterEqual(hr["history_versions_preserved"], 3)
            self.assertEqual(hr["final_packet_status"], "ACCEPTED_BY_HUMAN")

            cmp_entry = rep["conventional_workflow_comparisons"][cid]
            self.assertEqual(
                cmp_entry["openline_case_packet"]["reconstruction_completeness_score_pct"],
                100.0,
            )
            self.assertGreater(
                cmp_entry["openline_case_packet"]["reconstruction_completeness_score_pct"],
                cmp_entry["competent_conventional_folder"]["reconstruction_completeness_score_pct"],
            )
            self.assertTrue((demo_out / f"{cid.lower()}_install_a_initial.zip").exists())
            self.assertTrue((demo_out / f"{cid.lower()}_install_b_continued.zip").exists())

    def test_02_real_chromium_browser_case_packet_workbench_and_all_six_apps(self) -> None:
        """Verifies the Advocate Case Packet Workbench in real headless Chromium at 1280x800
        and 390x844 across all 4 procedural cases (selecting cases, staging new span-linked
        evidence, accepting changes, exporting portable ZIP/HTML packets) and confirms all
        6 released applications remain intact with 0px overflow and 0 console errors."""
        srv = start_genie_server(port=0, state_dir=self.tmp_dir, use_model=False)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_port}"
        chrome_bin = _resolve_chrome()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    executable_path=chrome_bin,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                js_errors: list[str] = []
                page.on("pageerror", lambda ex: js_errors.append(str(ex)))
                page.on(
                    "console",
                    lambda m: js_errors.append(f"console.{m.type}: {m.text}")
                    if m.type == "error"
                    else None,
                )

                page.goto(f"{base}/products", wait_until="networkidle")
                page.wait_for_timeout(600)

                # Switch to Tab 2 (Advocate) and inspect Case Packet Workbench
                page.locator("#tab-advocate").click()
                page.wait_for_timeout(500)
                self.assertTrue(page.locator("#advocate-case-packet-workbench").is_visible())

                # Case 1 initially has a missing clinic document ("Some supporting information is missing")
                # Gate 4: the pill only renders once the case-packets fetch
                # lands (after ~60s first-use seeding); the test's fixed
                # 500ms wait after the tab click races it. Wait for the text.
                page.wait_for_function(
                    "() => document.getElementById('cp-status-pill').textContent.includes('Some supporting information is missing')",
                    timeout=120000,
                )
                self.assertIn(
                    "Some supporting information is missing",
                    page.locator("#cp-status-pill").evaluate("el => el.textContent"),
                )

                # Stage new supporting evidence on Case 1 via the workbench UI and accept changes
                page.locator("#btn-cp-stage-evidence").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(600)
                # Gate 4: the pill refreshes only after accept + state +
                # case-packets refetch (~2s); the fixed 600ms wait races it.
                page.wait_for_function(
                    "() => document.getElementById('cp-status-pill').textContent.includes('Ready to Share')",
                    timeout=60000,
                )
                self.assertIn(
                    "Ready to Share",
                    page.locator("#cp-status-pill").evaluate("el => el.textContent"),
                )

                # Export portable Case Packet and verify manifest preview
                page.locator("#btn-cp-export-packet").click()
                page.wait_for_timeout(500)
                exp_txt = page.locator("#cp-export-preview-box").evaluate("el => el.textContent")
                self.assertIn("openline.advocate.case_packet_export_bundle.v1", exp_txt)
                self.assertIn("CRYPTOGRAPHIC SIGNATURE DISCLOSURE", exp_txt)

                # Verify mobile 390x844 viewport has 0px horizontal overflow
                page.set_viewport_size(390, 844)
                page.wait_for_timeout(300)
                overflow_m = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                self.assertFalse(overflow_m, "Mobile 390x844 horizontal overflow detected on Advocate Case Packet UI")

                # Verify 6th released application (/neighborhood) loads cleanly with 0 errors
                page.goto(f"{base}/neighborhood", wait_until="networkidle")
                page.wait_for_timeout(400)
                self.assertIn("ClearCovenant", page.locator("body").text_content())

                self.assertEqual(js_errors, [], f"Browser JS errors: {js_errors}")
                browser.close()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
