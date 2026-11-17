#!/usr/bin/env python3
"""Regression Test Suite for Visual-Geometric Counterfactual Perception & Repair
(`tests/test_visual_intelligence_breakthrough_001.py`).

Uses the 16 regression fixtures in `tests/visual_regression_16_cases.py` (strictly
classified as regression tests, NOT unseen generalization or self-certified acceptance).
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from core.independent_evaluation_boundary import submit_candidate_repair_for_external_evaluation
from core.portable_verified_inheritance import (
    WorkerBPortableInheritanceRuntime,
    qualify_and_export_visual_capsule_worker_a,
)
from core.visual_intelligence_harness import (
    CANDIDATE_HAS_EVALUATION_AUTHORITY,
    VHarnessAtomicOperators,
    check_candidate_visual_and_functional_invariants,
    diagnose_visual_causal_bottleneck,
    observe_rendered_artifact,
    repair_visual_artifact,
)
from run_visual_intelligence_breakthrough_001 import (
    run_100_yard_inheritance_regression,
    run_independent_visual_falsification_suite,
    verify_dogfood_repairs_and_seven_apps,
)
from tests.visual_regression_16_cases import (
    CLAIMS_UNSEEN_GENERALIZATION,
    IS_SEALED_HOLDOUT,
    REGRESSION_SUITE_ONLY,
    build_regression_16_case_suite,
    run_regression_16_case_comparison,
)


class TestVisualIntelligenceBreakthrough001(unittest.TestCase):
    def test_01_vharness_five_atomic_operators(self) -> None:
        cases = build_regression_16_case_suite()
        obs = observe_rendered_artifact(cases[2].case_id, cases[2].initial_html, artifact_family=cases[2].family)
        tr = VHarnessAtomicOperators.transcribe(obs)
        self.assertEqual(tr["action"], "mcp__atomic__transcribe")
        self.assertGreaterEqual(tr["children_count"], 4)

        matches = VHarnessAtomicOperators.grep(obs, "node-verifier")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], "node-verifier")

        insp = VHarnessAtomicOperators.inspect(obs, "node-verifier", format="image")
        self.assertTrue(insp["clipped_by_viewbox"])

        al = VHarnessAtomicOperators.align(obs)
        self.assertFalse(al["match"])

        df = VHarnessAtomicOperators.diff(obs, mode="prominent")
        self.assertGreaterEqual(df["discrepancy_count"], 1)

    def test_02_sixteen_case_regression_suite_and_decontamination(self) -> None:
        self.assertFalse(CANDIDATE_HAS_EVALUATION_AUTHORITY)
        self.assertTrue(REGRESSION_SUITE_ONLY)
        self.assertFalse(IS_SEALED_HOLDOUT)
        self.assertFalse(CLAIMS_UNSEEN_GENERALIZATION)

        res = run_regression_16_case_comparison()
        arms = res["arms"]
        self.assertEqual(arms["A_EXISTING_GENIE"]["regression_cases_passed_precheck"], 2)
        self.assertEqual(arms["B_CONVENTIONAL"]["regression_cases_passed_precheck"], 3)
        self.assertEqual(arms["C_EXTERNAL_VISUAL_VHARNESS"]["regression_cases_passed_precheck"], 7)
        self.assertEqual(arms["D_HYBRID_EMERGENCE"]["regression_cases_passed_precheck"], 16)
        self.assertEqual(arms["D_HYBRID_EMERGENCE"]["false_self_pass_count"], 0)
        # Verify candidate never claims independent acceptance on any case
        for c in arms["D_HYBRID_EMERGENCE"]["cases"]:
            self.assertFalse(c["independently_accepted"])
            self.assertEqual(c["split"], "regression_fixture")

    def test_03_worker_a_to_worker_b_inheritance_and_assumption_recall(self) -> None:
        hy = run_100_yard_inheritance_regression()
        self.assertTrue(hy["all_10_steps_passed"])
        self.assertEqual(hy["capsule_id"], "CAPSULE-ARGON-VIS-001")

        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            cap = qualify_and_export_visual_capsule_worker_a(Path(dir_a))
            wb = WorkerBPortableInheritanceRuntime(Path(dir_b))
            imp = wb.verify_and_import_capsule(asdict(cap))
            self.assertEqual(imp["standing"], "ACCEPTED")

            # Verify automatic assumption-drift reopen on Worker B for visual capsule
            wb.update_live_environment(data_version="dataset-v9.9-drifted")
            with self.assertRaises(PermissionError):
                wb.execute_on_unseen_task({
                    "ref_ok": True,
                    "fixed_header_overlap_px": 10.0,
                    "svg_overflow_px": 0.0,
                    "room_overlap_iou": 0.0,
                    "landlocked_rooms": 0,
                    "state_desync_count": 0,
                    "functional_controls_before": 2,
                    "functional_controls_after": 2,
                })
            self.assertEqual(wb.current_standing, "REOPEN")

    def test_04_independent_adversarial_falsification_all_10_vectors(self) -> None:
        fals = run_independent_visual_falsification_suite()
        self.assertEqual(fals["total_vectors"], 10)
        self.assertEqual(fals["vectors_passed"], 10)
        self.assertTrue(fals["all_passed"])

    def test_05_r5_restore_and_form_defaults_live_dogfood(self) -> None:
        dogfood = verify_dogfood_repairs_and_seven_apps()
        self.assertTrue(dogfood["all_7_workbenches_offline_clean"])
        self.assertTrue(dogfood["r5_restore_sequential_accepts_verified"])
        self.assertTrue(dogfood["r5_restore_external_revocation_still_blocked"])
        self.assertTrue(dogfood["form_defaults_chromium_preserved_untouched_tariff_0_32"])
        self.assertEqual(dogfood["robotics_and_ratchet_chromium_pageerrors"], 0)


if __name__ == "__main__":
    unittest.main()
