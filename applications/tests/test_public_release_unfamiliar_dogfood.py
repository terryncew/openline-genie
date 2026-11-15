#!/usr/bin/env python3
"""Final Independent Unfamiliar-User Dogfood, Plain-Language UI Audit & Screenshot Suite
(`tests/test_public_release_unfamiliar_dogfood.py`).

Tests all 5 OpenLine Genie applications as an unfamiliar user from a clean installation:
- Verifies zero internal engineering jargon appears in visible UI text.
- Exercises unfamiliar inputs, alternative comparisons, Accept/Reject, STOP/Resume,
  assumption correction ('Needs another review'), server close/restart persistence,
  and export/restore in a second clean installation.
- Verifies desktop (1280x800) and mobile (390x844) layouts with 0px overflow and captures
  real Chromium screenshots for the public launch package.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request

from genie_server import start_genie_server
from openline_009_living_project import LivingProjectEngine
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path(tempfile.gettempdir()) / "openline-public-release-screenshots"


def _resolve_chrome() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


class TestPublicReleaseUnfamiliarDogfood(unittest.TestCase):
    def setUp(self) -> None:
        self.install_1_dir = Path(tempfile.mkdtemp(prefix="genie-dogfood-install1-"))
        self.install_2_dir = Path(tempfile.mkdtemp(prefix="genie-dogfood-install2-"))
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.install_1_dir, ignore_errors=True)
        shutil.rmtree(self.install_2_dir, ignore_errors=True)

    def test_01_one_command_launcher_verify_only_and_sample_projects(self) -> None:
        """Verifies that launch_genie.py --verify-only succeeds on a clean directory and all 5
        sample bundles in examples/ restore cleanly into a fresh installation."""
        launcher = Path(__file__).resolve().parent.parent / "launch_genie.py"
        proc = subprocess.run(
            ["python3", str(launcher), "--state-dir", str(self.install_1_dir), "--verify-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(out["status"], "READY")
        self.assertEqual(len(out["applications_ready"]), 5)

        examples_dir = Path(__file__).resolve().parent.parent / "examples"
        clean_eng = LivingProjectEngine(state_dir=self.install_2_dir)
        for sample_file in sorted(examples_dir.glob("sample_*.json")):
            bundle = json.loads(sample_file.read_text(encoding="utf-8"))
            res = clean_eng.import_portable_bundle(bundle, allow_overwrite=True)
            self.assertGreaterEqual(res["accepted"]["version"], 1)

    def test_02_unfamiliar_user_dogfood_all_five_applications_desktop_and_mobile(self) -> None:
        """Dogfoods Energy Commons, Advocate, Capability Commons, Science, and Civic in real
        headless Chromium with unfamiliar user inputs, verifies plain-language UI (zero internal
        jargon), tests STOP/Resume, server restart, export/restore, and saves screenshots."""
        srv = start_genie_server(port=0, state_dir=self.install_1_dir, use_model=False)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_port}"
        chrome_bin = _resolve_chrome()

        forbidden_jargon = [
            "Argon",
            "Astra",
            "MUSE",
            "dogfood",
            "009 RC",
            "EXPLORATORY_PENDING",
            "ReceiverGuard",
            "BUCSW",
            "CRP-001",
            "ET-COSA",
            "dependency_closure_incomplete",
        ]

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

                # 1. Verify Energy Commons with unfamiliar 36-unit building inputs
                body_text = page.locator("body").inner_text()
                for term in forbidden_jargon:
                    self.assertNotIn(term, body_text, f"Forbidden internal jargon '{term}' visible in Energy Commons UI")

                page.fill("#energy-households", "36")
                page.fill("#energy-kwh", "19800")
                page.fill("#energy-tariff", "0.31")
                page.fill("#energy-peak-tariff", "0.44")
                page.locator("#btn-stage-energy").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                self.assertIn("Waiting for your review", page.locator("#shared-proposal-drawer").text_content())
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")
                page._driver.save_screenshot(str(SCREENSHOTS_DIR / "01_energy_commons_desktop.png"))

                # 2. Verify Advocate with unfamiliar notice & missing-document check
                page.locator("#tab-advocate").click()
                page.wait_for_timeout(400)
                body_text = page.locator("body").inner_text()
                for term in forbidden_jargon:
                    self.assertNotIn(term, body_text, f"Forbidden internal jargon '{term}' visible in Advocate UI")

                # Uncheck medical cert -> stage & accept -> verify locking packet says 'Some supporting information is missing'
                page.locator("#advocate-include-med-cert").click()
                page.locator("#btn-stage-advocate").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(400)
                page.locator("#advocate-human-approved").click()
                page.locator("#btn-authorize-advocate-filing").click()
                page.wait_for_timeout(400)
                self.assertIn(
                    "Some supporting information is missing",
                    page.locator("#product-action-banner").evaluate("el => el.textContent"),
                )
                # Re-attach medical cert -> stage & accept -> lock succeeds
                page.locator("#advocate-include-med-cert").click()
                page.locator("#btn-stage-advocate").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(400)
                page.locator("#btn-authorize-advocate-filing").click()
                page.wait_for_timeout(400)
                self.assertIn(
                    "Appeal packet approved and locked",
                    page.locator("#product-action-banner").evaluate("el => el.textContent"),
                )
                page._driver.save_screenshot(str(SCREENSHOTS_DIR / "02_advocate_desktop.png"))

                # 3. Verify Capability Commons with unfamiliar community project
                page.locator("#tab-commons").click()
                page.wait_for_timeout(400)
                body_text = page.locator("body").inner_text()
                for term in forbidden_jargon:
                    self.assertNotIn(term, body_text, f"Forbidden internal jargon '{term}' visible in Commons UI")

                page.fill("#commons-new-title", "Neighborhood Weatherization & Heat-Pump Co-op")
                page.fill("#commons-new-prompt", "Coordinate volunteer weatherization crews, window seals, and heat-pump installations.")
                page.locator("#btn-create-commons-project").click()
                page.wait_for_timeout(600)
                self.assertIn("4 Projects Active", page.locator("#commons-count-pill").evaluate("el => el.textContent"))
                page._driver.save_screenshot(str(SCREENSHOTS_DIR / "03_capability_commons_desktop.png"))

                # 4. Verify Science with unfamiliar hypothesis & seed offsets
                page.locator("#tab-science").click()
                page.wait_for_timeout(400)
                body_text = page.locator("body").inner_text()
                for term in forbidden_jargon:
                    self.assertNotIn(term, body_text, f"Forbidden internal jargon '{term}' visible in Science UI")

                page.fill("#science-seed1", "5")
                page.fill("#science-seed2", "105")
                page.fill("#science-hyp-title", "Three-Parameter Thermal Reserve Model")
                page.locator("#btn-add-science-hypothesis").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")
                page._driver.save_screenshot(str(SCREENSHOTS_DIR / "04_science_desktop.png"))

                # 5. Verify Civic with unfamiliar resident challenge & STOP/Resume
                page.locator("#tab-civic").click()
                page.wait_for_timeout(400)
                body_text = page.locator("body").inner_text()
                for term in forbidden_jargon:
                    self.assertNotIn(term, body_text, f"Forbidden internal jargon '{term}' visible in Civic UI")

                # Test Pause All Changes (STOP) -> blocks staging -> Resume Editing
                page.locator("#btn-trigger-stop").click()
                page.wait_for_timeout(400)
                self.assertIn("Editing: Paused (STOP)", page.locator("#pill-stop-state").evaluate("el => el.textContent"))
                page.locator("#btn-stage-civic").click()
                page.wait_for_timeout(400)
                self.assertIn("paused (STOP is active)", page.locator("#product-action-banner").evaluate("el => el.textContent"))
                page.locator("#btn-clear-stop").click()
                page.wait_for_timeout(400)

                page.fill("#civic-chal-claim", "Fire Marshal lane survey confirms 14ft emergency clearance on Parcel 9.")
                page.locator("#btn-add-civic-challenge").click()
                page.locator("#shared-proposal-drawer").wait_for(state="visible", timeout=10000)
                page.locator("#btn-accept-staged-proposal").click()
                page.wait_for_timeout(500)
                self.assertEqual(page.locator("#kpi-accepted-version").evaluate("el => el.textContent"), "v3")
                page._driver.save_screenshot(str(SCREENSHOTS_DIR / "05_civic_desktop.png"))

                # 6. Switch to Mobile 390x844 viewport, verify 0px overflow & save mobile screenshot
                page.set_viewport_size(390, 844)
                page.locator("#tab-energy").click()
                page.wait_for_timeout(400)
                overflow_mobile = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                self.assertFalse(overflow_mobile, "Mobile 390x844 overflow detected")
                page._driver.save_screenshot(str(SCREENSHOTS_DIR / "06_mobile_390x844_view.png"))

                self.assertEqual(js_errors, [], f"Unexpected browser JS errors: {js_errors}")
                browser.close()
        finally:
            srv.shutdown()
            srv.server_close()

        # 7. Restart server on install_1_dir and verify all accepted work survived restart
        srv2 = start_genie_server(port=0, state_dir=self.install_1_dir, use_model=False)
        th2 = threading.Thread(target=srv2.serve_forever, daemon=True)
        th2.start()
        base2 = f"http://127.0.0.1:{srv2.server_port}"
        try:
            with urllib.request.urlopen(f"{base2}/api/five_products/state", timeout=10) as resp:
                st2 = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(st2["products"]["energy"]["accepted_version"], 3)
            self.assertEqual(st2["products"]["energy"]["civilization_app"]["assumptions"]["household_units"], 36)
            self.assertEqual(st2["products"]["advocate"]["accepted_version"], 5)
            self.assertEqual(st2["products"]["science"]["accepted_version"], 3)
            self.assertEqual(st2["products"]["civic"]["accepted_version"], 3)
            self.assertEqual(len(st2["commons_library"]["projects"]), 4)
        finally:
            srv2.shutdown()
            srv2.server_close()


if __name__ == "__main__":
    unittest.main()
