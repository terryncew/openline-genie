#!/usr/bin/env python3
"""RC3 backend tests for OpenLine Genie — NO model calls.

Uses a fake adapter returning canned spec/app content. Covers: adapter
cap enforcement + spend logging (stubbed subprocess), worker build with
a fake adapter, artifact versioning + reject-restore byte identity,
model swap preserving accepted SHA-256, close blocking mutation +
reopen verification, deterministic fallback without an adapter, and the
new HTTP endpoints.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from genie_engine import OpenLineGenieEngine
from genie_server import GenieRequestHandler
from core import model_adapter as ma
from core.model_adapter import AnthropicAdapter, ModelError, SpendCapExceeded, SpendLedger

CANNED_SPEC = {
    "title": "Mobile Barber Booking & Reminders",
    "family": "booking_reminders",
    "data_model": [
        {"key": "client_name", "label": "Client Name", "type": "text"},
        {"key": "service", "label": "Service", "type": "text"},
        {"key": "date", "label": "Date", "type": "date"},
        {"key": "price_dollars", "label": "Price ($)", "type": "number"},
    ],
    "features": ["add/list bookings", "live booking count", "delete a booking"],
    "ui_layout": "Form on top, booking list below, total count at the bottom.",
}

CANNED_APP = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Mobile Barber Booking &amp; Reminders</title>
<style>body{font-family:sans-serif;margin:16px}</style></head>
<body>
<h1>Mobile Barber Booking &amp; Reminders</h1>
<form id="add-form">
<input id="client" type="text" placeholder="Client name">
<input id="service" type="text" placeholder="Service">
<input id="date" type="date">
<input id="price" type="number" placeholder="Price">
<button type="button" id="add-btn">Add Booking</button>
</form>
<ul id="list"></ul>
<p>Total bookings: <span id="total">0</span></p>
<script>
const KEY='mobile-barber-booking-v1';
let MEM=null;
function load(){try{const s=localStorage.getItem(KEY);if(s===null)return MEM||[];const v=JSON.parse(s);MEM=v;return v}catch(e){return MEM||[]}}
function save(items){MEM=items;try{localStorage.setItem(KEY,JSON.stringify(items))}catch(e){}}
function render(){const items=load();const ul=document.getElementById('list');ul.innerHTML='';items.forEach((it,i)=>{const li=document.createElement('li');li.textContent=it.name+' - '+it.service;const b=document.createElement('button');b.textContent='Delete';b.onclick=()=>{const cur=load();cur.splice(i,1);save(cur);render()};li.appendChild(b);ul.appendChild(li)});document.getElementById('total').textContent=String(items.length)}
document.getElementById('add-btn').addEventListener('click',()=>{const name=document.getElementById('client').value.trim();const service=document.getElementById('service').value.trim();if(!name)return;const items=load();items.push({name:name,service:service});save(items);render();document.getElementById('add-form').reset()});
render();
</script>
</body>
</html>"""

CANNED_APP_V2 = CANNED_APP.replace(
    "<h1>Mobile Barber Booking &amp; Reminders</h1>",
    "<h1>Mobile Barber Booking &amp; Reminders v2</h1>",
)
CANNED_APP_V3 = CANNED_APP.replace(
    "<h1>Mobile Barber Booking &amp; Reminders</h1>",
    "<h1>Mobile Barber Booking &amp; Reminders v3</h1>",
)


class FakeAdapter(ma.ModelAdapter):
    """Returns canned spec then canned app; records every call."""

    model = "fake-test-model"
    available = True
    calls: list[dict]

    def __init__(self) -> None:
        self.calls = []

    def complete(self, system: str, user: str, max_tokens: int = 8000, purpose: str = "") -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens, "purpose": purpose})
        if "JSON object" in system:
            text = json.dumps(CANNED_SPEC)
        else:
            text = CANNED_APP
        return {
            "text": text,
            "input_tokens": 10,
            "output_tokens": 20,
            "model": self.model,
            "message_id": f"fake-msg-{len(self.calls)}",
        }


class ExplodingAdapter(ma.ModelAdapter):
    model = "exploding-test-model"
    available = True

    def complete(self, system: str, user: str, max_tokens: int = 8000, purpose: str = ""):
        raise AssertionError("fake adapter must not be called on this path")


def _post(base: str, path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as ex:
        return ex.code, json.loads(ex.read())


def _get(base: str, path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(base + path, timeout=10) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as ex:
        return ex.code, json.loads(ex.read())


class GenieRC3BackendSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="genie-rc3-test-")
        self.ledger_dir = Path(self.tmp.name) / "ledger"
        self.ledger_dir.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # -- adapter: cap + logging -------------------------------------------
    def test_adapter_cap_refuses_before_call(self) -> None:
        adapter = AnthropicAdapter(ledger_dir=self.ledger_dir, sub_budget_usd=0.000001)
        with self.assertRaises(SpendCapExceeded):
            adapter.complete("sys", "hello", max_tokens=100)
        # Refused before any call: nothing recorded.
        self.assertEqual(SpendLedger(self.ledger_dir).total_usd(), 0.0)
        self.assertEqual(SpendLedger(self.ledger_dir).calls(), [])

    def test_adapter_logs_spend_from_stubbed_helper(self) -> None:
        adapter = AnthropicAdapter(ledger_dir=self.ledger_dir, sub_budget_usd=1.50)
        fake_stdout = json.dumps(
            {
                "id": "msg_test123",
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )

        class FakeProc:
            stdout = fake_stdout

        orig_run = ma.subprocess.run
        ma.subprocess.run = lambda *a, **k: FakeProc()  # type: ignore[assignment]
        try:
            out = adapter.complete("sys", "hello", max_tokens=100)
        finally:
            ma.subprocess.run = orig_run
        self.assertEqual(out["text"], "hello")
        self.assertEqual(out["message_id"], "msg_test123")
        # 10 * 0.10e-6 + 5 * 0.50e-6 = 3.5e-6
        self.assertAlmostEqual(SpendLedger(self.ledger_dir).total_usd(), 3.5e-6)
        calls = SpendLedger(self.ledger_dir).calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["message_id"], "msg_test123")
        self.assertIn("msg_test123", (self.ledger_dir / "SPEND_LEDGER.md").read_text())

    def test_adapter_http_error_surfaces_without_retry_or_spend(self) -> None:
        adapter = AnthropicAdapter(ledger_dir=self.ledger_dir, sub_budget_usd=1.50)

        class FakeProc:
            stdout = json.dumps({"_http_error": 429, "_body": "rate limited"})

        orig_run = ma.subprocess.run
        ma.subprocess.run = lambda *a, **k: FakeProc()  # type: ignore[assignment]
        try:
            with self.assertRaises(ModelError):
                adapter.complete("sys", "hello", max_tokens=100)
        finally:
            ma.subprocess.run = orig_run
        self.assertEqual(SpendLedger(self.ledger_dir).total_usd(), 0.0)

    # -- worker with fake adapter ------------------------------------------
    def test_worker_build_with_fake_adapter(self) -> None:
        adapter = FakeAdapter()
        engine = OpenLineGenieEngine(state_dir=self.tmp.name, model_adapter=adapter)
        bundle = engine.build_from_prompt("Build a free booking and reminder tool for a mobile barber")
        st = bundle["accepted"]["state"]
        self.assertEqual(st["project_family"], "model_built_app")
        self.assertEqual(st["schema"], "openline.genie.model_built_app.v1")
        self.assertEqual(st["app_version"], 1)
        self.assertEqual(st["app_sha256"], hashlib.sha256(CANNED_APP.encode()).hexdigest())
        artifact = engine.get_app_version(st["project_id"])
        self.assertEqual(artifact["content"], CANNED_APP)
        self.assertEqual(artifact["status"], "accepted")
        self.assertEqual(len(adapter.calls), 2)  # understand + build, no repair needed
        provs = {row["provenance"] for row in bundle["autonomy_log"]}
        self.assertIn("MODEL_WORKER:fake-test-model", provs)
        stages = [row["stage"] for row in bundle["autonomy_log"]]
        self.assertTrue(any("Understand Goal" in s for s in stages))
        self.assertTrue(any("Test App" in s for s in stages))
        # Export is the runnable app, byte-identical to the artifact.
        exp = engine.export_portable_bundle(st["project_id"])
        self.assertTrue(exp["runs_standalone"])
        self.assertEqual(exp["standalone_html"], CANNED_APP)
        self.assertEqual(exp["app_sha256"], st["app_sha256"])

    def test_artifact_versioning_reject_restores_byte_identity(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name, model_adapter=FakeAdapter())
        bundle = engine.build_from_prompt("Build a free booking and reminder tool for a mobile barber")
        pid = bundle["project_id"]
        sha_v1 = bundle["accepted"]["state_sha256"]
        app_sha_v1 = bundle["accepted"]["state"]["app_sha256"]

        # Propose v2 app content, accept it.
        prop = engine.propose_exploratory_change(pid, "v2 redesign", {"app_content": CANNED_APP_V2})
        prop_id = prop["exploratory"][0]["proposal_id"]
        accepted = engine.accept_exploratory_change(pid, prop_id)
        self.assertEqual(accepted["accepted"]["state"]["app_version"], 2)
        self.assertEqual(accepted["accepted"]["state"]["app_sha256"], hashlib.sha256(CANNED_APP_V2.encode()).hexdigest())
        self.assertEqual(engine.get_app_version(pid)["content"], CANNED_APP_V2)
        sha_after_v2 = accepted["accepted"]["state_sha256"]

        # Propose v3 app content, reject it: accepted bytes must be untouched.
        prop3 = engine.propose_exploratory_change(pid, "v3 redesign", {"app_content": CANNED_APP_V3})
        prop3_id = prop3["exploratory"][0]["proposal_id"]
        after_reject = engine.reject_exploratory_change(pid, prop3_id, reason="user_rejected_v3")
        self.assertEqual(after_reject["accepted"]["state_sha256"], sha_after_v2)
        self.assertEqual(engine.get_app_version(pid)["content"], CANNED_APP_V2)
        self.assertEqual(engine.get_app_version(pid, 2)["content"], CANNED_APP_V2)
        self.assertEqual(engine.get_app_version(pid, 3)["status"], "rejected")
        self.assertEqual(engine.get_app_version(pid, 1)["content"], CANNED_APP)
        # v1 history survives; v1 sha still matches the original build.
        self.assertEqual(after_reject["accepted"]["state"]["app_sha256"], hashlib.sha256(CANNED_APP_V2.encode()).hexdigest())
        self.assertNotEqual(sha_after_v2, sha_v1)
        self.assertEqual(app_sha_v1, hashlib.sha256(CANNED_APP.encode()).hexdigest())

    # -- model swap / close / reopen ---------------------------------------
    def test_model_swap_leaves_accepted_sha_unchanged(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name, model_adapter=FakeAdapter())
        before = {p["project_id"]: p["state_sha256"] for p in engine.list_projects()}
        res = engine.replace_model("claude-sonnet-5-5")
        self.assertTrue(res["unchanged"])
        self.assertTrue(res["all_projects_unchanged"])
        self.assertEqual(res["previous_model"], "fake-test-model")
        self.assertEqual(res["model"], "claude-sonnet-5-5")
        self.assertEqual(res["accepted_sha256_before"], res["accepted_sha256_after"])
        after = {p["project_id"]: p["state_sha256"] for p in engine.list_projects()}
        self.assertEqual(before, after)
        self.assertEqual(engine.get_status()["model_id"], "claude-sonnet-5-5")
        # Swap back; the adapter follows the recorded model id.
        engine.replace_model("claude-haiku-5-5")
        self.assertEqual(engine.model_adapter.model, "claude-haiku-5-5")

    def test_stop_blocks_propose_and_accept_but_not_reject(self) -> None:
        """STOP is a full freeze on new proposals and accepts (RC3 fix).

        Found by the decisive test: propose_exploratory_change accepted a
        proposal while STOPPED because it never touched the guard. Reject
        stays allowed: it is an owner safety action, not a mutation of
        accepted state.
        """
        from core.openline_guard import GuardRefused

        engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        pid = "demo-a-service-quoting"
        engine.trigger_stop("test_stop_freeze")
        with self.assertRaises(GuardRefused):
            engine.propose_exploratory_change(pid, "change while stopped", {"customization": {"x": 1}})
        # A proposal made before the stop still cannot be accepted under it.
        engine.clear_stop("test_setup")
        before = engine.propose_exploratory_change(pid, "pre-stop proposal", {"customization": {"x": 2}})
        prop_id = before["exploratory"][0]["proposal_id"]
        engine.trigger_stop("test_stop_freeze_2")
        with self.assertRaises(GuardRefused):
            engine.accept_exploratory_change(pid, prop_id)
        # Reject is the owner's safety action and stays available.
        engine.reject_exploratory_change(pid, prop_id, reason="owner_rejected_under_stop")
        self.assertEqual(
            engine.get_project_bundle(pid)["rejected"][0]["proposal_id"], prop_id)
        engine.clear_stop("test_resume")
        after = engine.propose_exploratory_change(pid, "after clear", {"customization": {"x": 3}})
        self.assertEqual(after["exploratory"][0]["status"], "EXPLORATORY_PENDING")

    def test_worker_succession_survives_engine_restart(self) -> None:
        """Worker succession is persisted, not in-memory only (RC3 fix).

        Found by the decisive addendum: after replace_worker_and_recover,
        a fresh engine on the same state dir defaulted to revoked
        worker-A and every commit failed with worker_revoked.
        """
        engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        pid = "demo-a-service-quoting"
        before = engine.propose_exploratory_change(pid, "pre-succession", {"customization": {"x": 1}})
        engine.accept_exploratory_change(pid, before["exploratory"][0]["proposal_id"])
        engine.replace_worker_and_recover()
        self.assertEqual(engine.active_worker_id, "worker-b")
        # A fresh engine on the same state dir must pick up worker-B.
        engine2 = OpenLineGenieEngine(state_dir=self.tmp.name)
        self.assertEqual(engine2.active_worker_id, "worker-b")
        after = engine2.propose_exploratory_change(pid, "post-restart", {"customization": {"x": 2}})
        accepted = engine2.accept_exploratory_change(pid, after["exploratory"][0]["proposal_id"])
        self.assertEqual(accepted["accepted"]["state"]["customization"]["x"], 2)

    def test_pre_fix_succession_derived_from_revocation_ledger(self) -> None:
        """A succession performed before the pointer existed is derived.

        Simulates the pre-fix state: worker-a revoked via the guard with
        no persisted active-worker pointer. A fresh engine must derive
        worker-b from the revocation ledger and persist the pointer.
        """
        engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        engine.guard.revoke_worker(engine.worker_a_identity.public, reason="test_pre_fix")
        engine2 = OpenLineGenieEngine(state_dir=self.tmp.name)
        self.assertEqual(engine2.active_worker_id, "worker-b")
        self.assertEqual(engine2.guard.get_active_worker_pub(), engine2.worker_b_identity.public)
        pid = "demo-a-service-quoting"
        prop = engine2.propose_exploratory_change(pid, "post-migration", {"customization": {"x": 9}})
        accepted = engine2.accept_exploratory_change(pid, prop["exploratory"][0]["proposal_id"])
        self.assertEqual(accepted["accepted"]["state"]["customization"]["x"], 9)

    def test_close_blocks_mutation_and_reopen_verifies(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        pid = "demo-a-service-quoting"
        closed = engine.close_project(pid)
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(engine.get_project_bundle(pid)["status"], "closed")
        with self.assertRaises(ValueError):
            engine.close_project(pid)
        with self.assertRaises(PermissionError):
            engine.demo_a_add_or_update_quote(
                customer_id="CUST-101",
                customer_name="Maria Chen",
                items=[{"service_id": "SRV-01", "quantity": 1, "unit_price_dollars": 10, "taxable": False}],
            )
        with self.assertRaises(PermissionError):
            engine.propose_exploratory_change(pid, "change while closed", {"customization": {"payment_terms": "Net 30"}})
        sha_closed = engine.get_project_bundle(pid)["accepted"]["state_sha256"]
        reopened = engine.reopen_project(pid)
        self.assertEqual(reopened["status"], "open")
        self.assertEqual(reopened["accepted"]["state_sha256"], sha_closed)
        with self.assertRaises(ValueError):
            engine.reopen_project(pid)
        # Mutations work again after reopen.
        engine.demo_a_add_or_update_quote(
            customer_id="CUST-101",
            customer_name="Maria Chen",
            items=[{"service_id": "SRV-01", "quantity": 1, "unit_price_dollars": 10, "taxable": False}],
        )

    # -- deterministic behavior without a model -----------------------------
    def test_no_adapter_unfamiliar_prompt_stays_deterministic(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        bundle = engine.build_from_prompt("Build a free booking and reminder tool for a mobile barber")
        self.assertEqual(bundle["accepted"]["state"]["schema"], "openline.genie.synthesized_app.v1")

    def test_worker_failure_falls_back_to_deterministic_synthesizer(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name, model_adapter=ExplodingAdapter())
        bundle = engine.build_from_prompt("Build a free booking and reminder tool for a mobile barber")
        self.assertEqual(bundle["accepted"]["state"]["schema"], "openline.genie.synthesized_app.v1")
        stages = [row["stage"] for row in bundle["autonomy_log"]]
        self.assertIn("0. Model Worker Fallback", stages)
        # Fixture prompts never touch the adapter at all.
        engine2 = OpenLineGenieEngine(state_dir=self.tmp.name + "-b", model_adapter=ExplodingAdapter())
        fixture = engine2.build_from_prompt("Build a free quoting and invoicing tool for my small service business.")
        self.assertEqual(fixture["accepted"]["state"]["project_family"], "service_quoting_invoicing")

    def test_export_without_artifact_stays_read_only_snapshot(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        exp = engine.export_portable_bundle("demo-a-service-quoting")
        self.assertFalse(exp["runs_standalone"])
        self.assertIsNone(exp["app_sha256"])
        self.assertIn("PORTABLE STANDALONE EXPORT", exp["standalone_html"])

    # -- HTTP endpoints ------------------------------------------------------
    def test_new_api_endpoints(self) -> None:
        engine = OpenLineGenieEngine(state_dir=self.tmp.name, model_adapter=FakeAdapter())
        engine.build_from_prompt("Build a free booking and reminder tool for a mobile barber")
        GenieRequestHandler.engine = engine
        srv = ThreadingHTTPServer(("127.0.0.1", 0), GenieRequestHandler)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_port}"
        try:
            code, status = _get(base, "/api/status")
            self.assertEqual(code, 200)
            self.assertEqual(status["model_id"], "fake-test-model")
            self.assertTrue(status["model_available"])
            self.assertEqual(status["cap_usd"], 5.0)

            code, swapped = _post(base, "/api/replace_model", {"model": "claude-haiku-5-5"})
            self.assertEqual(code, 200)
            self.assertTrue(swapped["unchanged"])
            self.assertEqual(swapped["model"], "claude-haiku-5-5")

            pid = "genie-model-mobile-barber-booking-reminders"
            code, artifact = _get(base, f"/api/artifact?project_id={pid}")
            self.assertEqual(code, 200)
            self.assertEqual(artifact["content"], CANNED_APP)
            self.assertEqual(artifact["sha256"], hashlib.sha256(CANNED_APP.encode()).hexdigest())
            code, missing = _get(base, "/api/artifact?project_id=demo-a-service-quoting")
            self.assertEqual(code, 404)

            code, closed = _post(base, "/api/close", {"project_id": "demo-a-service-quoting"})
            self.assertEqual(code, 200)
            self.assertEqual(closed["status"], "closed")
            code, blocked = _post(
                base,
                "/api/demo_a/quote",
                {"customer_id": "CUST-101", "customer_name": "X", "items": []},
            )
            self.assertEqual(code, 400)  # closed project refuses the mutation
            code, reopened = _post(base, "/api/reopen", {"project_id": "demo-a-service-quoting"})
            self.assertEqual(code, 200)
            self.assertEqual(reopened["status"], "open")

            code, built = _post(
                base,
                "/api/build",
                {"prompt": "Build a free quoting tool for my shop.", "use_model": False},
            )
            self.assertEqual(code, 200)
            self.assertEqual(built["accepted"]["state"]["project_family"], "service_quoting_invoicing")
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
