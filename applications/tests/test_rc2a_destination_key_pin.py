#!/usr/bin/env python3
"""RC2A destination-key pinning, ported to Genie's ReceiverGuard.

This is a faithful port of the six cases in GPT-6's Shared Receiver RC2A
`tests/test_destination_key_pin.py` (recovery-rc2a/.../OPENLINE-SHARED-
RECEIVER-INTEGRATION-001/tests/), adapted to Genie's guard API
(`core/openline_guard.py`: ReceiverGuard, SigningIdentity, sign_envelope).
The five Argon integrated scenarios in that repo (`test_shared_receiver_
001.py`) test the shared receiver's own LivingProjectNode / Astra classes,
which do not exist in Genie, so they cannot run against Genie's guard;
they were run as-is against the RC2A source tree instead (see
RC2A_INTEGRATION_NOTE.md). These six pin cases are the ported regression
suite for Genie's integrated guard.

No model calls. No network.
"""
from __future__ import annotations

import secrets
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.openline_guard import ReceiverGuard, SigningIdentity, sign_envelope


class _Endpoint:
    """Minimal signed destination endpoint (test double)."""

    def __init__(self, name: str, seed: bytes) -> None:
        self.name = name
        self.identity = SigningIdentity(seed=seed)
        self.public_key = self.identity.public
        self.delivered: dict[str, dict] = {}
        self.return_empty_ack_after_processing_once = False

    def _receipt(self, status: str, outbox_id: str, payload_sha256: str) -> dict:
        return sign_envelope(self.identity.key, {
            "schema": "openline.destination.delivery.v1",
            "status": status,
            "idempotency_key": outbox_id,
            "payload_sha256": payload_sha256,
        })

    def receive_webhook(self, envelope: dict) -> dict:
        oid = envelope["outbox_id"]
        psha = envelope["payload_sha256"]
        if oid in self.delivered:
            return {"status": "DELIVERED",
                    "destination_receipt": self._receipt("DELIVERED", oid, psha)}
        self.delivered[oid] = {"payload_sha256": psha}
        if self.return_empty_ack_after_processing_once:
            return {"status": "DELIVERED"}  # processed, but ack carries no receipt
        return {"status": "DELIVERED",
                "destination_receipt": self._receipt("DELIVERED", oid, psha)}

    def query_idempotency(self, outbox_id: str) -> dict:
        rec = self.delivered.get(outbox_id)
        if rec is None:
            return {"status": "CONFIRMED_ABSENT",
                    "destination_receipt": self._receipt("CONFIRMED_ABSENT", outbox_id, "0" * 64)}
        return {"status": "ALREADY_DELIVERED",
                "destination_receipt": self._receipt("ALREADY_DELIVERED", outbox_id, rec["payload_sha256"])}


class DestinationKeyPinTests(unittest.TestCase):
    def make_ready(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "guard.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, val INTEGER)")
        conn.execute("INSERT INTO items VALUES ('i1', 1)")
        conn.commit()
        conn.close()
        receiver = SigningIdentity(seed=secrets.token_bytes(32))
        owner = SigningIdentity(seed=secrets.token_bytes(32))
        worker = SigningIdentity(seed=secrets.token_bytes(32))
        guard = ReceiverGuard(str(db_path), receiver_identity=receiver,
                              strict_production=True, deterministic_ids=True)
        guard.register_issuer(owner.public)
        guard.set_basis("genie_operating_law", "v1.0-20261103")
        dest = "https://unregistered.example/webhook"
        sender = _Endpoint("untrusted-self-signer", secrets.token_bytes(32))
        grant = owner.issue_grant(
            worker.public, task_id="t-unpinned", step_id="s1", operation="op.1",
            allowed_targets=["i1"], grant_id="g-unpinned", expires=1894390000)
        req = worker.sign_request(grant, operation="op.1", target_id="i1",
                                  step_id="s1", payload={"v": 1})

        def effect(db, payload):
            db.execute("UPDATE items SET val=990 WHERE id='i1'")
            guard.stage_external_effect(db, task_id="t-unpinned", step_id="s1",
                                        channel="webhook", destination=dest,
                                        payload={"v": 1})

        guard.execute(grant=grant, request=req, fn=effect,
                      target_table="items", target_pk_col="id")
        return guard, sender, dest

    def test_self_signed_unpinned_receipt_cannot_confirm_delivery(self):
        guard, sender, dest = self.make_ready()
        self.assertIsNone(guard.get_destination_public_key(dest))
        self.assertEqual(guard.flush_external_outbox(sender.receive_webhook), [])
        self.assertEqual(
            guard.list_external_outbox(task_id="t-unpinned")[0]["state"],
            "UNKNOWN_RECONCILIATION_REQUIRED")

    def test_registered_destination_key_accepts_its_receipt(self):
        guard, sender, dest = self.make_ready()
        guard.register_destination(dest, sender.public_key)
        self.assertEqual(len(guard.flush_external_outbox(sender.receive_webhook)), 1)
        self.assertEqual(
            guard.list_external_outbox(task_id="t-unpinned")[0]["state"], "DISPATCHED")

    def test_cannot_opt_out_of_signed_ack_requirement(self):
        guard, sender, dest = self.make_ready()
        with self.assertRaisesRegex(ValueError, "unsigned_ack_mode_unsupported"):
            guard.flush_external_outbox(sender.receive_webhook, require_signed_ack=False)
        self.assertEqual(
            guard.list_external_outbox(task_id="t-unpinned")[0]["state"],
            "READY_TO_DISPATCH")

    def test_caller_supplied_key_cannot_replace_missing_pin(self):
        guard, sender, dest = self.make_ready()
        self.assertEqual(
            guard.flush_external_outbox(sender.receive_webhook,
                                        trusted_destination_pub=sender.public_key), [])
        self.assertEqual(
            guard.list_external_outbox(task_id="t-unpinned")[0]["state"],
            "UNKNOWN_RECONCILIATION_REQUIRED")

    def test_caller_supplied_key_must_match_receiver_pin(self):
        guard, sender, dest = self.make_ready()
        other = _Endpoint("real-pinned", secrets.token_bytes(32))
        guard.register_destination(dest, other.public_key)
        self.assertEqual(
            guard.flush_external_outbox(sender.receive_webhook,
                                        trusted_destination_pub=sender.public_key), [])
        self.assertEqual(
            guard.list_external_outbox(task_id="t-unpinned")[0]["state"],
            "UNKNOWN_RECONCILIATION_REQUIRED")

    def test_reconciliation_does_not_accept_caller_supplied_unpinned_key(self):
        guard, sender, dest = self.make_ready()
        sender.return_empty_ack_after_processing_once = True
        guard.flush_external_outbox(sender.receive_webhook)
        oid = guard.list_external_outbox(task_id="t-unpinned")[0]["outbox_id"]
        with self.assertRaisesRegex(ValueError, "destination_public_key_pin_mismatch"):
            guard.reconcile_external_outbox(
                oid, destination_probe=sender.query_idempotency,
                trusted_destination_pub=sender.public_key)
        self.assertEqual(
            guard.list_external_outbox(task_id="t-unpinned")[0]["state"],
            "UNKNOWN_RECONCILIATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
