"""Receiver authority-epoch anti-rollback regressions (GPT-6 falsifier PR #4).

Receiver-issued epochs cannot be reduced by task constraints or ordinary state updates.
These checks are local in-process integrity tests, not evidence of OS-level isolation.
"""
import unittest
from pathlib import Path

import kernel
from run_exp1_compression import build_trajectory_episodes

ROOT = Path(kernel.__file__).resolve().parent


class AuthorityEpochNoRollback(unittest.TestCase):
    def setUp(self):
        kernel.reset_authority_and_recall_state()
        episode = next(ep for ep in build_trajectory_episodes("dev")
                       if "bakery.py" in ep["facts"]["domain_module"]
                       and ep["expected"]["feasible"])
        self.task = {
            "facts": episode["facts"],
            "required_outputs": ["feasible_stabilization", "interventions",
                                 "min_stabilized_throughput", "total_capex_usd",
                                 "cumulative_opex_delta_usd"],
            "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
        }
        issued = kernel.execute(self.task, ROOT / "registry_g1.json")
        self.assertEqual(issued["disposition"], "EXECUTED")
        self.receipt = issued["executed"][0]["receipt"]
        self.assertEqual(self.receipt["authority_epoch"], 1)
        kernel.set_authority_state(authority_epoch=2)

    def tearDown(self):
        kernel.reset_authority_and_recall_state()

    def test_caller_cannot_lower_standing_floor(self):
        standing = kernel.evaluate_receipt_standing(
            self.receipt, constraints={"min_authority_epoch": 1})
        self.assertFalse(standing["valid"], standing)
        self.assertEqual(standing["standing"], "REOPEN")

    def test_prior_receipt_cannot_be_resurrected(self):
        t = dict(self.task, constraints=dict(self.task["constraints"],
            verify_prior_receipt=self.receipt,
            require_prior_receipt_valid=True,
            min_authority_epoch=1))
        result = kernel.execute(t, ROOT / "registry_g1.json")
        self.assertNotEqual(result["disposition"], "EXECUTED", result)

    def test_caller_cannot_mint_receipt_under_stale_epoch(self):
        t = dict(self.task, constraints=dict(self.task["constraints"], authority_epoch=1))
        result = kernel.execute(t, ROOT / "registry_g1.json")
        self.assertNotEqual(result["disposition"], "EXECUTED", result)

    def test_receiver_epoch_is_monotonic(self):
        with self.assertRaises((ValueError, kernel.ContractError)):
            kernel.set_authority_state(authority_epoch=1)
        self.assertEqual(kernel.get_authority_state()["authority_epoch"], 2)

    def test_invalid_minimum_fails_closed(self):
        standing = kernel.evaluate_receipt_standing(
            self.receipt, constraints={"min_authority_epoch": "1"})
        self.assertFalse(standing["valid"], standing)

    def test_future_epoch_receipt_cannot_be_replayed(self):
        forged = dict(self.receipt, authority_epoch=3)
        standing = kernel.evaluate_receipt_standing(forged)
        self.assertFalse(standing["valid"], standing)

    def test_current_receiver_epoch_remains_usable(self):
        t = dict(self.task, constraints=dict(self.task["constraints"], authority_epoch=2))
        issued = kernel.execute(t, ROOT / "registry_g1.json")
        self.assertEqual(issued["disposition"], "EXECUTED", issued)
        self.assertEqual(issued["executed"][0]["receipt"]["authority_epoch"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
