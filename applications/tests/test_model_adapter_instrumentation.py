#!/usr/bin/env python3
"""RC6 owner-review instrumentation: every adapter call is logged as
structured response-shape data (block types, stop_reason, usage, request
parameters, response shape) -- never keys, credentials, or model output
text -- and usage is recorded in the spend ledger whenever present,
including on the empty-text path. A response with no usage block at all
is logged explicitly as usage_missing; under reservation enforcement
(R5-B2) its worst-case reservation stands as the recorded spend, so the
ledger total is an upper bound on true spend for that call, never $0.

Mocked helper responses only -- zero model spend.
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

LOG_REL = Path("evidence") / "instrumentation" / "adapter_call_log.jsonl"


def _fake_run_factory(payload):
    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [], returncode=0,
            stdout=json.dumps(payload), stderr="",
        )
    return _fake_run


class TestAdapterCallInstrumentation(unittest.TestCase):
    def _adapter(self, tmp):
        helper = Path(tmp) / "anthropic-messages"
        helper.write_text("#!/bin/sh\n", encoding="utf-8")
        return AnthropicAdapter(
            ledger_dir=tmp, helper_path=helper,
            sub_budget_usd=100.0, total_cap_usd=100.0,
        )

    def _log_lines(self, tmp):
        path = Path(tmp) / LOG_REL
        self.assertTrue(path.exists(), f"call log missing: {path}")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def test_normal_text_response_logs_full_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_instr_ok_001",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "SECRET-MARKER-DO-NOT-LOG hello bakery"}],
                "usage": {"input_tokens": 120, "output_tokens": 45},
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                out = adapter.complete("sys", "user-prompt", max_tokens=2000, purpose="understand")
            self.assertEqual(out["text"], "SECRET-MARKER-DO-NOT-LOG hello bakery")
            lines = self._log_lines(tmp)
            self.assertEqual(len(lines), 1)
            rec = lines[0]
            self.assertEqual(rec["outcome"], "ok")
            self.assertEqual(rec["purpose"], "understand")
            self.assertEqual(rec["message_id"], "msg_instr_ok_001")
            # Request parameters.
            self.assertEqual(rec["request"]["model"], "claude-haiku-5-5")
            self.assertEqual(rec["request"]["max_tokens"], 2000)
            self.assertIsNone(rec["request"]["thinking_config"])  # never sent
            self.assertEqual(rec["request"]["estimated_input_tokens"], 4)  # ceil(15/4)
            # Response shape.
            self.assertEqual(rec["response"]["stop_reason"], "end_turn")
            self.assertEqual(rec["response"]["block_types"], ["text"])
            self.assertEqual(rec["response"]["content_block_count"], 1)
            self.assertTrue(rec["response"]["has_text_block"])
            self.assertEqual(rec["response"]["text_chars"], len("SECRET-MARKER-DO-NOT-LOG hello bakery"))
            self.assertEqual(rec["response"]["raw_response_length"], len(json.dumps(payload)))
            # Usage.
            self.assertTrue(rec["usage_present"])
            self.assertFalse(rec["usage_missing"])
            self.assertEqual(rec["usage"], {"input_tokens": 120, "output_tokens": 45})
            # Ledger recorded.
            self.assertTrue(rec["ledger_recorded"])
            self.assertAlmostEqual(rec["cost_usd"], 120 * 0.10e-6 + 45 * 0.50e-6, places=9)
            self.assertEqual(len(SpendLedger(tmp).calls()), 1)
            # NEVER the model output text, in any field.
            self.assertNotIn("SECRET-MARKER-DO-NOT-LOG", json.dumps(rec))

    def test_empty_text_response_logs_structure_and_records_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_instr_empty_002",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [],
                "usage": {"input_tokens": 1486, "output_tokens": 8000},
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user-prompt", max_tokens=8000, purpose="build")
            self.assertIn("anthropic_empty_text_response", str(cm.exception))
            lines = self._log_lines(tmp)
            self.assertEqual(len(lines), 1)
            rec = lines[0]
            self.assertEqual(rec["outcome"], "empty_text")
            self.assertEqual(rec["purpose"], "build")
            self.assertEqual(rec["message_id"], "msg_instr_empty_002")
            self.assertEqual(rec["response"]["stop_reason"], "end_turn")
            self.assertEqual(rec["response"]["block_types"], [])
            self.assertEqual(rec["response"]["content_block_count"], 0)
            self.assertFalse(rec["response"]["has_text_block"])
            self.assertEqual(rec["response"]["text_chars"], 0)
            self.assertEqual(rec["request"]["max_tokens"], 8000)
            self.assertIsNone(rec["request"]["thinking_config"])
            self.assertTrue(rec["usage_present"])
            self.assertEqual(rec["usage"], {"input_tokens": 1486, "output_tokens": 8000})
            # Usage IS recorded on the empty-text path.
            self.assertTrue(rec["ledger_recorded"])
            self.assertAlmostEqual(rec["cost_usd"], 1486 * 0.10e-6 + 8000 * 0.50e-6, places=9)
            calls = SpendLedger(tmp).calls()
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["purpose"], "genie_worker_empty_text")
            self.assertEqual(calls[0]["message_id"], "msg_instr_empty_002")

    def test_empty_text_with_non_text_blocks_logs_block_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_instr_tool_003",
                "type": "message",
                "stop_reason": "tool_use",
                "content": [
                    {"type": "thinking", "thinking": "must not appear in log"},
                    {"type": "tool_use", "id": "toolu_1", "name": "x"},
                ],
                "usage": {"input_tokens": 60, "output_tokens": 90},
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError):
                    adapter.complete("sys", "user", max_tokens=8000, purpose="build")
            rec = self._log_lines(tmp)[0]
            self.assertEqual(rec["outcome"], "empty_text")
            self.assertEqual(rec["response"]["block_types"], ["thinking", "tool_use"])
            self.assertEqual(rec["response"]["content_block_count"], 2)
            self.assertFalse(rec["response"]["has_text_block"])
            self.assertEqual(rec["response"]["stop_reason"], "tool_use")
            self.assertTrue(rec["ledger_recorded"])
            # Block CONTENTS (e.g. thinking text) are never logged.
            self.assertNotIn("must not appear in log", json.dumps(rec))

    def test_response_without_usage_block_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_instr_nousage_004",
                "type": "message",
                "stop_reason": "max_tokens",
                "content": [],
                # No "usage" key at all.
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user", max_tokens=8000, purpose="build")
            self.assertIn("anthropic_empty_text_response", str(cm.exception))
            rec = self._log_lines(tmp)[0]
            self.assertEqual(rec["outcome"], "empty_text")
            self.assertFalse(rec["usage_present"])
            self.assertTrue(rec["usage_missing"])
            self.assertIsNone(rec["usage"])
            self.assertEqual(rec["response"]["stop_reason"], "max_tokens")
            # R5-B2: the worst-case reservation stands as the recorded
            # spend (est_in=2 for "sys"+"user", max_tokens=8000), never
            # $0 for a dispatched call.
            worst = 2 * 0.10e-6 + 8000 * 0.50e-6
            self.assertTrue(rec["ledger_recorded"])
            self.assertIn("reservation held", rec["ledger_note"])
            self.assertAlmostEqual(rec["cost_usd"], worst, places=9)
            self.assertEqual(rec["reservation_status"], "held")
            ledger = SpendLedger(tmp)
            self.assertEqual(len(ledger.calls()), 1)
            self.assertTrue(ledger.calls()[0].get("reservation_held"))
            self.assertAlmostEqual(ledger.total_usd(), worst, places=9)
            self.assertEqual(
                [r["status"] for r in ledger.reservations()], ["held"])

    def test_text_response_without_usage_block_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_instr_nousage_005",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "some html"}],
                # No "usage" key at all.
            }
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError):
                    adapter.complete("sys", "user", max_tokens=8000, purpose="build")
            rec = self._log_lines(tmp)[0]
            self.assertEqual(rec["outcome"], "usage_missing")
            self.assertFalse(rec["usage_present"])
            self.assertTrue(rec["usage_missing"])
            self.assertTrue(rec["ledger_recorded"])
            self.assertIn("reservation held", rec["ledger_note"])
            self.assertAlmostEqual(
                rec["cost_usd"], 2 * 0.10e-6 + 8000 * 0.50e-6, places=9)
            self.assertEqual(rec["reservation_status"], "held")
            ledger = SpendLedger(tmp)
            self.assertEqual(len(ledger.calls()), 1)
            self.assertTrue(ledger.calls()[0].get("reservation_held"))

    def test_spend_cap_refusal_is_logged_without_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = Path(tmp) / "anthropic-messages"
            helper.write_text("#!/bin/sh\n", encoding="utf-8")
            adapter = AnthropicAdapter(
                ledger_dir=tmp, helper_path=helper,
                sub_budget_usd=0.000001, total_cap_usd=100.0,
            )
            with mock.patch("subprocess.run") as fake_run:
                with self.assertRaises(Exception):
                    adapter.complete("sys", "user", max_tokens=8000, purpose="build")
                fake_run.assert_not_called()
            rec = self._log_lines(tmp)[0]
            self.assertEqual(rec["outcome"], "spend_cap_refused")
            self.assertFalse(rec["ledger_recorded"])
            self.assertEqual(SpendLedger(tmp).calls(), [])


if __name__ == "__main__":
    unittest.main()
