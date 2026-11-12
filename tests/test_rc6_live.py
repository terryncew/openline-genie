#!/usr/bin/env python3
"""RC6 live tests — real server + real headless Chromium.

Starts genie_server.py (--no-model: deterministic bakery build, zero
model spend) on a scratch port, then drives the living-world UI:
wish screen -> bakery world (RECEIVER VERIFIED, 174/oven) -> explore
(real proposal in the engine, preview 240) -> accept (baseline 240)
-> explore hours (preview 280) -> reject (accepted preserved) ->
STOP blocks explore -> clear STOP -> replace worker (accepted SHA
preserved) -> export (real app bytes) -> opportunities recompute.

Phone-density checks at 390x844 and 320x640: no horizontal overflow,
tap targets >=44px, no section overlap, no truncated labels, text
contrast >= 4.5:1, keyboard navigation, reduced motion.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

def _require_playwright_browser(test_case):
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        test_case.skipTest("playwright not installed in Python runtime; HTTP + Node DOM/projection verification runs in test_genie_rc7_adversarial_gate.py")
    try:
        with sync_playwright() as pw:
            exe = pw.chromium.executable_path
            if not exe or not Path(exe).exists():
                test_case.skipTest(f"Playwright Chromium executable not installed at {exe}")
    except unittest.SkipTest:
        raise
    except Exception as exc:
        test_case.skipTest(f"Playwright browser unavailable in this container environment: {exc}")
    return sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PORT = 8797
BASE = f"http://127.0.0.1:{PORT}"
EVIDENCE = Path(__file__).resolve().parent / "evidence_live"
EVIDENCE.mkdir(parents=True, exist_ok=True)

BAKERY_PROMPT = (
    "Design a small neighborhood bakery — Hearth & Crumb Bakery: a single-file "
    "HTML app to plan daily baking, track batches, and see capacity."
)


def http_get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Origin": BASE},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def wait_up(timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            http_get("/api/status")
            return True
        except Exception:
            time.sleep(0.5)
    return False


class TestRc6Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state_dir = tempfile.mkdtemp(prefix="genie-rc6-live-")
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "genie_server.py"),
             "--port", str(PORT), "--state-dir", cls.state_dir, "--no-model"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        assert wait_up(), "server did not come up"
        status, bundle = http_post("/api/build", {"prompt": BAKERY_PROMPT, "use_model": False})
        assert status == 200, bundle
        cls.project_id = bundle["project_id"]

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    def test_wish_to_world_flow(self):
        sync_playwright = _require_playwright_browser(self)

        pid = self.project_id
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 390, "height": 844},
                                    device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/", wait_until="networkidle")
            # Wish screen first.
            self.assertTrue(page.locator("#wishScreen").is_visible())
            self.assertIn("What do you want to build?",
                          page.locator(".wishCard h1").inner_text())
            page.locator("#wishBakeryBtn").click()
            page.wait_for_selector("#wishScreen", state="hidden", timeout=10000)
            page.wait_for_timeout(400)
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(diag["verificationStatus"], "RECEIVER_VERIFIED")
            self.assertTrue(diag["receiverAttested"])
            self.assertEqual(diag["constraintResonance"]["system_throughput"], 174)
            self.assertEqual(diag["constraintResonance"]["bottleneck_id"], "oven")
            self.assertEqual(page.locator("#provBadge").inner_text(), "RECEIVER VERIFIED")
            opps = diag["opportunities"]
            self.assertTrue(2 <= len(opps) <= 4, opps)
            self.assertTrue(any(o["kind"] == "SYNERGISTIC_COMBO" for o in opps), opps)
            self.assertTrue(any(o["kind"] == "KEEP_WHAT_I_HAVE" for o in opps), opps)

            # Explore: another oven. Real proposal in the engine + preview 240.
            page.locator("#quickMoveBtn").click()
            page.wait_for_timeout(500)
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(diag["constraintResonance"]["system_throughput"], 240)
            self.assertEqual(diag["constraintResonance"]["baseline_throughput"], 174)
            bundle = http_get(f"/api/project?project_id={pid}")
            self.assertEqual(len(bundle["exploratory"]), 1)
            self.assertEqual(bundle["exploratory"][0]["status"], "EXPLORATORY_PENDING")
            self.assertEqual(
                bundle["exploratory"][0]["candidate_state"]["bakery"]["computed"]
                ["throughput_loaves_per_day"], 240)
            self.assertEqual(
                bundle["accepted"]["state"]["bakery"]["computed"]
                ["throughput_loaves_per_day"], 174)
            page.screenshot(path=str(EVIDENCE / "rc6_390_preview_240.png"))

            # Accept: baseline becomes 240 in the engine and the world.
            self.assertTrue(page.locator("#accept").is_visible())
            page.locator("#accept").click()
            page.wait_for_timeout(800)
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(diag["constraintResonance"]["baseline_throughput"], 240)
            self.assertEqual(diag["constraintResonance"]["system_throughput"], 240)
            bundle = http_get(f"/api/project?project_id={pid}")
            self.assertEqual(
                bundle["accepted"]["state"]["bakery"]["computed"]
                ["throughput_loaves_per_day"], 240)
            self.assertEqual(bundle["accepted"]["state"]["bakery"]["assumptions"]["ovens"], 2)

            # Explore hours (preview 280), then reject: accepted preserved.
            page.locator("#quickMoveBtn").click()
            page.wait_for_timeout(500)
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(diag["constraintResonance"]["system_throughput"], 280)
            page.locator("#rejectBtn").click()
            page.wait_for_timeout(800)
            bundle = http_get(f"/api/project?project_id={pid}")
            self.assertEqual(
                bundle["accepted"]["state"]["bakery"]["computed"]
                ["throughput_loaves_per_day"], 240)
            self.assertEqual(len(bundle["rejected"]), 1)
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(diag["constraintResonance"]["system_throughput"], 240)

            # STOP blocks explore: no preview, engine refuses.
            page.locator("#stopBtn").click()
            page.wait_for_timeout(600)
            bundle = http_get(f"/api/project?project_id={pid}")
            self.assertTrue(bundle["stopped"])
            before = page.evaluate("window.__genieVisualDiagnostics()")
            page.locator("#quickMoveBtn").click()
            page.wait_for_timeout(600)
            after = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(after["constraintResonance"]["system_throughput"],
                             before["constraintResonance"]["system_throughput"])
            self.assertEqual(len(http_get(f"/api/project?project_id={pid}")["exploratory"]), 2)
            page.locator("#stopBtn").click()  # Clear STOP
            page.wait_for_timeout(600)
            self.assertFalse(http_get(f"/api/project?project_id={pid}")["stopped"])

            # Replace worker from Details: accepted SHA preserved.
            sha_before = http_get(f"/api/project?project_id={pid}")["accepted"]["state_sha256"]
            page.locator("#detailToggle").click()
            page.wait_for_timeout(300)
            self.assertTrue(page.locator("#detailsPanel").is_visible())
            page.locator("#replaceWorkerBtn").click()
            page.wait_for_timeout(800)
            bundle = http_get(f"/api/project?project_id={pid}")
            self.assertEqual(bundle["active_worker_id"], "worker-b")
            self.assertEqual(bundle["accepted"]["state_sha256"], sha_before)

            # Export downloads the real accepted app bytes.
            with page.expect_download() as dl:
                page.locator("#exportAppBtn").click()
            dl.value.save_as(str(EVIDENCE / "rc6_export.html"))
            exported = (EVIDENCE / "rc6_export.html").read_text(encoding="utf-8")
            self.assertIn("Hearth", exported)
            self.assertNotIn("SIMULATED", exported[:2000])

            # Opportunities recomputed after the accept (hours now offered).
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertTrue(any(o["id"] == "hours" for o in diag["opportunities"]),
                            diag["opportunities"])
            self.assertFalse(errors, errors)
            page.screenshot(path=str(EVIDENCE / "rc6_390_accepted_240.png"))
            browser.close()

    def test_phone_density(self):
        sync_playwright = _require_playwright_browser(self)

        pid = self.project_id
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            for width, height in [(390, 844), (320, 640)]:
                ctx = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1, reduced_motion="reduce")
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(BASE + "/", wait_until="networkidle")
                page.locator("#wishBakeryBtn").click()
                page.wait_for_selector("#wishScreen", state="hidden", timeout=10000)
                page.wait_for_timeout(400)
                # No horizontal overflow.
                self.assertTrue(
                    page.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"),
                    f"horizontal overflow at {width}")
                # Tap targets >=44px for visible buttons/selects/text inputs.
                small = page.evaluate("""() => {
                  const bad = [];
                  for (const el of document.querySelectorAll('button,select,input[type=text]')) {
                    const r = el.getBoundingClientRect();
                    const vis = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
                    if (!vis) continue;
                    if (el.closest('[hidden]')) continue;
                    if (r.height < 44) bad.push(el.id || el.className || el.tagName + ':' + Math.round(r.height));
                  }
                  return bad;
                }""")
                self.assertEqual(small, [], f"small tap targets at {width}: {small}")
                # Sections do not overlap vertically.
                overlap = page.evaluate("""() => {
                  const sels = ['.top', '.lead', '.toolbar', '.scene', '.quickMove', '.inspector', '.choices', '.foot'];
                  const rects = sels.map(s => { const el = document.querySelector(s); if (!el) return null; const r = el.getBoundingClientRect(); return {s, top: r.top + window.scrollY, bottom: r.bottom + window.scrollY}; }).filter(Boolean);
                  const bad = [];
                  for (let i = 1; i < rects.length; i++) {
                    if (rects[i].top < rects[i-1].bottom - 1) bad.push(rects[i-1].s + ' overlaps ' + rects[i].s);
                  }
                  return bad;
                }""")
                self.assertEqual(overlap, [], f"overlapping sections at {width}: {overlap}")
                # No truncated labels in key text elements.
                truncated = page.evaluate("""() => {
                  const bad = [];
                  for (const el of document.querySelectorAll('#sceneTitle,#sceneDesc,#inspectTitle,#quickMoveTitle,#quickMoveSub,.choice strong,.choice p')) {
                    if (el.scrollWidth > el.clientWidth + 1) bad.push(el.id || el.textContent.slice(0, 30));
                  }
                  return bad;
                }""")
                self.assertEqual(truncated, [], f"truncated labels at {width}: {truncated}")
                # Text contrast >= 4.5:1 for main copy against page background.
                low_contrast = page.evaluate("""() => {
                  function lum(rgb) {
                    const m = rgb.match(/[\\d.]+/g).map(Number);
                    const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
                    return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]);
                  }
                  const bg = lum('rgb(4, 8, 20)');
                  const bad = [];
                  for (const el of document.querySelectorAll('.wishCard p, .lead p, .inspector p, .choice p')) {
                    const cs = getComputedStyle(el);
                    if (!el.offsetParent && el.closest('#wishScreen[hidden]')) continue;
                    const fg = lum(cs.color);
                    const ratio = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
                    if (ratio < 4.5) bad.push(el.className + ':' + ratio.toFixed(2));
                  }
                  return bad;
                }""")
                self.assertEqual(low_contrast, [], f"low contrast at {width}: {low_contrast}")
                # Keyboard: canvas focusable, ArrowRight moves selection.
                page.locator("#graph").focus()
                before = page.evaluate("window.__genieVisualDiagnostics().selected")
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(200)
                after = page.evaluate("window.__genieVisualDiagnostics().selected")
                self.assertNotEqual(before, after, "keyboard nav did not move selection")
                page.screenshot(path=str(EVIDENCE / f"rc6_{width}_world.png"))
                self.assertFalse(errors, errors)
                ctx.close()
            browser.close()


class TestDiscoveryFirstRun(unittest.TestCase):
    """Discovery-first: the counterintuitive result appears on its own,
    Explore creates a REAL proposal, Dismiss changes nothing."""

    PORT = 8799

    @classmethod
    def setUpClass(cls):
        cls.state_dir = Path(__file__).resolve().parent / "state-discovery"
        shutil.rmtree(cls.state_dir, ignore_errors=True)
        cls.state_dir.mkdir(parents=True, exist_ok=True)
        cls.base = f"http://127.0.0.1:{cls.PORT}"
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "genie_server.py"),
             "--port", str(cls.PORT), "--state-dir", str(cls.state_dir), "--no-model"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        t0 = time.time()
        while time.time() - t0 < 30:
            try:
                urllib.request.urlopen(cls.base + "/api/status", timeout=5)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("discovery server did not come up")
        req = urllib.request.Request(
            cls.base + "/api/build",
            data=json.dumps({"prompt": BAKERY_PROMPT, "use_model": False}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": cls.base},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            bundle = json.loads(r.read().decode("utf-8"))
        cls.project_id = bundle["project_id"]

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    def _engine(self):
        return json.loads(
            urllib.request.urlopen(
                self.base + "/api/project?project_id=" + self.project_id
            ).read()
        )

    def test_discovery_card_automatic_explore_is_real_dismiss_is_free(self):
        sync_playwright = _require_playwright_browser(self)

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                self._run(browser)
            finally:
                browser.close()

    def _run(self, browser):
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            page.goto(self.base + "/", wait_until="networkidle")
            page.click("#wishBakeryBtn")
            # The discovery is surfaced with NO prior tap on anything
            # else: the bar shows its summary in flow; one obvious
            # action opens the full card in its own layer.
            # (r3: the full card moved into a fixed sheet — Option Two —
            # so the bar is the always-visible surface and the sheet
            # holds the full title/body/numbers.)
            page.wait_for_selector("#discoveryBar:not([hidden])", timeout=15000)
            # (r3-qual: load-completion wait — the bar is never hidden,
            # so the selector above matches instantly, before the load
            # has populated the title; the title reads "No new discovery
            # right now" for ~100-500 ms after the click. Wait for the
            # discovery text itself, bounded 15 s.)
            page.wait_for_function(
                "() => (document.querySelector('#discBarTitle') || {})"
                ".textContent?.includes('looks useless on its own')",
                timeout=15000)
            self.assertIn("looks useless on its own",
                          page.text_content("#discBarTitle"))
            self.assertIn("280", page.text_content("#discNums"))
            page.click("#discoveryBarViewBtn")
            page.wait_for_selector("#discoveryCard:not([hidden])", timeout=15000)
            title = page.text_content("#discSheetTitle")
            body = page.text_content("#discSheetBody")
            nums = page.text_content("#discSheetNums")
            self.assertIn("looks useless on its own", title)
            self.assertIn("changes nothing", body)
            self.assertIn("+40", body)
            self.assertIn("174", body)
            self.assertIn("280", nums)
            # Explore creates a REAL exploratory proposal (both changes).
            # The combo leaves the opportunities list once branched, so
            # the open-preview signal is the inspector's Reject button.
            page.click("#discoverySheetExploreBtn")
            page.wait_for_selector("#rejectBtn:not([hidden])", timeout=15000)
            page.wait_for_timeout(500)
            diag = page.evaluate("window.__genieVisualDiagnostics()")
            self.assertEqual(diag["constraintResonance"]["system_throughput"], 280)
            proj = self._engine()
            pending = [e for e in proj["exploratory"] if e["status"] == "EXPLORATORY_PENDING"]
            self.assertEqual(len(pending), 1)
            exp = proj["exploratory"][0]["candidate_state"]["bakery"]["assumptions"]
            self.assertEqual(exp["ovens"], 2)
            self.assertTrue(exp["staggered_shift"])
            # Accepted state untouched while exploring.
            acc = proj["accepted"]["state"]["bakery"]
            self.assertEqual(acc["assumptions"]["ovens"], 1)
            self.assertEqual(acc["computed"]["throughput_loaves_per_day"], 174)
            # Reject restores the exact accepted state; the discovery
            # recomputes and the bar shows it again (the combo is still
            # open). (r3: the bar is the always-visible surface; wait for
            # the async reject to finish — Reject hiding — before
            # reading the bar.)
            page.click("#rejectBtn")
            page.wait_for_selector("#rejectBtn", state="hidden", timeout=15000)
            page.wait_for_selector("#discoveryBar:not([hidden])", timeout=15000)
            self.assertIn("looks useless on its own",
                          page.text_content("#discBarTitle"))
            proj = self._engine()
            pending = [e for e in proj["exploratory"] if e["status"] == "EXPLORATORY_PENDING"]
            self.assertEqual(len(pending), 0)
            self.assertEqual(len(proj["rejected"]), 1)
            self.assertEqual(
                proj["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 174
            )
            # Dismiss sets the discovery aside and changes NOTHING in
            # the engine. (r3: the bar switches to its honest
            # "no discovery" state; the sheet stays closed.)
            page.click("#discoveryDismissBtn")
            page.wait_for_selector("#discoveryCard", state="hidden", timeout=5000)
            self.assertIn("No new discovery right now",
                          page.text_content("#discBarTitle"))
            proj = self._engine()
            pending = [e for e in proj["exploratory"] if e["status"] == "EXPLORATORY_PENDING"]
            self.assertEqual(len(pending), 0)
            self.assertEqual(len(proj["rejected"]), 1)
            self.assertEqual(
                proj["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 174
            )
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
