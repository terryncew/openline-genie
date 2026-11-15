"""Unit tests for OpenLine 007 Autonomous Capability Creation, Successor Transfer, and Mode Controller."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import kernel
from capability_creator import build_garden_upgrade_suites


class TestOpenLine007(unittest.TestCase):
    def test_synthesized_capability_registered_and_hash_verified(self):
        reg = json.loads((ROOT / "registry_007.json").read_text())
        ids = [c["id"] for c in reg["capabilities"]]
        self.assertIn("multi-step-upgrade-planner", ids)
        cap = next(c for c in reg["capabilities"] if c["id"] == "multi-step-upgrade-planner")
        actual_sha = sha256((ROOT / cap["relative_source"]).read_bytes()).hexdigest()
        self.assertEqual(actual_sha, cap["source_sha256"])

    def test_garden_co_bottleneck_solved_by_registry_007(self):
        _, holdout_cases = build_garden_upgrade_suites()
        co_case = holdout_cases[6]  # HOLD_07 co-bottleneck tie
        task = {
            "goal": "Unlock co-bottleneck garden yield",
            "facts": co_case["facts"],
            "required_outputs": ["upgrade_sequence", "unlocked_throughput", "total_capex_usd", "feasible_upgrade"],
            "constraints": {"max_relative_cost_units": 5},
        }
        # Baseline 006 registry returns INVESTIGATE
        r0 = kernel.execute(task, ROOT / "registry.json")
        self.assertEqual(r0["disposition"], "INVESTIGATE")
        # 007 registry executes and finds exact multi-step sequence
        r1 = kernel.execute(task, ROOT / "registry_007.json")
        self.assertEqual(r1["disposition"], "EXECUTED")
        res = r1["executed"][0]["result"]
        self.assertTrue(res["feasible_upgrade"])
        self.assertGreaterEqual(res["unlocked_throughput"], co_case["expected"]["min_throughput"])
        self.assertLessEqual(res["total_capex_usd"], co_case["expected"]["max_capex"])

    def test_unfamiliar_bakery_domain_transfer(self):
        task = {
            "goal": "Transfer multi-step planner to unfamiliar Hearth & Crumb Bakery domain",
            "facts": {
                "domain_module": "upstream/bakery.py",
                "assumptions": {"ovens": 1, "bakers": 1, "extra_retarder_racks": 0, "shop_capacity_loaves": 300, "demand_loaves_per_day": 320},
                "target_throughput": 300,
                "max_capex_usd": 22500.0,
                "max_periodic_cost_delta_usd": 70.0,
            },
            "required_outputs": ["upgrade_sequence", "unlocked_throughput", "total_capex_usd", "feasible_upgrade"],
            "constraints": {"max_relative_cost_units": 5},
        }
        r = kernel.execute(task, ROOT / "registry_007.json")
        self.assertEqual(r["disposition"], "EXECUTED")
        res = r["executed"][0]["result"]
        self.assertTrue(res["feasible_upgrade"])
        self.assertEqual(res["unlocked_throughput"], 300)
        self.assertEqual(res["total_capex_usd"], 21700.0)

    def test_changed_interface_refusal(self):
        task = {
            "goal": "Reject missing or altered domain interface",
            "facts": {
                "domain_module": "upstream/nonexistent_domain.py",
                "assumptions": {},
                "target_throughput": 250,
                "max_capex_usd": 1000.0,
                "max_periodic_cost_delta_usd": 50.0,
            },
            "required_outputs": ["upgrade_sequence", "unlocked_throughput", "total_capex_usd", "feasible_upgrade"],
            "constraints": {"max_relative_cost_units": 5},
        }
        r = kernel.execute(task, ROOT / "registry_007.json")
        self.assertEqual(r["disposition"], "INVESTIGATE")
        self.assertEqual(r["reason"], "executor_preconditions_failed")


if __name__ == "__main__":
    unittest.main()
