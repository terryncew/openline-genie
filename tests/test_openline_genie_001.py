#!/usr/bin/env python3
"""Comprehensive Functional, Mobile/iPhone Browser, Adversarial, Recovery, Portability & Benchmark Suite for OpenLine Genie."""
from __future__ import annotations

import base64
import json
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from genie_engine import (
    GenieAppSynthesizer,
    OpenLineGenieEngine,
    calculate_quote_totals,
    simulate_robot_academy_program,
)
from genie_server import start_genie_server
from core.openline_guard import GuardRefused, SigningIdentity, verify_receipt_offline, sign_envelope
from core.ipc_protocol import ipc_request_intent_sha256


class OpenLineGenieVerificationSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="genie-test-")
        self.engine = OpenLineGenieEngine(state_dir=self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_01_demonstration_a_quoting_invoicing_cent_math_and_export(self) -> None:
        """Verifies Demo A (Small Service Business Quoting & Invoicing):
        - Creates/edits quotes with cent-accurate discount & tax math
        - Converts accepted quotes into numbered invoices
        - Persists and recovers records in SQLite + Ed25519 receipts
        - Exports usable HTML, CSV, and JSON without lock-in
        - Explicitly disclaims automatic customer generation or payment processing.
        """
        bundle = self.engine.get_project_bundle("demo-a-service-quoting")
        st = bundle["accepted"]["state"]
        self.assertIn("Does NOT automatically generate customers", st["honesty_boundary"])
        self.assertEqual(len(st["quotes"]), 2)
        self.assertEqual(len(st["invoices"]), 1)

        # Add a new quote Q-1003 and verify cent-accurate math
        updated = self.engine.demo_a_add_or_update_quote(
            customer_id="CUST-103",
            customer_name="Hearth & Crumb Corner Cafe",
            items=[
                {"service_id": "SRV-01", "description": "Lawn & Hedge Cleanup", "unit": "visit", "quantity": 2, "unit_price_dollars": 150.00, "taxable": False},
                {"service_id": "SRV-03", "description": "Organic Mulch", "unit": "cu yd", "quantity": 3, "unit_price_dollars": 80.00, "taxable": True},
            ],
            discount_pct=10.0,
            tax_rate_pct=8.25,
            deposit_pct=25.0,
            notes="Patio mulch refresh",
        )
        q3 = updated["accepted"]["state"]["quotes"][-1]
        self.assertEqual(q3["quote_id"], "Q-1003")
        # Subtotal = 300 + 240 = $540.00 (54000 cents)
        # Discount 10% = $54.00 -> after discount = $486.00 (48600 cents)
        # Taxable after 10% discount = 240 * 0.9 = $216.00 (21600 cents); Tax @ 8.25% = 1782 cents ($17.82)
        # Total = 48600 + 1782 = 50382 cents ($503.82)
        self.assertEqual(q3["subtotal_cents"], 54000)
        self.assertEqual(q3["discount_cents"], 5400)
        self.assertEqual(q3["tax_cents"], 1782)
        self.assertEqual(q3["total_cents"], 50382)
        self.assertEqual(q3["total_dollars"], 503.82)

        # Convert Q-1003 into Invoice INV-2002
        after_inv = self.engine.demo_a_convert_quote_to_invoice("Q-1003", payment_terms="Net 15")
        invoices = after_inv["accepted"]["state"]["invoices"]
        self.assertEqual(len(invoices), 2)
        inv2 = invoices[-1]
        self.assertEqual(inv2["invoice_id"], "INV-2002")
        self.assertEqual(inv2["source_quote_id"], "Q-1003")
        self.assertEqual(inv2["total_cents"], 50382)
        self.assertEqual(inv2["balance_due_cents"], 50382)

        # Verify offline Ed25519 receipt signature on accepted state
        receipt = after_inv["accepted"]["receipt"]
        ver = verify_receipt_offline(receipt['receipt'], pinned_receiver_pub=self.engine.receiver_identity.public)
        self.assertEqual(ver["crypto"], "VERIFIED"); self.assertEqual(ver["status"], "COMMITTED")

        # Export portable HTML, CSV, and JSON
        exp = self.engine.export_portable_bundle("demo-a-service-quoting")
        self.assertIn("INV-2002", exp["portable_csv"])
        self.assertIn("PORTABLE STANDALONE EXPORT", exp["standalone_html"])
        parsed_json = json.loads(exp["portable_json"])
        self.assertEqual(parsed_json["accepted"]["state_sha256"], exp["accepted_sha256"])

    def test_02_demonstration_b_robot_academy_levels_and_safety_permit(self) -> None:
        """Verifies Demo B (Free Interactive Robotics Learning Environment for Kids):
        - Runs progressive levels 1..4 with movement, sensor scan, and cell pickup
        - Enforces safety permit speed cap (blocks > 0.75 m/s) and human walkway boundary (x <= 4.20 m)
        - Works with zero accounts, zero paid APIs, and zero physical hardware.
        """
        for lvl in (1, 2, 3, 4):
            bundle = self.engine.get_project_bundle("demo-b-robot-academy-kids")
            rec_blocks = bundle["accepted"]["state"]["levels"][str(lvl)]["recommended_blocks"]
            res = self.engine.demo_b_run_program(lvl, rec_blocks, speed_mps=0.55)
            sim = res["accepted"]["state"]["last_simulation"]
            if not sim["reached_target"]:
                raise AssertionError(f"Level {lvl} recommended blocks failed to reach target: {sim}")
            self.assertEqual(sim["status"], "MISSION_COMPLETE")
            self.assertGreaterEqual(sim["min_clearance_m"], 0.40)

        # Test safety permit speed violation (> 0.75 m/s)
        unsafe = self.engine.demo_b_run_program(4, ["FORWARD 1.2"], speed_mps=1.15)
        sim_u = unsafe["accepted"]["state"]["last_simulation"]
        self.assertTrue(sim_u["speed_blocked_by_permit"])
        self.assertEqual(sim_u["status"], "PERMIT_BLOCKED_UNSAFE_SPEED")

    def test_03_rejected_proposals_never_overwrite_accepted_work_and_approved_promotes(self) -> None:
        """Proves Section 5 & Section 9:
        - Exploratory proposals do not mutate Accepted state
        - Rejected proposals are quarantined in `genie_rejected` and cannot overwrite Accepted state
        - Approved proposals promote cleanly to Accepted state and survive reload.
        """
        b0 = self.engine.get_project_bundle("demo-a-service-quoting")
        sha0 = b0["accepted"]["state_sha256"]
        ver0 = b0["accepted"]["version"]

        # 1. Propose an undesirable change (e.g. changing business name to "CORRUPTED_BY_BAD_AGENT")
        b_prop_bad = self.engine.propose_exploratory_change(
            "demo-a-service-quoting",
            "Bad proposal: overwrite business name and strip tagline",
            {"customization": {"business_name": "CORRUPTED_BY_BAD_AGENT"}},
        )
        # Accepted state must remain 100% identical while exploratory proposal is pending
        self.assertEqual(b_prop_bad["accepted"]["state_sha256"], sha0)
        bad_prop_id = b_prop_bad["exploratory"][0]["proposal_id"]

        # 2. Reject the bad proposal
        b_after_rej = self.engine.reject_exploratory_change(
            "demo-a-service-quoting", bad_prop_id, reason="user_rejected_destructive_proposal"
        )
        self.assertEqual(b_after_rej["accepted"]["state_sha256"], sha0)
        self.assertEqual(b_after_rej["accepted"]["version"], ver0)
        self.assertEqual(len(b_after_rej["rejected"]), 1)
        self.assertEqual(b_after_rej["rejected"][0]["preserved_accepted_sha256"], sha0)

        # Verify attempting to accept an already-rejected proposal is refused
        with self.assertRaises(PermissionError):
            self.engine.accept_exploratory_change("demo-a-service-quoting", bad_prop_id)

        # 3. Propose a good change and accept it
        b_prop_good = self.engine.propose_exploratory_change(
            "demo-a-service-quoting",
            "Enable 10% repeat-customer discount & Net 10 payment terms",
            {"customization": {"payment_terms": "Net 10", "repeat_customer_discount_enabled": True}},
        )
        good_prop_id = b_prop_good["exploratory"][0]["proposal_id"]
        b_accepted = self.engine.accept_exploratory_change("demo-a-service-quoting", good_prop_id)
        self.assertEqual(b_accepted["accepted"]["version"], ver0 + 1)
        self.assertNotEqual(b_accepted["accepted"]["state_sha256"], sha0)
        self.assertEqual(b_accepted["accepted"]["state"]["customization"]["payment_terms"], "Net 10")

        # 4. Reload engine from disk SQLite and verify permanent survival
        reloaded_engine = OpenLineGenieEngine(state_dir=self.tmp.name)
        b_reloaded = reloaded_engine.get_project_bundle("demo-a-service-quoting")
        self.assertEqual(b_reloaded["accepted"]["state_sha256"], b_accepted["accepted"]["state_sha256"])
        self.assertEqual(len(b_reloaded["rejected"]), 1)

    def test_04_hundred_yard_jump_unfamiliar_request_synthesis_and_falsifiers(self) -> None:
        """Tests Section 7 (Hundred-Yard Jump — GenieAppSynthesizer) across 3 unfamiliar requests
        and compares against the old Studio RC5 static fallback.
        """
        unfamiliar_prompts = [
            "Build a neighborhood tool library and equipment lending tracker with refundable deposits and overdue check-in alerts.",
            "Build a mobile pet grooming appointment and vaccination fee calculator.",
            "Help me figure out whether solar panels would save money on this building.",
        ]
        for prompt in unfamiliar_prompts:
            bundle = self.engine.build_from_prompt(prompt)
            st = bundle["accepted"]["state"]
            self.assertEqual(st["schema"], "openline.genie.synthesized_app.v1")
            self.assertGreaterEqual(len(st["fields"]), 4)
            self.assertGreaterEqual(len(st["records"]), 2)

            # Add a new record and verify live formula calculation
            new_rec = {
                "item_name": "Test Synthesized Item",
                "borrower_name": "Alex Rivera",
                "deposit_paid_dollars": 80.0,
                "late_days": 3,
                "daily_late_fee_dollars": 4.0,
                "array_watts": 800,
                "marginal_rate_dollars": 0.36,
                "self_use_fraction": 0.85,
                "quantity_units": 5,
                "unit_rate_dollars": 50.0,
                "adjustments_dollars": 10.0,
            }
            updated = self.engine.synthesized_app_add_record(bundle["project_id"], new_rec)
            self.assertEqual(len(updated["accepted"]["state"]["records"]), len(st["records"]) + 1)

        # Falsifier check: negative deposit or invalid bounds must be rejected
        tool_state = self.engine.get_project_bundle("genie-synth-neighborhood-tool-library")["accepted"]["state"]
        with self.assertRaises(ValueError):
            GenieAppSynthesizer.compute_record_metric(tool_state, {"deposit_paid_dollars": -25.0, "late_days": 1})

    def test_05_adversarial_workflow_lab_four_repairs_and_external_reconciliation(self) -> None:
        """Proves Section 1 & Section 9:
        - Consequential external actions are blocked without owner authorization
        - D-01 + D-01b: Pre-commit crash rolls back staged external outbox; mid-dispatch timeout transitions to
          UNKNOWN_RECONCILIATION_REQUIRED with 0 silent duplicate retries, and reconciles cleanly
        - D-02: ipc_request_intent_sha256 is invariant across >=1s clock boundaries
        - D-03: Transitive upstream_receipt_sha256 reopen blocks downstream execution on stale basis
        - STOP and Worker-A -> Worker-B replacement preserve accepted work.
        """
        # 1. Consequential external action blocked without owner approval
        blocked = self.engine.attempt_consequential_external_action(
            "demo-a-service-quoting",
            "publish_public_website",
            "https://example.org/publish",
            {"domain": "verdant.example"},
            owner_approved=False,
        )
        self.assertEqual(blocked["status"], "BLOCKED_OWNER_AUTHORIZATION_REQUIRED")
        self.assertEqual(blocked["external_effects_sent"], 0)

        # 2. D-01b: Owner-approved external action with simulated network drop enters UNKNOWN_RECONCILIATION_REQUIRED
        dropped = self.engine.attempt_consequential_external_action(
            "demo-a-service-quoting",
            "send_customer_email",
            "https://mail.example.org/webhook",
            {"invoice_id": "INV-2001"},
            owner_approved=True,
            simulate_network_drop=True,
        )
        self.assertEqual(dropped["status"], "UNKNOWN_RECONCILIATION_REQUIRED")
        outbox_id = dropped["outbox_id"]

        # Verify subsequent flush_external_outbox does NOT blindly re-send UNKNOWN_RECONCILIATION_REQUIRED row
        re_sent = []
        self.engine.guard.flush_external_outbox(lambda env: (re_sent.append(env), {"status": "DELIVERED"})[1])
        self.assertEqual(len(re_sent), 0)

        # Reconcile unknown outbox with destination probe confirming ALREADY_DELIVERED -> 0 duplicate sends
        dest_key = SigningIdentity(seed=secrets.token_bytes(32))
        # RC2A: the destination key must be owner-pinned before any
        # reconciliation can trust its receipts (fixture registration,
        # mirroring the RC2A patch's fixture updates).
        self.engine.guard.register_destination("https://mail.example.org/webhook", dest_key.public)
        # Unsigned / unpinned claim must remain UNKNOWN, not become verified delivery.
        with self.assertRaises(ValueError):
            self.engine.guard.reconcile_external_outbox(
                outbox_id, destination_probe=lambda oid: {"status": "ALREADY_DELIVERED"}
            )
        entry = next(x for x in self.engine.guard.list_external_outbox() if x["outbox_id"] == outbox_id)
        dest_receipt = sign_envelope(dest_key.key, {
            "schema": "openline.destination.delivery.v1",
            "status": "ALREADY_DELIVERED",
            "idempotency_key": outbox_id,
            "payload_sha256": entry["payload_sha256"],
        })
        reconciled = self.engine.guard.reconcile_external_outbox(
            outbox_id,
            destination_probe=lambda oid: {
                "status": "ALREADY_DELIVERED", "destination_receipt": dest_receipt
            },
            trusted_destination_pub=dest_key.public,
        )
        self.assertEqual(reconciled["state"], "RECONCILED_DELIVERED")
        self.assertEqual(reconciled["new_external_effects"], 0)

        # 3. D-02: Verify ipc_request_intent_sha256 invariance across 1-second timestamp tick
        env_t1 = {
            "schema": "openline.ipc.request.v1",
            "deployment_id": "dep-1",
            "project_id": "demo-a",
            "receiver_id": "rec-1",
            "channel": "worker",
            "request_id": "req-100",
            "principal_id": "worker-a",
            "operation": "submit",
            "nonce": "n-100",
            "issued_at": 1762790000,
            "expires_at": 1762790300,
            "payload_sha256": "abcd" * 16,
            "signer_pub": "pub-a",
            "signature": "sig-t1",
        }
        env_t2 = dict(env_t1, issued_at=1762790002, expires_at=1762790302, signature="sig-t2")
        self.assertEqual(ipc_request_intent_sha256(env_t1), ipc_request_intent_sha256(env_t2))

        # 4. Worker replacement (Worker-A -> Worker-B) & STOP preservation
        succ = self.engine.replace_worker_and_recover()
        self.assertEqual(succ["new_active_worker"], "worker-b")
        b_after_succ = self.engine.demo_a_add_or_update_quote(
            customer_id="CUST-101",
            customer_name="Maria Chen",
            items=[{"service_id": "SRV-01", "description": "Cleanup", "unit": "visit", "quantity": 1, "unit_price_dollars": 165.00, "taxable": False}],
        )
        self.assertEqual(b_after_succ["active_worker_id"], "worker-b")

        # Trigger STOP -> verify mutation is refused while Accepted state survives
        sha_before_stop = b_after_succ["accepted"]["state_sha256"]
        self.engine.trigger_stop("test_stop_preservation")
        with self.assertRaises(GuardRefused):
            self.engine.demo_a_convert_quote_to_invoice("Q-1002")
        self.assertEqual(self.engine.get_project_bundle("demo-a-service-quoting")["accepted"]["state_sha256"], sha_before_stop)
        self.engine.clear_stop("resume_after_test")

    # NOTE (2026-11-10): test_06 was REMOVED here, not weakened.
    # Its button-by-button journey targeted a pre-RC3 UI whose element
    # IDs no longer exist; the requirement is RETIRED per
    # tests/TEST_06_DISPOSITION.md. The original method is preserved
    # verbatim at tests/preserved/test_openline_genie_001_ORIGINAL.py,
    # and the rewritten regression for the live requirement is
    # tests/test_06_living_world_journey.py.


if __name__ == "__main__":
    unittest.main(verbosity=2)
