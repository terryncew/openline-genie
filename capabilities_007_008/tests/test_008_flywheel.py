"""Unit tests for OpenLine 008 Recursive Intelligence Compression Flywheel (G1, G2, G3, Zero-Oracle, Receipts)."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import kernel
from run_exp1_compression import build_trajectory_episodes, verify_trajectory_stabilization
from run_exp2_exp3_flywheel import build_g2_portfolio_suite, build_g3_incident_audit_suite, verify_g2_portfolio, verify_g3_bundle


class TestOpenLine008Flywheel(unittest.TestCase):
    def test_g1_compressed_trajectory_stabilizer_and_receipt(self):
        eps = build_trajectory_episodes("dev")
        # Test compound two-stage shock episode (index 2)
        ep = eps[2]
        r = kernel.execute({
            "facts": ep["facts"],
            "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"],
            "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
        }, ROOT / "registry_g1.json")
        self.assertEqual(r["disposition"], "EXECUTED")
        exec_item = r["executed"][0]
        self.assertIn("receipt", exec_item)
        self.assertEqual(len(exec_item["receipt"]["input_sha256"]), 64)
        self.assertEqual(len(exec_item["receipt"]["output_sha256"]), 64)
        res = exec_item["result"]
        self.assertTrue(res["escalated_to_staged_solver"])
        self.assertEqual(len(res["interventions"]), 2)
        self.assertTrue(verify_trajectory_stabilization(ep["facts"], res, ep["expected"]))

    def test_g2_coupled_portfolio_allocator_uses_g1(self):
        tasks = build_g2_portfolio_suite("dev")
        t = tasks[0]
        r = kernel.execute({
            "facts": t["facts"],
            "required_outputs": ["portfolio_feasible", "facility_plans", "charge_schedule", "total_portfolio_capex_usd", "total_portfolio_ops_usd"],
            "constraints": {"max_relative_cost_units": 4, "strict_zero_oracle": True},
        }, ROOT / "registry_g2.json")
        self.assertEqual(r["disposition"], "EXECUTED")
        res = r["executed"][0]["result"]
        self.assertTrue(verify_g2_portfolio(t["facts"], res, t["expected"]))
        self.assertLess(res["domain_evaluations"], 250)

    def test_g3_distilled_artifact_gate_and_onnx_escalation(self):
        bundles = build_g3_incident_audit_suite("dev")
        # Bundle 0: safe Python AST -> 0 ONNX calls, ALLOW, portfolio executed
        r0 = kernel.execute({
            "facts": bundles[0]["facts"],
            "required_outputs": ["triage_action", "portfolio_executed", "portfolio_result"],
            "constraints": {"max_relative_cost_units": 4, "strict_zero_oracle": True},
        }, ROOT / "registry_g3.json")
        res0 = r0["executed"][0]["result"]
        self.assertEqual(res0["triage_action"], "ALLOW")
        self.assertEqual(res0["onnx_calls"], 0)
        self.assertTrue(verify_g3_bundle(bundles[0]["facts"], res0, bundles[0]["expected"]))

        # Bundle 5: malicious rm -rf -> 0 ONNX calls, HOLD, portfolio not executed
        r5 = kernel.execute({
            "facts": bundles[5]["facts"],
            "required_outputs": ["triage_action", "portfolio_executed", "portfolio_result"],
            "constraints": {"max_relative_cost_units": 4, "strict_zero_oracle": True},
        }, ROOT / "registry_g3.json")
        res5 = r5["executed"][0]["result"]
        self.assertEqual(res5["triage_action"], "HOLD")
        self.assertEqual(res5["onnx_calls"], 0)
        self.assertFalse(res5["portfolio_executed"])

        # Bundle 7: ambiguous prose-padded wrapper -> escalates to 1 ONNX call
        r7 = kernel.execute({
            "facts": bundles[7]["facts"],
            "required_outputs": ["triage_action", "portfolio_executed", "portfolio_result"],
            "constraints": {"max_relative_cost_units": 4, "strict_zero_oracle": True},
        }, ROOT / "registry_g3.json")
        res7 = r7["executed"][0]["result"]
        self.assertEqual(res7["onnx_calls"], 1)
        self.assertTrue(res7["escalated_to_onnx"])
        self.assertTrue(verify_g3_bundle(bundles[7]["facts"], res7, bundles[7]["expected"]))

    def test_strict_zero_oracle_refuses_label_leakage(self):
        ep = build_trajectory_episodes("dev")[0]
        contaminated = copy.deepcopy(ep["facts"])
        contaminated["gold_action"] = "ALLOW"
        r = kernel.execute({
            "facts": contaminated,
            "required_outputs": ["feasible_stabilization"],
            "constraints": {"strict_zero_oracle": True},
        }, ROOT / "registry_g3.json")
        self.assertEqual(r["disposition"], "REFUSE")
        self.assertIn("REFUSE_LABEL_LEAKAGE", r["reason"])

    def test_owner_stop_and_external_effect_denial(self):
        ep = build_trajectory_episodes("dev")[0]
        r_stop = kernel.execute({
            "facts": ep["facts"],
            "required_outputs": ["feasible_stabilization"],
            "constraints": {"owner_stop": True},
        }, ROOT / "registry_g3.json")
        self.assertEqual(r_stop["disposition"], "STOP")

        r_deny = kernel.execute({
            "facts": ep["facts"],
            "required_outputs": ["feasible_stabilization"],
            "constraints": {"requires_external_effect": True},
        }, ROOT / "registry_g3.json")
        self.assertEqual(r_deny["disposition"], "DENY")

    def test_source_tamper_fails_closed(self):
        p = ROOT / "generated/compressed_trajectory_stabilizer.py"
        orig = p.read_bytes()
        try:
            p.write_bytes(orig + b"\n# unauthorized mutation\n")
            ep = build_trajectory_episodes("dev")[0]
            with self.assertRaises(kernel.ContractError):
                kernel.execute({
                    "facts": ep["facts"],
                    "required_outputs": ["feasible_stabilization"],
                    "constraints": {},
                }, ROOT / "registry_g3.json")
        finally:
            p.write_bytes(orig)

    def test_changed_domain_interface_refusal(self):
        ep = copy.deepcopy(build_trajectory_episodes("dev")[0])
        ep["facts"]["domain_module"] = "upstream/nonexistent_module.py"
        r = kernel.execute({
            "facts": ep["facts"],
            "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"],
            "constraints": {"strict_zero_oracle": True},
        }, ROOT / "registry_g3.json")
        self.assertEqual(r["disposition"], "INVESTIGATE")
        self.assertEqual(r["reason"], "executor_preconditions_failed")

    def test_economic_break_even_and_compounding(self):
        exp1 = json.loads((ROOT.parent / "evidence_008/exp1_cp1/exp1_compression_summary.json").read_text())
        exp23 = json.loads((ROOT.parent / "evidence_008/exp2_exp3/exp2_exp3_flywheel_summary.json").read_text())
        # Verify N=1 net evals is negative (creation cost > 1-shot savings), while N=10 and N=100 are positive
        self.assertLess(exp1["economic_acceptance_g1"]["net_savings_after_n_uses"]["N_1"]["net_domain_evaluations_saved"], 0)
        self.assertGreater(exp1["economic_acceptance_g1"]["net_savings_after_n_uses"]["N_10"]["net_domain_evaluations_saved"], 0)
        self.assertGreater(exp1["economic_acceptance_g1"]["net_savings_after_n_uses"]["N_100"]["net_domain_evaluations_saved"], 80000)
        # Verify G2 creation speedup from G1 > 5x
        self.assertGreater(exp23["experiment_2_part_a_generation_2"]["cross_task_transfer_from_g1"]["creation_evals_speedup_from_g1"], 5.0)


if __name__ == "__main__":
    unittest.main()
