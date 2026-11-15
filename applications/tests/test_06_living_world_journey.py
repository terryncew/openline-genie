#!/usr/bin/env python3
"""test_06 rewritten for the current requirement (living-world UI).

Replaces the stale test_06 in tests/test_openline_genie_001.py, whose
button-by-button journey targeted a pre-RC3 UI that no longer exists
(see tests/TEST_06_DISPOSITION.md for the full disposition and the
recorded decision: the old-UI journey is RETIRED; the underlying journey
is NOT retired). The preserved original is
tests/preserved/test_openline_genie_001_ORIGINAL.py.

This test runs the equivalent mobile journey against the living-world UI
at /, in real headless Chromium (Playwright) at 390x844, against the
real genie_server.py on a fresh ephemeral port with a fresh state dir:

  wish -> deterministic build ($0, --no-model server) -> discovery card
  visible automatically -> explore a preview -> reject (accepted state
  preserved) -> accept a change -> STOP blocks a mutation -> clear STOP
  -> close/reopen preserves accepted work -> export downloads a real
  standalone app.

Spend: $0 by design. The server runs with --no-model, so the wish-form
build takes the deterministic synthesizer path (no adapter, no model
call). No model call is made anywhere in this file.
"""
from __future__ import annotations

import json
import socket
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

EVIDENCE = Path(__file__).resolve().parent / "evidence_live"
EVIDENCE.mkdir(parents=True, exist_ok=True)

BAKERY_PROMPT = (
    "Design a small neighborhood bakery — Hearth & Crumb Bakery: a single-file "
    "HTML app to plan daily baking, track batches, and see capacity."
)


def _pick_free_port() -> int:
    """First free port in 8820-8850, verified free before use.

    Never kills another agent's server: a port that accepts a connection
    is in use and is skipped.
    """
    for port in range(8820, 8851):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise AssertionError("no free port in 8820-8850")


class Test06LivingWorldJourney(unittest.TestCase):
    """The test_06 customer journey, rewritten for the living-world UI."""

    @classmethod
    def setUpClass(cls):
        cls.port = _pick_free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.state_dir = tempfile.mkdtemp(prefix="genie-test06-living-world-")
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "genie_server.py"),
             "--port", str(cls.port), "--state-dir", cls.state_dir,
             "--no-model"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        t0 = time.time()
        while time.time() - t0 < 30:
            try:
                with urllib.request.urlopen(cls.base + "/api/status",
                                            timeout=5) as r:
                    status = json.loads(r.read().decode("utf-8"))
                # Confirm the server that answered is OURS on OUR port.
                assert "model_id" in status, status
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("test_06 server did not come up on "
                                 f"port {cls.port}")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    def _http_get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def _http_post(self, path, body):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Origin": self.base},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def _project_id(self):
        projects = self._http_get("/api/projects")["projects"]
        bakery = [p for p in projects
                  if p.get("project_family") == "bakery"
                  or "bakery" in str(p.get("project_id", ""))]
        self.assertEqual(len(bakery), 1, projects)
        return bakery[0]["project_id"]

    def _bundle(self, pid):
        return self._http_get(f"/api/project?project_id={pid}")

    def _accepted_throughput(self, bundle):
        return bundle["accepted"]["state"]["bakery"]["computed"][
            "throughput_loaves_per_day"]

    def test_06_living_world_mobile_journey(self):
        sync_playwright = _require_playwright_browser(self)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True, args=["--no-sandbox",
                                     "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 390, "height": 844},
                                    device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            try:
                # 1. Wish screen; no horizontal overflow at 390x844.
                page.goto(self.base + "/", wait_until="networkidle")
                self.assertTrue(page.locator("#wishScreen").is_visible())
                self.assertIn("What do you want to build?",
                              page.locator(".wishCard h1").inner_text())
                self.assertTrue(
                    page.evaluate("document.documentElement.scrollWidth"
                                  "<=window.innerWidth+1"),
                    "wish screen has horizontal overflow at 390x844")

                # 2. Wish -> build (deterministic, $0: --no-model server).
                page.fill("#wishInput", BAKERY_PROMPT)
                page.click("#wishBuildBtn")
                page.wait_for_selector("#wishScreen", state="hidden",
                                       timeout=120000)
                page.wait_for_timeout(500)
                self.assertTrue(
                    page.evaluate("document.documentElement.scrollWidth"
                                  "<=window.innerWidth+1"),
                    "living world has horizontal overflow at 390x844")
                pid = self._project_id()

                # 3. World loaded: RECEIVER VERIFIED, 174 loaves/day, Oven.
                diag = page.evaluate("window.__genieVisualDiagnostics()")
                self.assertEqual(diag["verificationStatus"],
                                 "RECEIVER_VERIFIED")
                self.assertTrue(diag["receiverAttested"])
                self.assertEqual(
                    diag["constraintResonance"]["system_throughput"], 174)
                self.assertEqual(
                    diag["constraintResonance"]["bottleneck_id"], "oven")
                self.assertEqual(page.locator("#provBadge").inner_text(),
                                 "RECEIVER VERIFIED")

                # 4. Discovery surfaced automatically (no prior tap): the
                # bar shows the discovery summary in flow; one obvious
                # action opens the full card in its own layer.
                # (r3: the full card moved into a fixed sheet — Option Two —
                # so the bar is the always-visible surface and the sheet
                # holds the full title/body/numbers.)
                page.wait_for_selector("#discoveryBar:not([hidden])",
                                       timeout=15000)
                self.assertIn("looks useless on its own",
                              page.text_content("#discBarTitle"))
                self.assertIn("280", page.text_content("#discNums"))
                page.click("#discoveryBarViewBtn")
                page.wait_for_selector("#discoveryCard:not([hidden])",
                                       timeout=15000)
                self.assertIn("looks useless on its own",
                              page.text_content("#discSheetTitle"))
                self.assertIn("174", page.text_content("#discSheetBody"))
                self.assertIn("+40", page.text_content("#discSheetBody"))
                self.assertIn("280", page.text_content("#discSheetNums"))

                # 5. Explore the discovery combo: preview 280, accepted 174.
                page.click("#discoverySheetExploreBtn")
                page.wait_for_selector("#rejectBtn:not([hidden])",
                                       timeout=15000)
                page.wait_for_timeout(500)
                diag = page.evaluate("window.__genieVisualDiagnostics()")
                self.assertEqual(
                    diag["constraintResonance"]["system_throughput"], 280)
                bundle = self._bundle(pid)
                pending = [e for e in bundle["exploratory"]
                           if e["status"] == "EXPLORATORY_PENDING"]
                self.assertEqual(len(pending), 1)
                cand = pending[0]["candidate_state"]["bakery"]["assumptions"]
                self.assertEqual(cand["ovens"], 2)
                self.assertTrue(cand["staggered_shift"])
                self.assertEqual(self._accepted_throughput(bundle), 174)

                # 6. Reject: accepted state preserved exactly, 1 rejected.
                sha_before_reject = bundle["accepted"]["state_sha256"]
                page.click("#rejectBtn")
                # (r3: the discovery stays available in the bar after a
                # reject; the full card is the sheet, opened on demand.)
                page.wait_for_selector("#discoveryBar:not([hidden])",
                                       timeout=15000)
                bundle = self._bundle(pid)
                self.assertEqual(
                    [e for e in bundle["exploratory"]
                     if e["status"] == "EXPLORATORY_PENDING"], [])
                self.assertEqual(len(bundle["rejected"]), 1)
                self.assertEqual(bundle["accepted"]["state_sha256"],
                                 sha_before_reject)
                self.assertEqual(self._accepted_throughput(bundle), 174)
                # (phase1b: the Reject handler reloads the live project
                # asynchronously, so the diagnostics snapshot can still
                # show the stale preview (280) on the first read. Wait
                # for the value to settle to the accepted baseline
                # (174) before asserting — same assertion, causally
                # ordered after the reload.)
                page.wait_for_function(
                    "() => window.__genieVisualDiagnostics?.()"
                    ".constraintResonance?.system_throughput === 174",
                    timeout=15000)
                diag = page.evaluate("window.__genieVisualDiagnostics()")
                self.assertEqual(
                    diag["constraintResonance"]["system_throughput"], 174)

                # 7. Accept a change: another oven, preview 240 -> accept.
                page.click("#quickMoveBtn")
                page.wait_for_timeout(500)
                diag = page.evaluate("window.__genieVisualDiagnostics()")
                self.assertEqual(
                    diag["constraintResonance"]["system_throughput"], 240)
                self.assertTrue(page.locator("#accept").is_visible())
                page.click("#accept")
                page.wait_for_timeout(800)
                bundle = self._bundle(pid)
                self.assertEqual(self._accepted_throughput(bundle), 240)
                self.assertEqual(
                    bundle["accepted"]["state"]["bakery"]["assumptions"]
                    ["ovens"], 2)
                diag = page.evaluate("window.__genieVisualDiagnostics()")
                self.assertEqual(
                    diag["constraintResonance"]["baseline_throughput"], 240)

                # 8. STOP blocks a mutation; clear STOP restores it.
                page.click("#stopBtn")
                page.wait_for_timeout(600)
                bundle = self._bundle(pid)
                self.assertTrue(bundle["stopped"])
                sha_stopped = bundle["accepted"]["state_sha256"]
                before = page.evaluate(
                    "window.__genieVisualDiagnostics()")
                page.click("#quickMoveBtn")
                page.wait_for_timeout(600)
                after = page.evaluate("window.__genieVisualDiagnostics()")
                self.assertEqual(
                    after["constraintResonance"]["system_throughput"],
                    before["constraintResonance"]["system_throughput"])
                bundle = self._bundle(pid)
                self.assertEqual(bundle["accepted"]["state_sha256"],
                                 sha_stopped)
                self.assertEqual(
                    [e for e in bundle["exploratory"]
                     if e["status"] == "EXPLORATORY_PENDING"], [])
                status, body = self._http_post(
                    "/api/build", {"prompt": "Build a robot game for kids.",
                                   "use_model": False})
                self.assertEqual(status, 409, body)
                page.click("#stopBtn")  # Clear STOP
                page.wait_for_timeout(600)
                self.assertFalse(self._bundle(pid)["stopped"])

                # 9. Close/reopen preserves accepted work.
                sha_before_close = self._bundle(pid)["accepted"][
                    "state_sha256"]
                page.locator("#detailToggle").click()
                page.wait_for_timeout(300)
                self.assertTrue(page.locator("#detailsPanel").is_visible())
                page.locator("#closeProjectBtn").click()
                page.wait_for_timeout(800)
                bundle = self._bundle(pid)
                self.assertEqual(bundle["status"], "closed")
                self.assertIn("closed",
                              page.locator("#provStatus").inner_text().lower())
                # Mutation refused while closed.
                status, body = self._http_post(
                    "/api/propose",
                    {"project_id": pid, "summary": "closed probe",
                     "patch": {}})
                self.assertNotEqual(status, 200, body)
                self.assertIn("project_closed", str(body))
                page.locator("#reopenProjectBtn").click()
                page.wait_for_timeout(800)
                bundle = self._bundle(pid)
                self.assertEqual(bundle["status"], "open")
                self.assertEqual(bundle["accepted"]["state_sha256"],
                                 sha_before_close)
                self.assertEqual(self._accepted_throughput(bundle), 240)

                # 10. Export downloads the real standalone app.
                exported = self._http_get(
                    f"/api/export?project_id={pid}")["content"]
                with page.expect_download() as dl:
                    page.locator("#exportAppBtn").click()
                download = dl.value
                path = EVIDENCE / "test06_living_world_export.html"
                download.save_as(str(path))
                content = path.read_text(encoding="utf-8")
                # The living-world export goes through a Blob download, which
                # normalizes the CSV section's CRLF line endings to LF; the
                # bytes are otherwise identical to /api/export. Compare
                # line-ending-normalized, and pin the CSV rows explicitly.
                self.assertEqual(content.replace("\r\n", "\n"),
                                 exported.replace("\r\n", "\n"))
                self.assertIn("REC-101", content)
                self.assertIn("<!DOCTYPE html>", content)
                self.assertIn("Hearth", content)
                self.assertGreater(len(content), 1000)
                self.assertNotIn("SIMULATED", content[:2000])
                self.assertIn("Download started",
                              page.locator("#exportConfirm").inner_text())

                self.assertFalse(errors, errors)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
