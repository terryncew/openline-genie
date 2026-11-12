#!/usr/bin/env python3
"""RC6 repair: empty-text adapter responses are diagnosable and accounted.

Regression test for the second-domain caveat: when a model response has
zero text blocks, AnthropicAdapter.complete used to raise BEFORE logging
usage, so the failure carried no structure and its tokens went
unrecorded. Now the response structure (block types, stop_reason,
input/output usage) is captured first, usage is recorded in the ledger
whenever it is present, and only then is the error raised.

Mocked helper responses only — zero model spend.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model_adapter import AnthropicAdapter, ModelError, SpendLedger  # noqa: E402


def _fake_run_factory(payload):
    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [], returncode=0,
            stdout=json.dumps(payload), stderr="",
        )
    return _fake_run


class TestEmptyTextDiagnosability(unittest.TestCase):
    def _adapter(self, tmp):
        helper = Path(tmp) / "anthropic-messages"
        helper.write_text("#!/bin/sh\n", encoding="utf-8")
        return AnthropicAdapter(
            ledger_dir=tmp, helper_path=helper,
            sub_budget_usd=100.0, total_cap_usd=100.0,
        )

    def test_zero_text_blocks_records_usage_and_names_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_empty_001",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [],
                "usage": {"input_tokens": 1200, "output_tokens": 37},
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            msg = str(cm.exception)
            self.assertIn("anthropic_empty_text_response", msg)
            self.assertIn("end_turn", msg)
            self.assertIn("[]", msg)  # block types: none
            self.assertIn("1200/37", msg)
            ledger = SpendLedger(tmp)
            self.assertEqual(len(ledger.calls()), 1)
            call = ledger.calls()[0]
            self.assertEqual(call["input_tokens"], 1200)
            self.assertEqual(call["output_tokens"], 37)
            self.assertEqual(call["purpose"], "genie_worker_empty_text")
            self.assertEqual(call["message_id"], "msg_empty_001")
            # Haiku rates: 1200 * $0.10e-6 + 37 * $0.50e-6.
            self.assertAlmostEqual(
                ledger.total_usd(), 1200 * 0.10e-6 + 37 * 0.50e-6, places=9)

    def test_non_text_blocks_recorded_with_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_tool_002",
                "type": "message",
                "stop_reason": "tool_use",
                "content": [{"type": "tool_use", "id": "toolu_1", "name": "x"}],
                "usage": {"input_tokens": 50, "output_tokens": 200},
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            msg = str(cm.exception)
            self.assertIn("tool_use", msg)
            self.assertIn("50/200", msg)
            ledger = SpendLedger(tmp)
            self.assertEqual(len(ledger.calls()), 1)
            self.assertEqual(ledger.calls()[0]["input_tokens"], 50)
            self.assertEqual(ledger.calls()[0]["output_tokens"], 200)

    def test_text_response_still_returns_and_records_normally(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_ok_003",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hello bakery"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                out = adapter.complete("sys", "user")
            self.assertEqual(out["text"], "hello bakery")
            ledger = SpendLedger(tmp)
            self.assertEqual(len(ledger.calls()), 1)
            self.assertEqual(ledger.calls()[0]["purpose"], "genie_worker")

    def test_empty_text_without_usage_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_nousage_004",
                "type": "message",
                "stop_reason": "max_tokens",
                "content": [],
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            self.assertIn("max_tokens", str(cm.exception))
            # R5-B2: the reservation stands as the recorded spend (worst
            # case: est_in=2, max_tokens=8000), never $0 for a dispatched call.
            worst = 2 * 0.10e-6 + 8000 * 0.50e-6
            ledger = SpendLedger(tmp)
            self.assertEqual(len(ledger.calls()), 1)
            self.assertTrue(ledger.calls()[0].get("reservation_held"))
            self.assertAlmostEqual(ledger.total_usd(), worst, places=9)
            self.assertEqual(
                [r["status"] for r in ledger.reservations()], ["held"])


if __name__ == "__main__":
    unittest.main()
