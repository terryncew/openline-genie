#!/usr/bin/env python3
"""Decisive-test addendum (Step 4 follow-up), no Sonnet calls.

The first decisive run (26/30) left two items to close honestly:
  1. Recurrence in the Sonnet revision was reported FAIL only because the
     check looked for the word "recur"; the app has a Repeat select
     (Weekly / Every 2 weeks / ...). Verify functionally: a Weekly
     booking creates multiple instances.
  2. Conflict detection is genuinely absent in v1 AND in the Sonnet
     revision: a double-booking is silently added. Repair with a Haiku
     revise (disclosed: the Sonnet revision did not add it), propose +
     accept through the receiver, then re-drive the double-booking.
Writes evidence/decisive/addendum.json + barber-final-v3.html.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from core.model_adapter import AnthropicAdapter
from core.genie_worker import GenieWorker

EVID = Path(__file__).resolve().parents[1] / "evidence" / "decisive"
STATE_DIR = EVID / "state"
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
results: list[dict] = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)[:200]) if detail else ""), flush=True)


def drive(app_html: str, label: str, repeat_weekly: bool = False) -> dict:
    """Add a booking (optionally Weekly repeat), then an identical one;
    report what the app did."""
    from playwright.sync_api import sync_playwright

    facts: dict = {"label": label, "console_errors": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.on("console", lambda m: facts["console_errors"].append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: facts["console_errors"].append(str(e)))
            tmp = EVID / f"_addendum-{label}.html"
            tmp.write_text(app_html, encoding="utf-8")
            page.goto(tmp.as_uri())
            page.wait_for_timeout(600)

            def fill_once(client: str):
                scope = page
                forms = page.locator("form").all()
                if forms:
                    scope = forms[0]
                for inp in scope.locator("input, textarea, select").all():
                    try:
                        if not inp.is_visible():
                            continue
                        tag = inp.evaluate("el => el.tagName.toLowerCase()")
                        itype = (inp.get_attribute("type") or "").lower()
                        ident = (inp.get_attribute("id") or "") + (inp.get_attribute("name") or "")
                        if tag == "select" and "repeat" in ident.lower():
                            if repeat_weekly:
                                inp.select_option("weekly")
                            continue
                        if tag == "select":
                            opts = inp.locator("option").all()
                            if len(opts) > 1:
                                inp.select_option(index=1)
                        elif tag == "textarea" or itype in ("", "text", "search", "tel"):
                            inp.fill(client)
                        elif itype == "email":
                            inp.fill("addendum@example.com")
                        elif itype == "number":
                            inp.fill("30")
                        elif itype == "date":
                            inp.fill("2026-11-13")
                        elif itype == "time":
                            inp.fill("10:00")
                    except Exception:
                        continue
                for btn in scope.locator("button").all():
                    label_t = (btn.inner_text() or "").strip()
                    if any(w in label_t.lower() for w in ("add", "save", "create", "book", "schedule", "submit")):
                        try:
                            btn.click(timeout=8000)
                            return label_t
                        except Exception:
                            return f"TIMEOUT:{label_t}"
                return ""

            clicked = fill_once("Addendum Client")
            page.wait_for_timeout(600)
            after1 = page.evaluate("document.body ? document.body.innerText : ''")
            facts["clicked"] = clicked
            facts["count_after_first"] = after1.count("Addendum Client")
            facts["after_first"] = after1
            # Identical second booking.
            fill_once("Addendum Client")
            page.wait_for_timeout(600)
            after2 = page.evaluate("document.body ? document.body.innerText : ''")
            facts["count_after_second"] = after2.count("Addendum Client")
            facts["after_second"] = after2
            m = re.search(r".{0,60}conflict.{0,120}", after2, re.IGNORECASE)
            facts["conflict_text"] = m.group(0) if m else ""
            m2 = re.search(r".{0,60}(already booked|already exists|duplicate|overlap).{0,120}", after2, re.IGNORECASE)
            facts["dup_text"] = m2.group(0) if m2 else ""
        finally:
            browser.close()
    return facts


def main() -> int:
    adapter = AnthropicAdapter()
    engine = OpenLineGenieEngine(state_dir=str(STATE_DIR), model_adapter=adapter)
    worker = GenieWorker(adapter, engine)
    bundle = engine.get_project_bundle(PID)
    v2 = engine.get_app_version(PID)
    print(f"starting state: accepted v{v2['version']} sha={v2['sha256'][:16]} status={bundle['status']} model={engine.model_id}", flush=True)

    # 1. Functional recurrence check on the Sonnet revision (v2).
    f2 = drive(v2["content"], "v2-weekly", repeat_weekly=True)
    check("addendum: Weekly booking creates multiple instances",
          f2["count_after_first"] >= 2,
          f"client appears {f2['count_after_first']}x after one Weekly booking")
    check("addendum: v2 loads with zero console errors", not f2["console_errors"],
          "; ".join(f2["console_errors"][:2]))

    # 2. Conflict-detection repair (Haiku; disclosed).
    engine.replace_model("claude-haiku-5-5", project_id=PID)
    change = ("Add scheduling conflict detection: when a new booking overlaps an existing "
              "booking for the same barber at the same date and time, refuse the duplicate "
              "and show a clear conflict message; do not create the duplicate booking.")
    rev = worker.revise(prompt=bundle["accepted"]["state"].get("prompt", ""),
                        current_app_html=v2["content"], change_request=change,
                        project_id=PID, title=str(bundle["accepted"]["state"].get("title", PID)))
    print(f"Haiku conflict repair ready sha={rev['app_sha256'][:16]} bytes={rev['bytes']} model={rev['model']}", flush=True)
    prop = engine.propose_exploratory_change(PID, change, {"app_content": rev["app_html"], "app_filename": v2["filename"]})
    prop_id = prop["exploratory"][0]["proposal_id"]
    check("addendum: conflict repair proposed through the receiver",
          prop["exploratory"][0]["validation_passed"], prop_id)
    ver_before_accept = engine.get_app_version(PID)["version"]
    engine.accept_exploratory_change(PID, prop_id)
    v3 = engine.get_app_version(PID)
    (EVID / "barber-final-v6.html").write_text(v3["content"], encoding="utf-8")
    check("addendum: conflict repair accepted (next version, exact SHA)",
          v3["version"] == ver_before_accept + 1
          and v3["sha256"] == rev["app_sha256"], f"v{v3['version']} sha={v3['sha256'][:16]}")
    check("addendum: v2 bytes preserved in history",
          engine.get_app_version(PID, v2["version"])["sha256"] == v2["sha256"])

    # 3. Re-drive the double-booking on v3.
    f3 = drive(v3["content"], "v3-conflict", repeat_weekly=False)
    conflict_shown = bool(f3["conflict_text"] or f3["dup_text"])
    check("addendum: double-booking now shows a conflict message",
          conflict_shown, f3["conflict_text"] or f3["dup_text"] or "no conflict wording")
    check("addendum: duplicate booking is NOT created",
          f3["count_after_second"] <= f3["count_after_first"],
          f"first={f3['count_after_first']} second={f3['count_after_second']}")
    check("addendum: v3 loads with zero console errors", not f3["console_errors"],
          "; ".join(f3["console_errors"][:2]))
    # Recurrence still works after the repair.
    f3w = drive(v3["content"], "v3-weekly", repeat_weekly=True)
    check("addendum: Weekly recurrence still works in v3",
          f3w["count_after_first"] >= 2, f"client appears {f3w['count_after_first']}x")

    out = {"checks": results,
           "v2_sha256": v2["sha256"], "final_sha256": v3["sha256"],
           "final_version": v3["version"],
           "repair_model": rev["model"], "repair_sha256": rev["app_sha256"]}
    (EVID / "addendum.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} addendum checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
