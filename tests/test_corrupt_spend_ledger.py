"""Independent regression: fail-closed if a persisted spend ledger is malformed.
Run against frozen original (must FAIL) and hotfix candidate (must PASS).
No model calls; uses fresh scratch ledgers only.
"""
import json, tempfile, sys, unittest
from pathlib import Path
from unittest import mock
from core.model_adapter import AnthropicAdapter, ModelError, SpendLedger

class SpendCorruptionProbe(unittest.TestCase):
    def test_existing_corrupt_ledger_does_not_authorize_new_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = SpendLedger(d)
            ledger.json_path.write_text('{"total_usd":5.0, BROKEN')
            before = ledger.json_path.read_bytes()
            with self.assertRaises(ModelError):
                ledger.reserve('claude-haiku-5-5', 100, 100, 'independent_probe', 5.0)
            self.assertEqual(ledger.json_path.read_bytes(), before)

    def test_existing_corrupt_ledger_does_not_dispatch_helper(self):
        with tempfile.TemporaryDirectory() as d:
            helper = Path(d)/'helper.py'
            helper.write_text('# placeholder helper; subprocess.run is mocked')
            adapter=AnthropicAdapter(ledger_dir=d,helper_path=helper,total_cap_usd=5.0,sub_budget_usd=5.0)
            adapter.ledger.json_path.write_text('{"total_usd":5.0, BROKEN')
            with mock.patch('subprocess.run') as call:
                with self.assertRaises(ModelError):
                    adapter.complete('sys','user',max_tokens=100)
                call.assert_not_called()
            self.assertEqual(adapter.ledger.json_path.read_text(), '{"total_usd":5.0, BROKEN')

if __name__=='__main__':unittest.main()
