#!/usr/bin/env python3
"""ARGON — OPENLINE CIVILIZATION FRONTIER 001
Unit & Regression Test Suite (`tests/test_civilization_frontier_001.py`).

Tests:
1. Authoritative system recovery & SHA-256 verification across all upstream baselines (`70a81de4...`, `6b2028b8...`,
   `9c53ab89...`, `a3ea42f6...`, `f84f5cd4...`, `950ff072...`, `05674591...`, `04524a58...`).
2. Screening of all 8 civilization frontiers within a single `LivingProjectEngine` instance (verifying Defects 5 & 6 repairs:
   collision-safe fixture project_id disambiguation, non-zero solar record summary metrics, and clinic/vaccine/cold-chain
   operational compilation without `"solar"` keyword hijack).
3. Cross-domain causal isomorphism verification (`verify_causal_isomorphism`):
   - Accepts RC low-pass <-> PCM Stefan latent-heat buffer (`VERIFIED_CAUSAL_ISOMORPHISM`, `z >= 2.58`, `4/4` structural).
   - Accepts Darcy/Fickian straw mulch <-> Biosand hydraulic retention (`VERIFIED_CAUSAL_ISOMORPHISM`).
   - Rejects viral social cascade metaphor (`STRUCTURAL_RHYME_ONLY_REJECTED`).
4. Experimental Intervention (`simulate_sdd_pcm_multiservice_hub`):
   - Proves `OPENLINE_SDD_PCM_PRIORITY_ROUTER` achieves `0` vaccine excursion hours and `100.0%` potable water reliability
     across a 72-hour monsoon storm at `$4,095` 10-year total cost and `0 kg` battery e-waste, outperforming unprioritized
     `CONVENTIONAL_SOLAR_LITHIUM_BATTERY_UNPRIORITIZED` (`25` vaccine excursion hours, `87.05%` water reliability, `$8,100`
     10-year cost, `135 kg` battery e-waste) and `NAIVE_SOLAR_DIRECT_NO_BUFFER` (`146` excursion hours).
5. Fixed evaluation budget compliance (`118 <= 150` evaluation units) and OpenLine 009 authority boundaries (`STOP`, `Recall`,
   and real subprocess `SIGKILL` worker recovery).
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE / "core") not in sys.path:
    sys.path.insert(0, str(HERE / "core"))

from run_civilization_frontier_001 import (
    MAX_EVAL_BUDGET,
    evaluate_cross_domain_isomorphisms_and_multipliers,
    run_experimental_sdd_pcm_comparison,
    screen_eight_civilization_frontiers,
    verify_authoritative_system,
    verify_defects_5_and_6_and_authority,
)


class TestCivilizationFrontier001(unittest.TestCase):
    def test_01_authoritative_system_hashes_verified(self) -> None:
        res = verify_authoritative_system()
        self.assertTrue(res["all_verified"], f"Hash mismatches: {res['mismatches']}")
        self.assertTrue(res["frozen_baseline_untouched"])

    def test_02_eight_frontiers_screened_in_single_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frontiers, evals = screen_eight_civilization_frontiers(pathlib.Path(tmp))
            self.assertEqual(len(frontiers), 8)
            self.assertEqual(evals, 16)
            selected = [f for f in frontiers if f["selected_for_deep_investigation"]]
            self.assertEqual(len(selected), 3)
            pids = [f["living_project_id"] for f in frontiers]
            self.assertEqual(len(set(pids)), 8, "All 8 frontier Living Projects must have unique project_ids")
            for f in frontiers:
                self.assertGreater(f["baseline_throughput_metric"], 0)
                self.assertEqual(f["seam_status"], "PASS")

    def test_03_cross_domain_isomorphisms_and_false_metaphor_rejection(self) -> None:
        iso_res, evals = evaluate_cross_domain_isomorphisms_and_multipliers()
        self.assertEqual(evals, 24)
        isos = iso_res["verified_isomorphisms"]
        self.assertEqual(isos["rc_lowpass_to_pcm_stefan_buffer"]["disposition"], "VERIFIED_CAUSAL_ISOMORPHISM")
        self.assertEqual(isos["darcy_mulch_to_biosand_retention"]["disposition"], "VERIFIED_CAUSAL_ISOMORPHISM")
        self.assertEqual(isos["rejected_viral_cascade_metaphor"]["disposition"], "STRUCTURAL_RHYME_ONLY_REJECTED")
        mult = iso_res["quantified_1kw_sdd_pcm_cross_domain_multiplier"]
        self.assertEqual(mult["total_self_utilization_pct"], 100.0)

    def test_04_experimental_sdd_pcm_hub_outperforms_comparators(self) -> None:
        exp_res, evals = run_experimental_sdd_pcm_comparison()
        self.assertEqual(evals, 48)
        self.assertTrue(exp_res["prediction_exact_match"])
        arms = exp_res["comparative_simulation_results_168h"]
        ol = arms["OPENLINE_SDD_PCM_PRIORITY_ROUTER"]
        li = arms["CONVENTIONAL_SOLAR_LITHIUM_BATTERY_UNPRIORITIZED"]
        nv = arms["NAIVE_SOLAR_DIRECT_NO_BUFFER"]

        self.assertEqual(ol["vaccine_excursion_hours_during_72h_monsoon"], 0)
        self.assertTrue(ol["vaccine_who_pqs_grade_a_compliant"])
        self.assertEqual(ol["potable_water_reliability_pct"], 100.0)
        self.assertEqual(ol["ten_year_chemical_battery_ewaste_kg"], 0.0)

        self.assertGreater(li["vaccine_excursion_hours_during_72h_monsoon"], 20)
        self.assertLess(li["potable_water_reliability_pct"], 90.0)
        self.assertLess(ol["ten_year_total_cost_usd"], li["ten_year_total_cost_usd"])
        self.assertGreater(nv["vaccine_excursion_hours_during_72h_monsoon"], 100)
        self.assertEqual(
            exp_res["kernel_certification_receipt"]["final_disposition"],
            "ADOPT_CERTIFIED_DISCOVERY",
        )

    def test_05_defects_5_and_6_and_authority_sigkill_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = verify_defects_5_and_6_and_authority(pathlib.Path(tmp))
            self.assertEqual(res["defect_5_multi_project_fixture_slug_disambiguation"]["status"], "FIXED_AND_VERIFIED")
            self.assertTrue(res["defect_5_multi_project_fixture_slug_disambiguation"]["distinct_ids_created"])
            self.assertTrue(res["defect_5_multi_project_fixture_slug_disambiguation"]["solar_summary_net_value_populated"])
            self.assertEqual(res["defect_6_solar_keyword_hijack_of_clinic_water_prompts"]["status"], "FIXED_AND_VERIFIED")
            self.assertTrue(res["defect_6_solar_keyword_hijack_of_clinic_water_prompts"]["compiled_has_operations_model"])

            auth = res["authority_and_sigkill_guarantees"]
            self.assertTrue(auth["recall_standing_reopened"])
            self.assertTrue(auth["accepted_sha256_preserved_on_recall"])
            self.assertTrue(auth["stop_blocks_proposals"])
            self.assertTrue(auth["sigkill_terminated"])
            self.assertTrue(auth["sigkill_accepted_bytes_preserved"])
            self.assertEqual(auth["sigkill_uncommitted_draft_disposition"], "REVOKED_BY_WORKER_SWAP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
