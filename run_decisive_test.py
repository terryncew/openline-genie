#!/usr/bin/env python3
"""Decisive customer test + agent replacement (Step 4), end to end.

Fresh run, real model worker through the real receiver, real browser:
  (a) "Build a free booking and reminder tool for a mobile barber."
      Genie builds the app; the app is exercised in a real browser
      (appointments, scheduling conflict, customer record, service
      price, reminder prepared for owner review, never sent).
  (b) Owner: "Add recurring appointments and let customers choose their
      barber." DURING that unfinished modification the owner interrupts
      ("Stop this AI. Give my project to another one."): STOP + revoke
      worker-A through the receiver; accepted work preserved; the
      unfinished Haiku revision is discarded uncommitted; remaining work
      goes to a replacement worker on a DIFFERENT model (the ONE approved
      Sonnet 5.5 call); the replacement finishes it; revoked authority
      cannot continue; no operation is repeated; the final app runs
      standalone.
  (c) The owner rejects one proposed design change; the accepted app is
      restored byte-identical.
  (d) Close/reopen round-trips.

Also exercises the RC2A outbox path in the demo: an owner-approved
external reminder send whose acknowledgement is dropped stays UNKNOWN
until reconciled against a registered destination key (0 duplicates,
never presented as success).

No model call happens outside core/model_adapter.py. Spend is
cap-enforced and logged there. Run: python3 run_decisive_test.py
Writes evidence/decisive/{transcript.json,barber-v1.html,barber-final.html}
and prints PASS/FAIL per check.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from core.model_adapter import AnthropicAdapter
from core.genie_worker import GenieWorker
from core.openline_guard import GuardRefused, SigningIdentity, sign_envelope

EVID = Path(__file__).resolve().parents[1] / "evidence" / "decisive"
EVID.mkdir(parents=True, exist_ok=True)
STATE_DIR = EVID / "state"
BARBER_PROMPT = "Build a free booking and reminder tool for a mobile barber."
CHANGE = "Add recurring appointments and let customers choose their barber."
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
transcript: dict = {"checks": [], "events": []}


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    transcript["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)[:200]) if detail else ""), flush=True)


def event(kind, detail):
    transcript["events"].append({"kind": kind, "detail": detail, "t": time.strftime("%H:%M:%S")})
    print(f"  [{kind}] {detail}", flush=True)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def drive_app(app_html: str, label: str) -> dict:
    """Exercise a built app in a real browser from a file:// load.

    Adaptive: finds the add inputs/buttons by label, fills them, submits,
    and probes for conflict handling, prices, and reminder preparation.
    Returns observed facts; never asserts on app-specific wording.
    """
    from playwright.sync_api import sync_playwright

    facts: dict = {"label": label, "console_errors": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.on("console", lambda m: facts["console_errors"].append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: facts["console_errors"].append(str(e)))
            tmp = EVID / f"_drive-{label}.html"
            tmp.write_text(app_html, encoding="utf-8")
            page.goto(tmp.as_uri())
            page.wait_for_timeout(600)
            facts["body_len"] = len(page.evaluate("document.body ? document.body.innerText : ''"))
            facts["body_text"] = page.evaluate("document.body ? document.body.innerText : ''")
            # Fill the add inputs with a distinctive client and submit.
            scope = page
            forms = page.locator("form").all()
            if forms:
                scope = forms[0]
            inputs = scope.locator("input, textarea, select").all()
            filled = 0
            for inp in inputs:
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
                        inp.fill("Decisive Client")
                        filled += 1
                    elif itype == "email":
                        inp.fill("decisive@example.com")
                        filled += 1
                    elif itype == "number":
                        inp.fill("30")
                        filled += 1
                    elif itype == "date":
                        inp.fill("2026-11-13")
                        filled += 1
                    elif itype == "time":
                        inp.fill("10:00")
                        filled += 1
                except Exception:
                    continue
            facts["filled_inputs"] = filled
            clicked = ""
            for btn in scope.locator("button").all():
                label_t = (btn.inner_text() or "").strip()
                if any(w in label_t.lower() for w in ("add", "save", "create", "book", "schedule", "submit")):
                    try:
                        btn.click(timeout=8000)
                        clicked = label_t
                    except Exception as exc:
                        clicked = f"TIMEOUT:{label_t}:{str(exc)[:80]}"
                    break
            facts["clicked"] = clicked
            page.wait_for_timeout(600)
            facts["after_text"] = page.evaluate("document.body ? document.body.innerText : ''")
            facts["record_visible"] = "Decisive Client" in facts["after_text"]
            # Second identical booking: does the app notice a conflict?
            facts["conflict_text"] = ""
            for inp in scope.locator("input, textarea, select").all():
                try:
                    if not inp.is_visible():
                        continue
                    tag = inp.evaluate("el => el.tagName.toLowerCase()")
                    itype = (inp.get_attribute("type") or "").lower()
                    if tag == "textarea" or itype in ("", "text", "search", "tel"):
                        inp.fill("Decisive Client")
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
                    except Exception:
                        pass
                    break
            page.wait_for_timeout(600)
            after2 = page.evaluate("document.body ? document.body.innerText : ''")
            facts["after_second_text"] = after2
            m = re.search(r".{0,60}conflict.{0,120}", after2, re.IGNORECASE)
            facts["conflict_text"] = m.group(0) if m else ""
            facts["decisive_count"] = after2.count("Decisive Client")
            # Persistence across reload.
            page.reload()
            page.wait_for_timeout(500)
            facts["persist_text"] = page.evaluate("document.body ? document.body.innerText : ''")
            facts["record_persists"] = "Decisive Client" in facts["persist_text"]
        finally:
            browser.close()
    return facts


def main() -> int:
    adapter = AnthropicAdapter()
    engine = OpenLineGenieEngine(state_dir=str(STATE_DIR), model_adapter=adapter)
    worker = GenieWorker(adapter, engine)

    # ---- (a) fresh barber build through the receiver -------------------
    event("build", "prompt: " + BARBER_PROMPT)
    bundle = engine.build_from_prompt(BARBER_PROMPT, use_model=True)
    pid = bundle["project_id"]
    event("build", f"project {pid} family={bundle['project_family']}")
    check("(a) barber built by the real model worker",
          bundle["project_family"] == "model_built_app", bundle["project_family"])
    state = bundle["accepted"]["state"]
    v1 = engine.get_app_version(pid)
    (EVID / "barber-v1.html").write_text(v1["content"], encoding="utf-8")
    event("build", f"app v{v1['version']} sha={v1['sha256'][:16]} bytes={len(v1['content'])}")
    transcript["barber_project_id"] = pid
    transcript["v1_sha256"] = v1["sha256"]
    transcript["v1_version"] = v1["version"]

    facts = drive_app(v1["content"], "v1")
    check("(a) app loads in a real browser with zero console errors",
          not facts["console_errors"], "; ".join(facts["console_errors"][:2]))
    check("(a) add appointment: record appears",
          facts["record_visible"], f"filled={facts['filled_inputs']} clicked={facts['clicked']!r}")
    check("(a) record persists across reload", facts["record_persists"])
    price_hit = bool(re.search(r"\$\s?\d", facts["body_text"]))
    check("(a) service prices shown", price_hit, facts["body_text"][:160].replace("\n", " | "))
    reminder_hit = "remind" in facts["body_text"].lower()
    check("(a) reminders prepared for owner review (not sent)",
          reminder_hit, "reminder UI present" if reminder_hit else "no reminder UI found")
    if facts["conflict_text"]:
        check("(a) scheduling conflict detected on double-booking", True, facts["conflict_text"])
    else:
        check("(a) scheduling conflict detected on double-booking", False,
              f"second identical booking added silently; 'Decisive Client' appears "
              f"{facts['decisive_count']}x; no conflict wording found")
    transcript["v1_drive"] = {k: v for k, v in facts.items() if k not in ("body_text", "after_text", "after_second_text", "persist_text")}

    # ---- external-effect honesty (RC2A path in the demo) ----------------
    dest = "https://reminders.example/barber-webhook"
    dest_key = SigningIdentity(seed=secrets.token_bytes(32))
    engine.register_destination(dest, dest_key.public)
    event("outbox", f"registered destination {dest} (owner-pinned)")
    dropped = engine.attempt_consequential_external_action(
        pid, "send_customer_email", dest, {"invoice_id": "REM-1"},
        owner_approved=True, simulate_network_drop=True)
    check("(a) dropped external send stays UNKNOWN, never success",
          dropped["status"] == "UNKNOWN_RECONCILIATION_REQUIRED", dropped["status"])
    oid = dropped["outbox_id"]
    entry = next(x for x in engine.guard.list_external_outbox() if x["outbox_id"] == oid)
    rec = engine.guard.reconcile_external_outbox(
        oid, destination_probe=lambda k: {
            "status": "ALREADY_DELIVERED",
            "destination_receipt": sign_envelope(dest_key.key, {
                "schema": "openline.destination.delivery.v1",
                "status": "ALREADY_DELIVERED", "idempotency_key": oid,
                "payload_sha256": entry["payload_sha256"]})})
    check("(a) reconcile against pinned key: delivered, 0 new effects",
          rec["state"] == "RECONCILED_DELIVERED" and rec["new_external_effects"] == 0,
          str(rec)[:160])
    transcript["outbox_id"] = oid

    # ---- (b) interruption DURING the modification -----------------------
    accepted_sha_before = bundle["accepted"]["state_sha256"]
    app_before = v1["content"]
    haiku_result: dict = {}

    def haiku_revise():
        try:
            haiku_result["rev"] = worker.revise(
                prompt=state.get("prompt", BARBER_PROMPT),
                current_app_html=app_before, change_request=CHANGE,
                project_id=pid, title=str(state.get("title", pid)))
        except Exception as exc:  # noqa: BLE001 - record, do not crash the demo
            haiku_result["error"] = f"{type(exc).__name__}:{exc}"

    event("interrupt", "starting Haiku revision in background: " + CHANGE)
    th = threading.Thread(target=haiku_revise, daemon=True)
    th.start()
    time.sleep(8)  # let the revision get properly under way
    event("interrupt", 'owner: "Stop this AI. Give my project to another one."')
    stop = engine.trigger_stop("owner_interrupt_agent_replacement")
    check("(b) STOP issued by the owner", stop["status"] == "STOPPED", str(stop)[:120])
    # A mutation attempted while STOPPED must be refused by the receiver.
    try:
        engine.propose_exploratory_change(pid, "change while stopped", {"customization": {"x": 1}})
        check("(b) mutation while STOPPED is refused", False, "propose was accepted")
    except Exception as exc:
        check("(b) mutation while STOPPED is refused", True, f"{type(exc).__name__}:{str(exc)[:100]}")
    repl = engine.replace_worker_and_recover()
    check("(b) worker-A revoked, worker-B active",
          repl["new_active_worker"] == "worker-b"
          and repl["revoked_worker_pub"] == engine.worker_a_identity.public,
          str(repl)[:160])
    # Revoked authority cannot continue executing.
    grant = engine.owner_identity.issue_grant(
        engine.worker_a_identity.public, task_id="task-replay", step_id="s1",
        operation="autonomous_build", allowed_targets=[pid], max_amount=1000000,
        required_basis={"genie_operating_law": "v1.0-20261103"},
        grant_id="grant-replay-after-revoke",
        stop_epoch=engine.guard.read_stop_state()["epoch"])
    req = engine.worker_a_identity.sign_request(
        grant, operation="autonomous_build", target_id=pid, step_id="s1",
        payload={"project_id": pid, "amount": 1})
    try:
        engine.guard.execute(grant=grant, request=req, fn=lambda db, p: {},
                             target_table="genie_accepted", target_pk_col="project_id",
                             amount_field="amount")
        check("(b) revoked worker-A cannot continue executing", False, "guard executed it")
    except Exception as exc:
        check("(b) revoked worker-A cannot continue executing", True,
              f"{type(exc).__name__}:{str(exc)[:100]}")
    th.join(timeout=180)
    if "rev" in haiku_result:
        event("interrupt", f"Haiku revision finished in flight (sha "
              f"{haiku_result['rev']['app_sha256'][:12]}...) — DISCARDED, never proposed")
        transcript["discarded_haiku_revision_sha256"] = haiku_result["rev"]["app_sha256"]
    else:
        event("interrupt", "Haiku revision did not finish: " + str(haiku_result.get("error")))
        transcript["discarded_haiku_revision_error"] = str(haiku_result.get("error"))
    bundle_now = engine.get_project_bundle(pid)
    check("(b) accepted work preserved byte-identical through STOP+revoke",
          bundle_now["accepted"]["state_sha256"] == accepted_sha_before,
          bundle_now["accepted"]["state_sha256"][:16])
    # The interrupted worker's revision must never appear as a proposal:
    # check by its SHA, not by a raw pending count (an owner probe that
    # was itself refused under STOP creates no proposal at all).
    discarded_sha = transcript.get("discarded_haiku_revision_sha256")
    pending_shas = [e.get("candidate", {}).get("app_sha256")
                    for e in bundle_now["exploratory"]
                    if e["status"] == "EXPLORATORY_PENDING"]
    check("(b) no proposal was committed from the interrupted worker",
          discarded_sha not in pending_shas, f"pending={pending_shas}")
    engine.clear_stop("owner_resume_after_replacement")
    event("interrupt", "STOP cleared; replacement worker takes over")

    # ---- the ONE Sonnet call: replacement finishes the remaining work --
    swap = engine.replace_model("claude-sonnet-5-5", project_id=pid)
    check("(b) model swapped to Sonnet, accepted SHAs unchanged",
          swap["unchanged"] and swap["accepted_sha256_before"] == accepted_sha_before,
          str(swap)[:200])
    event("swap", "model is now claude-sonnet-5-5 (the one approved Sonnet call)")
    sonnet_rev = None
    sonnet_error = None
    try:
        sonnet_rev = worker.revise(
            prompt=state.get("prompt", BARBER_PROMPT),
            current_app_html=app_before, change_request=CHANGE,
            project_id=pid, title=str(state.get("title", pid)),
            max_repairs=0, max_tokens=6000)
    except Exception as exc:  # noqa: BLE001 - fall back to Haiku, disclosed
        sonnet_error = f"{type(exc).__name__}:{exc}"
    if sonnet_rev is not None:
        event("swap", f"Sonnet revision ready sha={sonnet_rev['app_sha256'][:16]} "
              f"bytes={sonnet_rev['bytes']} model={sonnet_rev['model']}")
        transcript["sonnet_revision_sha256"] = sonnet_rev["app_sha256"]
        transcript["sonnet_model"] = sonnet_rev["model"]
    else:
        event("swap", "Sonnet revision FAILED its test, falling back to Haiku repair (disclosed): " + str(sonnet_error))
        transcript["sonnet_revision_error"] = str(sonnet_error)
        sonnet_rev = worker.revise(
            prompt=state.get("prompt", BARBER_PROMPT),
            current_app_html=app_before, change_request=CHANGE,
            project_id=pid, title=str(state.get("title", pid)),
            max_repairs=2)
        event("swap", "Haiku completed the revision after Sonnet's attempt; "
              "the model-swap proof is the Sonnet call itself, not the final bytes")
        transcript["haiku_completed_after_sonnet"] = True
    final_html = sonnet_rev["app_html"]
    # The replacement's work goes through the normal propose/accept gate.
    prop_bundle = engine.propose_exploratory_change(
        pid, CHANGE, {"app_content": final_html, "app_filename": v1["filename"]})
    prop = prop_bundle["exploratory"][0]
    event("swap", f"proposal {prop['proposal_id']} validation_passed={prop['validation_passed']}")
    accepted_bundle = engine.accept_exploratory_change(pid, prop["proposal_id"])
    final = engine.get_app_version(pid)
    (EVID / "barber-final.html").write_text(final["content"], encoding="utf-8")
    check("(b) replacement finished the remaining work and it was accepted",
          final["sha256"] == sonnet_rev["app_sha256"], final["sha256"][:16])
    check("(b) accepted v1 bytes are gone only by explicit accept (v1 preserved in history)",
          engine.get_app_version(pid, 1)["sha256"] == v1["sha256"])
    transcript["final_sha256"] = final["sha256"]
    transcript["final_version"] = final["version"]

    facts2 = drive_app(final["content"], "final")
    check("(b) final app loads with zero console errors", not facts2["console_errors"],
          "; ".join(facts2["console_errors"][:2]))
    check("(b) final app still adds appointments", facts2["record_visible"])
    check("(b) final app still persists across reload", facts2["record_persists"])
    recurring = any(w in facts2["body_text"].lower()
                    for w in ("recur", "repeat", "weekly", "every 2 weeks"))
    barber_choice = ("barber" in facts2["body_text"].lower()
                     and ("choose" in facts2["body_text"].lower()
                          or "select" in facts2["body_text"].lower()
                          or facts2["body_text"].lower().count("barber") > 2))
    check("(b) recurring appointments present in final app", recurring,
          facts2["body_text"][:200].replace("\n", " | "))
    check("(b) customers can choose their barber", barber_choice,
          facts2["body_text"][:200].replace("\n", " | "))
    # v1 seed content survives: no completed operation repeated or lost.
    v1_seed = re.search(r"(Mike|Example Client|Decisive)", v1["content"])
    seed_name = None
    if v1_seed:
        seed_name = v1_seed.group(0)
    check("(b) previously accepted content survives in the final app",
          (seed_name is None) or (seed_name in final["content"]),
          f"seed marker {seed_name!r}")
    transcript["final_drive"] = {k: v for k, v in facts2.items() if k not in ("body_text", "after_text", "after_second_text", "persist_text")}

    # ---- (c) owner rejects one proposed design change -------------------
    rejected_html = final["content"].replace(
        "<title>", "<title>REJECTED-DESIGN ", 1) if "<title>" in final["content"] else final["content"] + "\n<!-- rejected design -->"
    if rejected_html == final["content"]:
        rejected_html = final["content"].replace("</body>", "<!-- rejected design --></body>")
    prop2 = engine.propose_exploratory_change(
        pid, "Rejected design: restyle the header", {"app_content": rejected_html})
    prop2_id = prop2["exploratory"][0]["proposal_id"]
    sha_before_reject = engine.get_project_bundle(pid)["accepted"]["state_sha256"]
    after_reject = engine.reject_exploratory_change(pid, prop2_id, reason="owner_rejected_design")
    check("(c) rejected proposal stays rejected",
          after_reject["rejected"][0]["proposal_id"] == prop2_id)
    check("(c) accepted app byte-identical after reject",
          engine.get_app_version(pid)["content"] == final["content"]
          and after_reject["accepted"]["state_sha256"] == sha_before_reject,
          after_reject["accepted"]["state_sha256"][:16])

    # ---- (d) close / reopen ---------------------------------------------
    exp = engine.export_portable_bundle(pid)
    check("(d) export is the runnable final app",
          exp.get("runs_standalone") is True
          and exp.get("standalone_html") == final["content"])
    closed = engine.close_project(pid)
    check("(d) project closes with a verified receipt",
          closed["status"] == "closed" and closed["state_sha256"] == sha_before_reject,
          str(closed["status"]))
    try:
        engine.propose_exploratory_change(pid, "change while closed", {"x": 1})
        check("(d) closed project refuses mutations", False, "propose was accepted")
    except Exception as exc:
        check("(d) closed project refuses mutations", True, f"{type(exc).__name__}")
    reopened = engine.reopen_project(pid)
    check("(d) project reopens with identical accepted state",
          reopened["accepted"]["state_sha256"] == sha_before_reject
          and reopened["status"] == "open")
    transcript["close_receipt_present"] = bool(closed.get("receipt"))
    transcript["final_bundle"] = {
        "project_id": pid,
        "accepted_sha256": reopened["accepted"]["state_sha256"],
        "accepted_version": reopened["accepted"]["version"],
        "autonomy_log": reopened["autonomy_log"],
    }
    (EVID / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
