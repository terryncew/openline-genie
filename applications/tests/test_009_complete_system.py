#!/usr/bin/env python3
"""OpenLine 009 — Complete End-to-End Integration, Two-Project Dogfood & Falsification Test Suite."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_009_dogfood_and_falsifiers import run_complete_009_dogfood_and_falsifiers


class TestOpenLine009CompleteSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_dir = Path(cls._tmp.name)
        cls.report = run_complete_009_dogfood_and_falsifiers(cls.out_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_01_living_project_1_end_to_end_and_worker_sigkill_recovery(self) -> None:
        p1 = self.report["project_1_mutual_aid"]
        self.assertEqual(p1["idea_layer_brief_id"], "IL-7-2")
        self.assertEqual(p1["v1_throughput_ops"], 42)
        self.assertTrue(p1["worker_a_sigkill_recovery"]["terminated_by_sigkill"])
        self.assertTrue(p1["worker_a_sigkill_recovery"]["accepted_bytes_preserved_exact"])
        self.assertEqual(p1["worker_a_sigkill_recovery"]["uncommitted_draft_disposition"], "REVOKED_BY_WORKER_SWAP")
        self.assertEqual(p1["v3_throughput_ops"], 70)
        self.assertEqual(
            p1["v3_interventions"],
            ["automate_intake", "expand_resource", "stagger_shifts"],
        )
        self.assertTrue(all(p1["lifecycle_exercises_verified"].values()))

    def test_02_living_project_2_capability_inheritance_and_cost_reduction(self) -> None:
        p2 = self.report["project_2_property_ops"]
        self.assertEqual(p2["idea_layer_brief_id"], "IL-9-3")
        self.assertEqual(p2["inheritance_mode"], "INHERITED")
        self.assertEqual(p2["incremental_eval_cost"], 1)
        self.assertEqual(p2["total_eval_budget_spent"], 2)
        self.assertIn(p2["v2_throughput_ops"], (68, 70))
        self.assertTrue(p2["budget_exhaustion_refusal_verified"])
        self.assertGreater(p2["per_project_eval_speedup_vs_conventional"], 10.0)

    def test_03_three_way_comparator_and_honest_breakeven_reporting(self) -> None:
        comp = self.report["three_way_comparator_20_projects"]
        inh = comp["openline_009_persistent_inheritance"]
        self.assertEqual(inh["completed_within_budget"], "20/20")
        self.assertEqual(inh["exact_solution_parity_with_conventional"], "20/20")
        self.assertGreater(inh["net_compounding_eval_multiplier_vs_conventional_20_projects"], 4.0)
        self.assertEqual(inh["breakeven_project_count_n"], 4)

    def test_04_all_nine_adversarial_falsifiers_blocked(self) -> None:
        self.assertTrue(self.report["all_falsifiers_blocked"])
        self.assertEqual(len(self.report["adversarial_falsifiers"]), 9)
        for name, item in self.report["adversarial_falsifiers"].items():
            self.assertTrue(item["blocked"], f"Falsifier not blocked: {name}")



    def test_05_d3_demand_recall_reopens_scenario_plan_and_research_seam_advisory(self) -> None:
        from openline_009_living_project import (
            LivingProjectEngine,
            export_idea_layer_opportunity,
            plan_living_project_contract,
        )
        with tempfile.TemporaryDirectory() as tmp:
            eng = LivingProjectEngine(state_dir=Path(tmp))
            opp = export_idea_layer_opportunity(6, "community groups", "toolkit", 0.0, 0)
            contract = plan_living_project_contract(opp, eval_budget_cap=300, target_throughput_ops=84)
            rec = eng.create_living_project(contract)
            pid = rec["project_id"]
            sha_before = rec["evidence"]["state_sha256"]

            # 1. Verify bounded research seam is strictly advisory and preserves accepted bytes
            seam_ok = eng.evaluate_proposal_at_research_seam(
                pid, goodhart_pressure_rg=0.15, evaluator_independent=True
            )
            self.assertTrue(seam_ok["accepted_sha256_preserved"])
            self.assertEqual(seam_ok["constraint_and_goodhart_gate"]["status"], "PASS")
            self.assertEqual(seam_ok["constraint_and_goodhart_gate"]["binding_constraint"], "workflow")

            seam_hold = eng.evaluate_proposal_at_research_seam(
                pid, goodhart_pressure_rg=0.80, evaluator_independent=False
            )
            self.assertEqual(seam_hold["constraint_and_goodhart_gate"]["status"], "HOLD_HARDEN_EVALUATOR_FIRST")

            # 2. Verify D.3 1-line support_sets fix: recalling 'demand' transitions scenario_plan to REOPEN
            recall_res = eng.recall_living_project_dependency(
                project_id=pid,
                station_node_id="demand",
                reason="Community surge demand revised upward",
            )
            self.assertEqual(recall_res["dnf_standing"], "REOPEN")
            self.assertTrue(any("demand" in r for r in recall_res["dnf_reasons"]))
            self.assertEqual(recall_res["preserved_accepted_sha256"], sha_before)
            self.assertTrue(recall_res["accepted_state_unchanged"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
