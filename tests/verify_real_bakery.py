#!/usr/bin/env python3
"""Self-contained live browser verification of the Bakery Living World UI and
exported standalone HTML application (`tests/verify_real_bakery.py`).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_server import start_genie_server
from playwright.sync_api import sync_playwright


def main() -> int:
    ev_dir = Path(
        os.environ.get("GENIE_VERIFY_EVIDENCE_DIR", "")
        or Path(__file__).resolve().parent / "evidence_live"
    )
    ev_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="genie-real-bakery-") as td:
        srv = start_genie_server(port=0, state_dir=Path(td), use_model=False, host="127.0.0.1")
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_port}"
        summary: dict[str, object] = {}
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(base + "/", wait_until="networkidle")
                page.locator("#wishBakeryBtn").click()
                page.wait_for_selector("#wishScreen", state="hidden", timeout=15000)
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
                page.screenshot(path=str(ev_dir / "rc6_real_bakery_390_world.png"))

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
                page.screenshot(path=str(ev_dir / "rc6_real_bakery_390_accepted.png"))
                assert not errors, errors

                # Export standalone HTML and exercise it offline in Chromium
                pid = str(diag["projectId"])
                exported_html = srv.genie_engine.export_portable_bundle(pid)["standalone_html"]
                exported_path = Path(td) / "rc6_bakery_app.html"
                exported_path.write_text(exported_html, encoding="utf-8")

                app = browser.new_page(viewport={"width": 390, "height": 844})
                app_errors: list[str] = []
                app.on("pageerror", lambda e: app_errors.append(str(e)))
                app.goto(exported_path.as_uri(), wait_until="load")
                app.wait_for_timeout(300)
                summary["exported_app_title"] = app.title()
                body1 = app.locator("body").inner_text()
                summary["exported_app_rendered_offline"] = len(body1) > 40
                app.reload(wait_until="load")
                app.wait_for_timeout(300)
                body2 = app.locator("body").inner_text()
                summary["exported_app_persists_after_reload"] = len(body2) > 40
                app.screenshot(path=str(ev_dir / "rc6_real_bakery_exported_app.png"))
                assert not app_errors, app_errors
                browser.close()
        finally:
            srv.shutdown()
            srv.server_close()

    (ev_dir / "rc6_real_bakery_verification.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
