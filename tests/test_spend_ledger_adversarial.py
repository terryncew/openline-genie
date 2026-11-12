"""B2 extended negative tests: zero external model calls, scratch state only."""
import json
import tempfile
import unittest
from core.model_adapter import SpendLedger, ModelError, SpendCapExceeded


class SpendLedgerExtendedAdversarial(unittest.TestCase):
    def test_malformed_reservations_and_calls_fail_closed(self):
        base = {"total_usd": 5.0, "cap_usd": 5.0, "calls": [], "reservations": []}
        cases = {
            "negative_open_reservation": {"reservations": [{"status": "open", "reserved_usd": -10}]},
            "nan_open_reservation": {"reservations": [{"status": "open", "reserved_usd": float("nan")}]},
            "unknown_reservation_status": {"reservations": [{"status": "unknown", "reserved_usd": 10}]},
            "negative_call_cost": {"calls": [{"cost_usd": -4}]},
            "nonfinite_call_cost": {"calls": [{"cost_usd": float("inf")}]},
            "fake_cap": {"cap_usd": 999.0},
            "string_total": {"total_usd": "5.0"},
            "no_total": {"total_usd": None},
        }
        for name, update in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                ledger = SpendLedger(d)
                bad = {**base, **update}
                ledger.json_path.write_text(json.dumps(bad))
                before = ledger.json_path.read_bytes()
                with self.assertRaises(ModelError):
                    ledger.reserve("claude-haiku-5-5", 100, 100, "probe", 5.0)
                self.assertEqual(before, ledger.json_path.read_bytes())

    def test_valid_exhausted_ledger_still_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = SpendLedger(d)
            ledger.json_path.write_text(json.dumps({"total_usd": 5., "cap_usd":5.,
                "calls": [{"cost_usd":5.}], "reservations": []}))
            with self.assertRaises(SpendCapExceeded):
                ledger.reserve("claude-haiku-5-5", 100, 100, "probe", 5.0)

if __name__ == "__main__": unittest.main()
