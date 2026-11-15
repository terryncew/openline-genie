#!/usr/bin/env python3
"""Step 7 demo video: the real user journey, recorded, no staging.

Journey (real server, decisive state dir, zero model calls):
  load UI -> open the barber project -> add an appointment in the
  artifact iframe -> open Details (receipts, worker-b) -> STOP ->
  clear STOP -> export the runnable app.
Records 390x844 vertical video (Playwright), converts to mp4.
Writes evidence/demo/genie-rc3-demo.mp4 (+ .webm source).
Run: python3 run_demo_video.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVID = Path(__file__).resolve().parents[1] / "evidence" / "demo"
EVID.mkdir(parents=True, exist_ok=True)
STATE_DIR = Path(__file__).resolve().parents[1] / "evidence" / "decisive" / "state"
PID = "genie-model-mobile-barber-booking-reminders"
def _resolve_chrome_path():
    """Browser binary for Playwright: GENIE_CHROME_PATH override, then a
    system Chromium/Chrome on PATH, else None (Playwright default lookup).
    No hardcoded home-directory path."""
    env = os.environ.get("GENIE_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if env:
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME = _resolve_chrome_path()
VID_DIR = EVID / "raw-video"
VID_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    server = subprocess.Popen(
        [sys.executable, "genie_server.py", "--port", "8799", "--state-dir", str(STATE_DIR)],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=CHROME, args=["--no-sandbox"])
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                record_video_dir=str(VID_DIR), record_video_size={"width": 390, "height": 844})
            page = ctx.new_page()
            page.goto("http://127.0.0.1:8799/", wait_until="networkidle")
            page.wait_for_timeout(1200)
            page.locator(f"[data-open-project='{PID}']").click()
            page.wait_for_timeout(1500)
            frame = page.frame_locator("#artifact-frame")
            page.locator("#artifact-frame").scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            # Add an appointment inside the real artifact iframe.
            scope = frame.locator("form").first
            if not scope.count():
                scope = frame
            for inp in scope.locator("input, textarea, select").all():
                try:
                    if not inp.is_visible():
                        continue
                    tag = inp.evaluate("el => el.tagName.toLowerCase()")
                    itype = (inp.get_attribute("type") or "").lower()
                    if tag == "select":
                        opts = inp.locator("option").all()
                        if len(opts) > 1:
                            inp.select_option(index=1)
                    elif tag == "textarea" or itype in ("", "text", "search", "tel"):
                        inp.fill("Demo Client")
                    elif itype == "date":
                        inp.fill("2026-11-13")
                    elif itype == "time":
                        inp.fill("10:00")
                    elif itype == "number":
                        inp.fill("30")
                except Exception:
                    continue
            for btn in scope.locator("button").all():
                label = (btn.inner_text() or "").strip()
                if any(w in label.lower() for w in ("add", "save", "create", "book", "schedule", "submit")):
                    btn.click(timeout=8000)
                    print("clicked:", label, flush=True)
                    break
            page.wait_for_timeout(800)
            body = frame.locator("body").inner_text()
            print("Demo Client visible in app:", "Demo Client" in body, flush=True)
            # Details: receipts + worker.
            page.locator("#details-tech summary").click()
            page.wait_for_timeout(800)
            # STOP, then clear.
            page.locator("#btn-global-stop").click()
            page.wait_for_timeout(800)
            print("STOP banner visible:", page.locator("#stop-banner").is_visible(), flush=True)
            page.locator("#btn-clear-stop").click()
            page.wait_for_timeout(800)
            # Export the runnable app.
            with page.expect_download() as dl:
                page.locator("#btn-export").click()
            download = dl.value
            download.save_as(str(EVID / "demo-export.html"))
            print("export saved:", download.suggested_filename, flush=True)
            page.wait_for_timeout(500)
            ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
    webms = sorted(VID_DIR.glob("*.webm"))
    print("recorded:", [w.name for w in webms], flush=True)
    if not webms:
        return 1
    src = webms[-1]
    out = EVID / "genie-rc3-demo.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                   check=True, capture_output=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-show_entries", "stream=width,height,codec_name",
                            "-of", "default=noprint_wrappers=1", str(out)],
                           capture_output=True, text=True, check=True)
    print(probe.stdout, flush=True)
    print("demo video:", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
