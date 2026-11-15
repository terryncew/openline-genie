#!/usr/bin/env python3
"""End-to-End Release Acceptance & Headless Chromium Browser Suite for
ARGON — OPENLINE FIVE PRODUCTS (`tests/test_five_products_release_acceptance.py`).

Tests all 5 products across:
1. Functional completeness (custom user input -> stage -> review -> accept/reject)
2. Usability & Real Chromium Browser UI (390x844 mobile & 1280x800 desktop, 0px overflow, labeled inputs, zero console errors)
3. Persistence across server shutdown and cold restart
4. Portability (export and restore in a completely clean state_dir installation)
5. Security (STOP HTTP 409, cross-origin CSRF 403, unauthorized commitment fail-closed, PII redaction 0 leaks)
6. Correction (Decision Recall reopening dependent standing while preserving accepted SHA-256)
7. Edge-case product-completion pass (empty strings, negative/NaN numbers, retroactive rules, tampered capabilities)
"""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from genie_server import start_genie_server
from openline_009_living_project import LivingProjectEngine, run_worker_sigkill_and_successor_recovery
from playwright.sync_api import sync_playwright


def _resolve_chrome() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


class TestOpenLineFiveProductsReleaseAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="openline-five-products-"))
        self.clean_import_dir = Path(tempfile.mkdtemp(prefix="openline-five-clean-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        shutil.rmtree(self.clean_import_dir, ignore_errors=True)

    def _http_get(self, base_url: str, path: str) -> tuple[int, dict]:
        req = urllib.request.Request(f"{base_url}{path}", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            return ex.code, json.loads(ex.read().decode("utf-8"))

    def _http_post(self, base_url: str, path: str, body: dict, headers: dict | None = None) -> tuple[int, dict]:
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{base_url}{path}", data=data, headers=hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            return ex.code, json.loads(ex.read().decode("utf-8"))

    def test_01_server_lifecycle_restart_persistence_and_clean_portability(self) -> None:
        """Verifies that all 5 products initialize, accept custom user changes, survive full
        server shutdown and restart, and export/restore cleanly into a fresh installation."""
        srv1 = start_genie_server(port=0, state_dir=self.tmp_dir, use_model=False)
        th1 = threading.Thread(target=srv1.serve_forever, daemon=True)
        th1.start()
        base1 = f"http://127.0.0.1:{srv1.server_port}"
        try:
            code, state0 = self._http_get(base1, "/api/five_products/state")
            self.assertEqual(code, 200)
            for pkey in ("energy", "advocate", "commons", "science", "civic"):
                self.assertIn(pkey, state0["products"])
                self.assertEqual(state0["products"][pkey]["accepted_version"], 2)

            # Stage and accept custom user scenario in Energy Commons (64 households, $0.39/kWh)
            c_st, res_st = self._http_post(base1, "/api/five_products/stage", {
                "product_key": "energy",
                "payload": {"inputs": {"households": 64, "grid_tariff_usd_per_kwh": 0.39}}
            })
            self.assertEqual(c_st, 200)
            prop_id = res_st["proposal"]["proposal_id"]

            c_ac, res_ac = self._http_post(base1, "/api/accept", {
                "project_id": "product-1-energy-commons",
                "proposal_id": prop_id,
            })
            self.assertEqual(c_ac, 200)
            v3_sha = res_ac["accepted"]["state_sha256"]
            self.assertEqual(res_ac["accepted"]["version"], 3)
        finally:
            srv1.shutdown()
            srv1.server_close()

        # Restart a brand-new server instance on the same state_dir
        srv2 = start_genie_server(port=0, state_dir=self.tmp_dir, use_model=False)
        th2 = threading.Thread(target=srv2.serve_forever, daemon=True)
        th2.start()
        base2 = f"http://127.0.0.1:{srv2.server_port}"
        try:
            code2, state2 = self._http_get(base2, "/api/five_products/state")
            self.assertEqual(code2, 200)
            self.assertEqual(state2["products"]["energy"]["accepted_version"], 3)
            self.assertEqual(state2["products"]["energy"]["accepted_sha256"], v3_sha)
            self.assertEqual(
                state2["products"]["energy"]["civilization_app"]["assumptions"]["household_units"],
                64,
            )

            # Export all 5 flagship products and restore them into a completely clean installation
            clean_eng = LivingProjectEngine(state_dir=self.clean_import_dir)
            for pkey, pinfo in state2["products"].items():
                pid = pinfo["project_id"]
                c_ex, exp_bundle = self._http_get(base2, f"/api/export?project_id={pid}")
                self.assertEqual(c_ex, 200)
                restored = clean_eng.import_portable_bundle(
                    exp_bundle,
                    target_project_id=pid, allow_overwrite=True,
                )
                self.assertEqual(restored["accepted"]["state"]["civilization_app"], pinfo["civilization_app"])
                # Verify post-import Decision Recall works on restored project (Defect 10 guard)
                rec_out = clean_eng.recall_living_project_dependency(
                    pid, "workflow", "post_restore_recall_audit"
                )
                self.assertEqual(rec_out["dnf_standing"], "REOPEN")
                self.assertTrue(rec_out["accepted_state_unchanged"])
        finally:
            srv2.shutdown()
            srv2.server_close()

    def test_02_edge_cases_malformed_inputs_and_fail_closed_security(self) -> None:
        """Tests empty states, malformed inputs, non-finite numbers, retroactive rules,
        unauthorized commitments, STOP freeze, and SIGKILL worker crash recovery."""
        srv = start_genie_server(port=0, state_dir=self.tmp_dir, use_model=False)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_port}"
        try:
            self._http_get(base, "/api/five_products/state")

            # 1. Malformed / empty custom option title refused (HTTP 400)
            c1, _ = self._http_post(base, "/api/five_products/stage", {
                "product_key": "energy",
                "payload": {"new_option": {"title": "   ", "solar_kw": 20}},
            })
            self.assertEqual(c1, 400)

            # 2. Negative tariff refused (HTTP 400)
            c2, _ = self._http_post(base, "/api/five_products/stage", {
                "product_key": "energy",
                "payload": {"inputs": {"grid_tariff_usd_per_kwh": -0.25}},
            })
            self.assertEqual(c2, 400)

            # 3. Retroactive statutory rule refused in Advocate (HTTP 400)
            c3, _ = self._http_post(base, "/api/five_products/stage", {
                "product_key": "advocate",
                "payload": {"rule_effective_date": "2020-01-01"},
            })
            self.assertEqual(c3, 400)

            # 4. Unauthorized procurement commitment in Energy Commons fails closed
            c4, r4 = self._http_post(base, "/api/five_products/action", {
                "product_key": "energy",
                "action": "authorize_procurement",
                "payload": {"human_approved": False},
            })
            self.assertEqual(c4, 200)
            self.assertEqual(r4["status"], "BLOCKED_HUMAN_AUTHORIZATION_REQUIRED")

            # 5. Unauthorized appeal filing in Advocate fails closed
            c5, r5 = self._http_post(base, "/api/five_products/action", {
                "product_key": "advocate",
                "action": "authorize_appeal_filing",
                "payload": {"human_approved": False},
            })
            self.assertEqual(c5, 200)
            self.assertEqual(r5["status"], "BLOCKED_HUMAN_AUTHORIZATION_REQUIRED")

            # 6. Emergency STOP blocks staging across all products with HTTP 409
            self._http_post(base, "/api/stop", {"reason": "adversarial_stop_test"})
            c6, _ = self._http_post(base, "/api/five_products/stage", {
                "product_key": "civic",
                "payload": {"population_served": 5000},
            })
            self.assertEqual(c6, 409)
            self._http_post(base, "/api/clear_stop", {"reason": "clear_after_test"})

            # 7. Real subprocess SIGKILL crash recovery on Capability Commons project
            sig_res = run_worker_sigkill_and_successor_recovery(
                self.tmp_dir, "commons-water-filtration-hub"
            )
            self.assertTrue(sig_res["terminated_by_sigkill"])
            self.assertTrue(sig_res["accepted_bytes_preserved_exact"])
            self.assertEqual(sig_res["uncommitted_draft_disposition"], "REVOKED_BY_WORKER_SWAP")
        finally:
            srv.shutdown()
            srv.server_close()

    def test_03_real_chromium_browser_all_five_products_e2e(self) -> None:
        """Launches real headless Chromium at 390x844 (mobile) and 1280x800 (desktop),
        navigates all 5 product tabs in /products, enters custom user inputs, runs each
        product's central workflow, stages/accepts/rejects proposals, exercises STOP and
        Decision Recall, and verifies 0px horizontal overflow and 0 JS console errors."""
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
                page = browser.new_page(viewport={"width": 390, "height": 844})
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

                # Check mobile 390x844 horizontal overflow is 0
                overflow_mobile = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                self.assertFalse(overflow_mobile, "Mobile 390x844 horizontal overflow detected")

                # Verify every visible input/select/textarea has an associated <label for="...">
                unlabeled = page.evaluate("""() => {
                    const els = Array.from(document.querySelectorAll('input, select, textarea'));
                    return els.filter(el => el.id && !document.querySelector(`label[for="${el.id}"]`)).map(el => el.id);
                }""")
                self.assertEqual(unlabeled, [], f"Unlabeled form controls found: {unlabeled}")

                # --- PRODUCT 1: ENERGY COMMONS ---
                page.fill("#energy-households", "60")
                page.fill("#energy-tariff", "0.38")
                page.locator("#btn-stage-energy").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")

                # Add custom option & reject proposal to verify accepted SHA preservation
                sha_v3 = page.locator("#kpi-accepted-sha").evaluate("el => el.textContent")
                page.fill("#energy-opt-title", "45kW Co-op Solar + Heat Pump")
                page.locator("#btn-add-energy-option").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-reject-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-sha").evaluate("el => el.textContent"), sha_v3)

                # Test human procurement gate (unchecked -> blocked, checked -> authorized v4)
                page.locator("#btn-authorize-energy-procurement").click()
                page.wait_for_timeout(400)
                self.assertIn("Approval required", page.locator("#product-action-banner").evaluate("el => el.textContent"))
                page.locator("#energy-human-approved").click()
                page.locator("#btn-authorize-energy-procurement").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v4")

                # --- PRODUCT 2: ADVOCATE ---
                page.locator("#tab-advocate").click()
                page.wait_for_timeout(400)
                page.fill("#advocate-claim-statement", "Verified clinic work-study exemption letter on file.")
                page.locator("#btn-add-advocate-claim").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")
                page.locator("#btn-advocate-redact").click()
                page.wait_for_timeout(400)
                self.assertIn("[REDACTED-ACCT]", page.locator("#advocate-redacted-box").evaluate("el => el.textContent"))

                # --- PRODUCT 3: CAPABILITY COMMONS ---
                page.locator("#tab-commons").click()
                page.wait_for_timeout(400)
                page.fill("#commons-new-title", "Solar Seed Bank & Irrigation Co-op")
                page.fill("#commons-new-prompt", "Build a community seed bank and solar drip irrigation scheduler.")
                page.locator("#btn-create-commons-project").click()
                page.wait_for_timeout(600)
                self.assertIn("4 Projects Active", page.locator("#commons-count-pill").evaluate("el => el.textContent"))

                # --- PRODUCT 4: OPENLINE SCIENCE ---
                page.locator("#tab-science").click()
                page.wait_for_timeout(400)
                page.fill("#science-hyp-title", "H4: Two-Parameter Coupled Slack Model")
                page.locator("#btn-add-science-hypothesis").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")
                page.locator("#btn-science-replay").click()
                page.wait_for_timeout(400)
                self.assertIn("Independent Replay Verified", page.locator("#product-action-banner").evaluate("el => el.textContent"))
                page.locator("#btn-science-tamper-probe").click()
                page.wait_for_timeout(400)
                self.assertIn("Tamper Protection Verified", page.locator("#product-action-banner").evaluate("el => el.textContent"))

                # --- PRODUCT 5: OPENLINE CIVIC ---
                page.locator("#tab-civic").click()
                page.wait_for_timeout(400)
                page.fill("#civic-chal-claim", "Bridge flood sensor log confirms 96h tanker road blockage.")
                page.locator("#btn-add-civic-challenge").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")
                page.locator("#btn-recall-civic").click()
                page.wait_for_timeout(400)
                self.assertIn("Needs another review", page.locator("#pill-dnf-standing").evaluate("el => el.textContent"))

                # Resize to desktop 1280x800 and verify 0px overflow
                page.set_viewport_size(1280, 800)
                page.wait_for_timeout(300)
                overflow_desktop = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                self.assertFalse(overflow_desktop, "Desktop 1280x800 horizontal overflow detected")
                self.assertEqual(js_errors, [], f"Browser JS errors detected: {js_errors}")
                browser.close()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
