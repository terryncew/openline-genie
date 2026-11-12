#!/usr/bin/env python3
"""Second-domain test (Step 5): build -> test -> export, fresh state dir.

Domain choice: community garden watering / plot / harvest tracker.
Why unfamiliar: no prior Genie prompt, fixture, or synthesizer family
touches gardening, watering schedules, plot assignments, or harvests.
Prior domains used: barber booking, service quoting/invoicing, kids
robotics, tool lending, solar savings, pet grooming. A garden tracker
shares only the generic "records + dates + money/quantities" shape, so
a working app here is evidence of general construction, not a
memorized template.
Writes evidence/second-domain/{result.json,garden-app.html}.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from core.model_adapter import AnthropicAdapter

EVID = Path(__file__).resolve().parents[1] / "evidence" / "second-domain"
EVID.mkdir(parents=True, exist_ok=True)
STATE_DIR = EVID / "state"
PROMPT = ("Build a free tool for a community garden to track watering "
          "schedules, plot assignments, and harvests.")
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
results: list[dict] = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)[:200]) if detail else ""), flush=True)


def main() -> int:
    adapter = AnthropicAdapter()
    engine = OpenLineGenieEngine(state_dir=str(STATE_DIR), model_adapter=adapter)
    bundle = engine.build_from_prompt(PROMPT, use_model=True)
    pid = bundle["project_id"]
    print(f"project {pid} family={bundle['project_family']}", flush=True)
    check("second domain: built by the real model worker",
          bundle["project_family"] == "model_built_app", bundle["project_family"])
    app = engine.get_app_version(pid)
    (EVID / "garden-app.html").write_text(app["content"], encoding="utf-8")
    print(f"app v{app['version']} sha={app['sha256'][:16]} bytes={len(app['content'])}", flush=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((EVID / "garden-app.html").as_uri())
            page.wait_for_timeout(600)
            body = page.evaluate("document.body ? document.body.innerText : ''")
            check("second domain: app loads with zero console errors", not errors,
                  "; ".join(errors[:2]))
            garden_words = [w for w in ("water", "plot", "harvest", "garden")
                            if w in body.lower()]
            check("second domain: garden concepts present in the app",
                  len(garden_words) >= 3, f"found: {garden_words}")
            scope = page
            forms = page.locator("form").all()
            if forms:
                scope = forms[0]
            filled = 0
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
                            filled += 1
                    elif tag == "textarea" or itype in ("", "text", "search", "tel"):
                        inp.fill("Garden Test Entry")
                        filled += 1
                    elif itype == "number":
                        inp.fill("5")
                        filled += 1
                    elif itype == "date":
                        inp.fill("2026-11-12")
                        filled += 1
                    elif itype == "time":
                        inp.fill("09:00")
                        filled += 1
                except Exception:
                    continue
            clicked = ""
            for btn in scope.locator("button").all():
                label = (btn.inner_text() or "").strip()
                if any(w in label.lower() for w in ("add", "save", "create", "book", "schedule", "submit", "log", "record")):
                    try:
                        btn.click(timeout=8000)
                        clicked = label
                    except Exception as exc:
                        clicked = f"TIMEOUT:{label}:{str(exc)[:60]}"
                    break
            page.wait_for_timeout(600)
            after = page.evaluate("document.body ? document.body.innerText : ''")
            check("second domain: added record appears",
                  "Garden Test Entry" in after, f"filled={filled} clicked={clicked!r}")
            page.reload()
            page.wait_for_timeout(500)
            check("second domain: record persists across reload",
                  "Garden Test Entry" in page.evaluate("document.body ? document.body.innerText : ''"))
        finally:
            browser.close()

    exp = engine.export_portable_bundle(pid)
    check("second domain: export is the runnable standalone app",
          exp.get("runs_standalone") is True and exp.get("standalone_html") == app["content"])
    closed = engine.close_project(pid)
    reopened = engine.reopen_project(pid)
    check("second domain: close/reopen round-trips",
          closed["status"] == "closed"
          and reopened["accepted"]["state_sha256"] == closed["state_sha256"])
    out = {"prompt": PROMPT, "project_id": pid, "app_sha256": app["sha256"],
           "checks": results}
    (EVID / "result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} second-domain checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
