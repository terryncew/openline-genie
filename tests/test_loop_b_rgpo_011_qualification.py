#!/usr/bin/env python3
"""Unit & Falsification Tests for Loop B: Independent RGPO 011 Qualification (`tests/test_loop_b_rgpo_011_qualification.py`)."""
from __future__ import annotations

import unittest

from core.rgpo_obligation_gate import (
    ExecutableProofObligationGate,
    RGPOPolicyViolation,
    build_independent_unseen_executable_benchmark,
    enforce_zero_oracle,
    run_loop_b_independent_qualification,
)


class TestLoopBRGPO011Qualification(unittest.TestCase):
    def test_01_recursive_enforce_zero_oracle_blocks_nested_lists_and_tuples(self) -> None:
        payloads = [
            {"a": [{"ground_truth": 1}]},
            {"a": ({"hidden_holdout_target": 2},)},
            [{"nested": [{"oracle_label": 3}]}],
            {"a": [[], {"b": {"sealed_answer": 4}}]},
            {"x": [{"ground_truth_scale_um": 0.08}]},
        ]
        for p in payloads:
            with self.subTest(payload=repr(p)):
                with self.assertRaises(RGPOPolicyViolation):
                    enforce_zero_oracle(p)
        cyclic: dict = {}
        cyclic["self"] = cyclic
        enforce_zero_oracle(cyclic)

    def test_02_static_7_flag_dict_and_always_abstain_rejected_by_executable_gate(self) -> None:
        res = run_loop_b_independent_qualification()
        self.assertFalse(res["static_7_flag_dict_passes_executable_obligation_gate"])
        self.assertFalse(res["always_abstain_passes_executable_obligation_gate"])
        arms = res["arm_comparison"]
        self.assertEqual(arms["Arm1_Static_7Flag_Shortcut"]["tasks_independently_accepted"], 0)
        self.assertEqual(arms["Arm2_Always_Abstain"]["tasks_independently_accepted"], 0)
        self.assertEqual(arms["Arm3_Naive_Standard_Unit_Tests"]["tasks_independently_accepted"], 0)
        self.assertGreater(arms["Arm3_Naive_Standard_Unit_Tests"]["total_false_acceptances_on_hazards"], 0)
        self.assertEqual(arms["Arm4_Guarded_Executable_RGPO"]["tasks_independently_accepted"], 4)
        self.assertEqual(arms["Arm4_Guarded_Executable_RGPO"]["total_false_acceptances_on_hazards"], 0)
        self.assertEqual(arms["Arm4_Guarded_Executable_RGPO"]["mean_nominal_coverage_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
