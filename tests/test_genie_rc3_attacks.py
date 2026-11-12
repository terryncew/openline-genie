#!/usr/bin/env python3
"""Attack tests for OpenLine Genie RC3 (Step 3): prove the boundary.

Each test attempts a real attack or failure against the integrated
engine/guard and asserts the fail-closed outcome. No model calls.
No network. The signed-destination test double is shared with the
ported RC2A pin tests.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from core.openline_guard import GuardRefused, SigningIdentity, sign_envelope
from tests.test_rc2a_destination_key_pin import _Endpoint


def _epoch(engine):
    return engine.guard.read_stop_state()["epoch"]


class AttackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        self.guard = self.engine.guard

    # -- helpers ---------------------------------------------------------
    def _stage(self, dest, payload, step_id):
        """Stage one external effect through a guarded commit (no flush)."""
        staged = []
        worker = self.engine._active_worker()
        grant = self.engine.owner_identity.issue_grant(
            worker.public, task_id="task-attack", step_id=step_id,
            operation="send_customer_email", allowed_targets=["demo-a-service-quoting"],
            max_amount=50000,
            required_basis={"genie_operating_law": "v1.0-20261103"},
            grant_id=f"grant-attack-{step_id}",
            stop_epoch=_epoch(self.engine))
        req = worker.sign_request(
            grant, operation="send_customer_email",
            target_id="demo-a-service-quoting", step_id=step_id,
            payload={"project_id": "demo-a-service-quoting", "amount": 1, **payload})

        def _apply(db, p):
            oid = self.guard.stage_external_effect(
                db, task_id="task-attack", step_id=step_id,
                channel="webhook", destination=dest, payload=payload)
            staged.append(oid)
            return {"outbox_id": oid}

        receipt = self.guard.execute(
            grant=grant, request=req, fn=_apply,
            target_table="genie_accepted", target_pk_col="project_id",
            amount_field="amount")
        return staged[0], receipt

    def _items_table(self):
        with sqlite3.connect(self.guard.db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, val INTEGER)")
            db.execute("INSERT OR IGNORE INTO items VALUES ('i1', 1)")
            db.commit()

    # -- 1. forged acknowledgments ---------------------------------------
    def test_forged_delivery_acknowledgment_stays_unknown(self):
        real = _Endpoint("real-dest", bytes.fromhex("a1" * 32))
        rogue = _Endpoint("rogue-dest", bytes.fromhex("a2" * 32))
        dest = "https://notify.example/webhook"
        self.engine.register_destination(dest, real.public_key)
        # Row 1: rogue dispatcher returns a correctly-shaped receipt
        # signed by the ROGUE key. Must stay UNKNOWN, 0 dispatched.
        oid1, _ = self._stage(dest, {"invoice_id": "INV-1"}, "s-forge-1")
        out = self.guard.flush_external_outbox(rogue.receive_webhook)
        self.assertEqual(out, [])
        row1 = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid1)
        self.assertEqual(row1["state"], "UNKNOWN_RECONCILIATION_REQUIRED")
        self.assertEqual(len(rogue.delivered), 1)  # rogue saw it; trust did not follow
        # Row 2: the real destination's signed receipt dispatches exactly once.
        oid2, _ = self._stage(dest, {"invoice_id": "INV-2"}, "s-forge-2")
        out = self.guard.flush_external_outbox(real.receive_webhook)
        self.assertEqual(len(out), 1)
        row2 = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid2)
        self.assertEqual(row2["state"], "DISPATCHED")
        # A later flush never re-sends either row.
        out = self.guard.flush_external_outbox(real.receive_webhook)
        self.assertEqual(out, [])
        self.assertEqual(len(real.delivered), 1)
        row1 = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid1)
        self.assertEqual(row1["state"], "UNKNOWN_RECONCILIATION_REQUIRED")

    # -- 2. caller-supplied keys ------------------------------------------
    def test_caller_supplied_destination_key_cannot_establish_trust(self):
        real = _Endpoint("real-dest", bytes.fromhex("b1" * 32))
        rogue = _Endpoint("rogue-dest", bytes.fromhex("b2" * 32))
        dest = "https://notify.example/key-swap"
        # No registration at all: even the real endpoint's receipt is refused.
        oid, _ = self._stage(dest, {"invoice_id": "INV-9"}, "s-key-1")
        self.assertEqual(self.guard.flush_external_outbox(real.receive_webhook), [])
        row = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid)
        self.assertEqual(row["state"], "UNKNOWN_RECONCILIATION_REQUIRED")
        # Owner pins the ROGUE key by mistake: the real receipt still fails,
        # and that row stays UNKNOWN (no silent retry of unknown effects).
        self.engine.register_destination(dest, rogue.public_key)
        oid2, _ = self._stage(dest, {"invoice_id": "INV-10"}, "s-key-2")
        self.assertEqual(self.guard.flush_external_outbox(real.receive_webhook), [])
        self.assertEqual(
            next(x for x in self.guard.list_external_outbox()
                 if x["outbox_id"] == oid2)["state"],
            "UNKNOWN_RECONCILIATION_REQUIRED")
        # Owner corrects the pin: a NEW row with the real receipt dispatches.
        self.engine.register_destination(dest, real.public_key)
        oid3, _ = self._stage(dest, {"invoice_id": "INV-11"}, "s-key-3")
        out = self.guard.flush_external_outbox(real.receive_webhook)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["outbox_id"], oid3)

    # -- 3. missing / mismatched receipts on reconcile --------------------
    def test_missing_or_mismatched_receipt_on_reconcile(self):
        real = _Endpoint("real-dest", bytes.fromhex("c1" * 32))
        dest = "https://notify.example/reconcile"
        self.engine.register_destination(dest, real.public_key)
        dropped = self.engine.attempt_consequential_external_action(
            "demo-a-service-quoting", "send_customer_email", dest,
            {"invoice_id": "INV-2001"}, owner_approved=True,
            simulate_network_drop=True)
        self.assertEqual(dropped["status"], "UNKNOWN_RECONCILIATION_REQUIRED")
        oid = dropped["outbox_id"]
        entry = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid)
        # (a) probe with no receipt at all
        with self.assertRaises(ValueError):
            self.guard.reconcile_external_outbox(
                oid, destination_probe=lambda k: {"status": "ALREADY_DELIVERED"})
        # (b) receipt bound to a different outbox id
        wrong = sign_envelope(real.identity.key, {
            "schema": "openline.destination.delivery.v1",
            "status": "ALREADY_DELIVERED", "idempotency_key": "0" * 64,
            "payload_sha256": entry["payload_sha256"]})
        with self.assertRaises(ValueError):
            self.guard.reconcile_external_outbox(
                oid, destination_probe=lambda k: {
                    "status": "ALREADY_DELIVERED", "destination_receipt": wrong})
        # (c) receipt signed by a key that is not the pinned one
        rogue = _Endpoint("rogue", bytes.fromhex("c2" * 32))
        forged = sign_envelope(rogue.identity.key, {
            "schema": "openline.destination.delivery.v1",
            "status": "ALREADY_DELIVERED", "idempotency_key": oid,
            "payload_sha256": entry["payload_sha256"]})
        # Bad signature surfaces as VerificationError; either way the
        # reconciliation is refused and the row stays UNKNOWN.
        from core.openline_guard import VerificationError
        with self.assertRaises((ValueError, VerificationError)):
            self.guard.reconcile_external_outbox(
                oid, destination_probe=lambda k: {
                    "status": "ALREADY_DELIVERED", "destination_receipt": forged})
        self.assertEqual(
            next(x for x in self.guard.list_external_outbox()
                 if x["outbox_id"] == oid)["state"],
            "UNKNOWN_RECONCILIATION_REQUIRED")
        # (d) the genuine probe reconciles with zero new effects.
        rec = self.guard.reconcile_external_outbox(
            oid, destination_probe=lambda k: {
                "status": "ALREADY_DELIVERED",
                "destination_receipt": sign_envelope(real.identity.key, {
                    "schema": "openline.destination.delivery.v1",
                    "status": "ALREADY_DELIVERED", "idempotency_key": oid,
                    "payload_sha256": entry["payload_sha256"]})})
        self.assertEqual(rec["state"], "RECONCILED_DELIVERED")
        self.assertEqual(rec["new_external_effects"], 0)

    # -- 4. STOP during execution -----------------------------------------
    def test_stop_during_execution_blocks_commit_and_rolls_back(self):
        self._items_table()
        worker = self.engine._active_worker()
        grant = self.engine.owner_identity.issue_grant(
            worker.public, task_id="t-stop-mid", step_id="s1",
            operation="op.1", allowed_targets=["i1"], grant_id="g-stop-mid",
            expires=1894390000, stop_epoch=_epoch(self.engine))
        req = worker.sign_request(grant, operation="op.1", target_id="i1",
                                  step_id="s1", payload={"v": 1})

        def effect(db, payload):
            db.execute("UPDATE items SET val=990 WHERE id='i1'")
            self.guard.stage_external_effect(
                db, task_id="t-stop-mid", step_id="s1", channel="webhook",
                destination="https://example.invalid/hook", payload={"v": 1})

        def stop_midway():
            self.engine.trigger_stop("attack_test_stop_mid_execution")

        with self.assertRaises((ValueError, GuardRefused)):
            self.guard.execute(grant=grant, request=req, fn=effect,
                               target_table="items", target_pk_col="id",
                               pre_commit_hook=stop_midway)
        with sqlite3.connect(self.guard.db_path) as db:
            self.assertEqual(db.execute("SELECT val FROM items WHERE id='i1'").fetchone()[0], 1)
        self.assertEqual(self.guard.list_external_outbox(task_id="t-stop-mid"), [])
        self.engine.clear_stop("attack_test_resume")
        # The engine commits again after the clear (post-stop epoch binding).
        after = self.engine.demo_a_add_or_update_quote(
            customer_id="CUST-101", customer_name="Maria Chen",
            items=[{"service_id": "SRV-01", "description": "Cleanup", "unit": "visit",
                    "quantity": 1, "unit_price_dollars": 165.00, "taxable": False}])
        self.assertIn("accepted", after)

    # -- 5. worker replacement during a partial commit --------------------
    def test_worker_replacement_during_partial_commit(self):
        self._items_table()
        worker_a = self.engine.worker_a_identity
        grant = self.engine.owner_identity.issue_grant(
            worker_a.public, task_id="t-revoke-mid", step_id="s1",
            operation="op.1", allowed_targets=["i1"], grant_id="g-revoke-mid",
            expires=1894390000, stop_epoch=_epoch(self.engine))
        req = worker_a.sign_request(grant, operation="op.1", target_id="i1",
                                    step_id="s1", payload={"v": 1})

        def effect(db, payload):
            db.execute("UPDATE items SET val=990 WHERE id='i1'")

        def revoke_midway():
            self.guard.revoke_worker(worker_a.public, reason="attack_test_revoke_mid_task")

        with self.assertRaises((ValueError, GuardRefused)):
            self.guard.execute(grant=grant, request=req, fn=effect,
                               target_table="items", target_pk_col="id",
                               pre_commit_hook=revoke_midway)
        with sqlite3.connect(self.guard.db_path) as db:
            self.assertEqual(db.execute("SELECT val FROM items WHERE id='i1'").fetchone()[0], 1)
        # Worker B continues; accepted work is intact.
        succ = self.engine.replace_worker_and_recover()
        self.assertEqual(succ["new_active_worker"], "worker-b")
        after = self.engine.demo_a_add_or_update_quote(
            customer_id="CUST-101", customer_name="Maria Chen",
            items=[{"service_id": "SRV-01", "description": "Cleanup", "unit": "visit",
                    "quantity": 1, "unit_price_dollars": 165.00, "taxable": False}])
        self.assertEqual(after["active_worker_id"], "worker-b")

    # -- 6. replayed actions after revocation ------------------------------
    def test_replayed_actions_after_revocation_refused(self):
        worker_a = self.engine.worker_a_identity
        before = self.engine.demo_a_add_or_update_quote(
            customer_id="CUST-101", customer_name="Maria Chen",
            items=[{"service_id": "SRV-01", "description": "Cleanup", "unit": "visit",
                    "quantity": 1, "unit_price_dollars": 165.00, "taxable": False}])
        n_before = len(before["accepted"]["state"]["quotes"])
        self.engine.replace_worker_and_recover()
        # Replay worker A's exact grant/request: the receiver refuses.
        grant = self.engine.owner_identity.issue_grant(
            worker_a.public, task_id="task-demo-a-service-quoting",
            step_id="replay-1", operation="autonomous_build",
            allowed_targets=["demo-a-service-quoting"], max_amount=1000000,
            required_basis={"genie_operating_law": "v1.0-20261103"},
            grant_id="grant-replay-1", stop_epoch=_epoch(self.engine))
        req = worker_a.sign_request(
            grant, operation="autonomous_build",
            target_id="demo-a-service-quoting", step_id="replay-1",
            payload={"project_id": "demo-a-service-quoting", "amount": 1})

        def noop(db, payload):
            return {}

        with self.assertRaises((ValueError, GuardRefused)):
            self.guard.execute(grant=grant, request=req, fn=noop,
                               target_table="genie_accepted",
                               target_pk_col="project_id", amount_field="amount")
        after = self.engine.get_project_bundle("demo-a-service-quoting")
        self.assertEqual(len(after["accepted"]["state"]["quotes"]), n_before)

    def test_idempotent_replay_of_committed_grant_does_not_duplicate(self):
        # Same grant + same payload executed twice while CURRENT: the second
        # execution is idempotent — no duplicate effect, same receipt.
        before = self.engine.demo_a_add_or_update_quote(
            customer_id="CUST-101", customer_name="Maria Chen",
            items=[{"service_id": "SRV-01", "description": "Cleanup", "unit": "visit",
                    "quantity": 1, "unit_price_dollars": 165.00, "taxable": False}])
        n_before = len(before["accepted"]["state"]["quotes"])
        # A second identical demo-A mutation is a NEW grant (new version),
        # so instead replay at the guard level with the same grant/request.
        self._items_table()
        worker = self.engine._active_worker()
        grant = self.engine.owner_identity.issue_grant(
            worker.public, task_id="t-idem", step_id="s1", operation="op.1",
            allowed_targets=["i1"], grant_id="g-idem", expires=1894390000,
            stop_epoch=_epoch(self.engine))
        req = worker.sign_request(grant, operation="op.1", target_id="i1",
                                  step_id="s1", payload={"v": 1})

        def effect(db, payload):
            db.execute("UPDATE items SET val=val+10 WHERE id='i1'")

        r1 = self.guard.execute(grant=grant, request=req, fn=effect,
                                target_table="items", target_pk_col="id")
        r2 = self.guard.execute(grant=grant, request=req, fn=effect,
                                target_table="items", target_pk_col="id")
        self.assertEqual(r1["receipt"]["payload_sha256"],
                         r2["receipt"]["payload_sha256"])
        with sqlite3.connect(self.guard.db_path) as db:
            self.assertEqual(db.execute("SELECT val FROM items WHERE id='i1'").fetchone()[0], 11)

    # -- 7. upstream reopen blocks downstream ------------------------------
    def test_upstream_reopen_blocks_downstream_decisions(self):
        self._items_table()
        self.guard.set_basis("test_basis", "v1")
        worker = self.engine._active_worker()

        def run_op(task, step, grant_id, upstream=None, up_sha=None, basis="v1"):
            grant = self.engine.owner_identity.issue_grant(
                worker.public, task_id=task, step_id=step, operation="op.1",
                allowed_targets=["i1"], grant_id=grant_id, expires=1894390000,
                required_basis={"test_basis": basis},
                upstream_receipt_sha256=up_sha,
                stop_epoch=_epoch(self.engine))
            req = worker.sign_request(
                grant, operation="op.1", target_id="i1", step_id=step,
                payload={"v": 1},
                upstream_receipt=upstream)
            return self.guard.execute(
                grant=grant, request=req,
                fn=lambda db, p: db.execute("UPDATE items SET val=val+1 WHERE id='i1'"),
                target_table="items", target_pk_col="id",
                upstream_receipt=upstream)

        up = run_op("t-up", "s1", "g-up-1")
        up_sha = up["receipt"]["payload_sha256"]
        down = run_op("t-down", "s1", "g-down-1", upstream=up["receipt"], up_sha=up_sha)
        self.assertEqual(down["status"], "COMMITTED")
        # Evidence changes: the basis version moves; the upstream receipt
        # (and transitively the downstream one) is reopened.
        reopened = self.guard.set_basis("test_basis", "v2")
        self.assertIn("t-up:s1", reopened)
        # The downstream grant now requires the CURRENT basis (v2), so the
        # basis check passes and the reopened upstream receipt is what
        # refuses the execution (surfaced as a signed GuardRefused).
        with self.assertRaisesRegex(GuardRefused, "upstream_receipt_reopened_or_stale"):
            run_op("t-down", "s2", "g-down-2", upstream=up["receipt"], up_sha=up_sha,
                   basis="v2")

    # -- 8. crash and recovery without duplicates --------------------------
    def test_crash_recovery_without_duplicate_external_effects(self):
        real = _Endpoint("real-dest", bytes.fromhex("d1" * 32))
        dest = "https://notify.example/crash"
        self.engine.register_destination(dest, real.public_key)
        oid, _ = self._stage(dest, {"invoice_id": "INV-77"}, "s-crash-1")

        def dispatch_then_lose_ack(envelope):
            resp = real.receive_webhook(envelope)  # destination recorded it
            raise TimeoutError("simulated_ack_loss_after_delivery")

        out = self.guard.flush_external_outbox(dispatch_then_lose_ack)
        self.assertEqual(out, [])
        self.assertEqual(len(real.delivered), 1)
        row = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid)
        self.assertEqual(row["state"], "UNKNOWN_RECONCILIATION_REQUIRED")
        # Crash-in-flight reservation also recovers to UNKNOWN, never re-sent.
        oid2, _ = self._stage(dest, {"invoice_id": "INV-78"}, "s-crash-2")
        with self.assertRaises(RuntimeError):
            self.guard.flush_external_outbox(
                real.receive_webhook, crash_after_in_flight_reservation=True)
        self.guard.recover_in_flight_outbox()
        row2 = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid2)
        self.assertEqual(row2["state"], "UNKNOWN_RECONCILIATION_REQUIRED")
        # Reconcile the first as already-delivered: zero new effects, and a
        # later flush still sends nothing twice.
        entry = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == oid)
        rec = self.guard.reconcile_external_outbox(
            oid, destination_probe=lambda k: {
                "status": "ALREADY_DELIVERED",
                "destination_receipt": sign_envelope(real.identity.key, {
                    "schema": "openline.destination.delivery.v1",
                    "status": "ALREADY_DELIVERED", "idempotency_key": oid,
                    "payload_sha256": entry["payload_sha256"]})})
        self.assertEqual(rec["state"], "RECONCILED_DELIVERED")
        self.assertEqual(rec["new_external_effects"], 0)
        self.assertEqual(self.guard.flush_external_outbox(real.receive_webhook), [])
        self.assertEqual(len(real.delivered), 1)


if __name__ == "__main__":
    unittest.main()
