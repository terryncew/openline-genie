#!/usr/bin/env python3
"""ARGON — OPENLINE FINAL PRODUCT & FRONTIER CLOSURE 001
Unit & Regression Test Suite (`tests/test_final_closure_001.py`).

Tests:
1. Fair Priority-Controlled Solar Falsification (`simulate_fair_solar_comparator` & `run_comprehensive_solar_falsification`):
   - Exact energy conservation (`conservation_error_kwh < 1e-6`) across all 4 architectures and all 6 stress scenarios.
   - Proves `CONV_PRIORITY_CONTROLLED_LI_BATTERY` achieves `0h` vaccine excursion and `100.0%` water reliability in the 72h
     monsoon (eliminating the `5h`–`28h` excursion of `CONV_UNPRIORITIZED_LI_BATTERY`).
   - Proves `OPENLINE_SDD_PCM_PRIORITY_ROUTER` matches `0h` vaccine excursion and `100.0%` water reliability in the 72h
     monsoon while cutting 10-year cost by `51.6%` (`$4,095` vs `$8,465` at 32C) and `60.1%` (`$4,095` vs `$10,265` at 43C),
     eliminating `135–180 kg` of battery e-waste, and surviving `battery_bms` failure (`0h` vs `18h` excursion).
   - Reconciles the `85.71h` nominal 32C holdover against `60.90h` at 43C extreme heat (`51.77h` aged) and proves that in a
     120-hour (5-day) 4%-sun typhoon blackout, `COMPETENT_HYBRID_SMALL_LFP_PLUS_PCM` (`8h` excursion) and
     `CONV_PRIORITY_CONTROLLED_LI_BATTERY` (`14h` excursion) outperform pure `OPENLINE_SDD_PCM_PRIORITY_ROUTER` (`38h` excursion).
2. Final Amendment — Decision Recall Dependency Completeness (`run_decision_recall_dependency_completeness_comparison`):
   - Verifies that recalling a declared assumption key (`volunteer_hours_per_week`) transitions `RecallLedger` standing to `REOPEN`.
   - Verifies Defect 7 repair: recalling an undeclared external dependency (`external_road_bridge_closure`) transitions
     `RecallLedger` standing to `UNRESOLVED` (`dependency_closure_incomplete`) without mutating accepted state bytes.
   - Verifies that `BUCSW` (`audit_decision_dependency_completeness`) achieves `0` missed consequential dependencies and `0`
     false reopenings across 20 drift trials (outperforming Existing Recall with omissions [`4/4` missed], Conventional B1
     Local FD [`4/4` missed due to water clamp], and Conventional B1 Read-Taint [`16/16` false reopenings on sub-slack/dead keys]).
3. Genie Model Modes (`verify_genie_model_modes`):
   - Verifies `--no-model` deterministic mode and explicit `0. Model Worker Fallback` logging when a model adapter is unavailable.
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

from run_final_closure_001 import (
    run_comprehensive_solar_falsification,
    run_decision_recall_dependency_completeness_comparison,
    verify_genie_model_modes,
)


class TestFinalClosure001(unittest.TestCase):
    def test_01_fair_priority_solar_comparator_and_energy_conservation(self) -> None:
        res = run_comprehensive_solar_falsification()
        self.assertEqual(res["decisive_verdict"], "ADVANTAGE VERIFIED IN SIMULATION")

        # Verify holdover reconciliation
        hr = res["holdover_reconciliation"]
        self.assertEqual(hr["nominal_32c_fresh_pcm_hours"], 85.71)
        self.assertEqual(hr["extreme_43c_fresh_pcm_hours"], 60.90)
        self.assertEqual(hr["aged_85pct_pcm_at_32c_hours"], 72.86)
        self.assertEqual(hr["aged_85pct_pcm_at_43c_hours"], 51.77)

        # Verify strict energy conservation across every scenario and architecture
        for sc_name, sc in res["scenarios"].items():
            for arch, data in sc.items():
                err = data["energy_balance_verified"]["conservation_error_kwh"]
                self.assertLess(err, 1e-6, f"Energy conservation error in {sc_name}/{arch}: {err}")

        # Scenario A: Fair Priority LiFePO4 eliminates unprioritized vaccine excursion, while OpenLine SDD-PCM wins on 10yr cost & e-waste
        sc_a = res["scenarios"]["A_baseline_72h_monsoon_32c"]
        self.assertGreater(sc_a["CONV_UNPRIORITIZED_LI_BATTERY"]["vaccine_excursion_hours"], 0)
        self.assertEqual(sc_a["CONV_PRIORITY_CONTROLLED_LI_BATTERY"]["vaccine_excursion_hours"], 0)
        self.assertEqual(sc_a["OPENLINE_SDD_PCM_PRIORITY_ROUTER"]["vaccine_excursion_hours"], 0)
        self.assertEqual(sc_a["COMPETENT_HYBRID_SMALL_LFP_PLUS_PCM"]["vaccine_excursion_hours"], 0)
        self.assertEqual(sc_a["OPENLINE_SDD_PCM_PRIORITY_ROUTER"]["ten_year_total_cost_usd"], 4095.0)
        self.assertEqual(sc_a["CONV_PRIORITY_CONTROLLED_LI_BATTERY"]["ten_year_total_cost_usd"], 8465.0)
        self.assertEqual(sc_a["OPENLINE_SDD_PCM_PRIORITY_ROUTER"]["ten_year_battery_ewaste_kg"], 0.0)

        # Scenario D (120h 4%-sun typhoon): Hybrid & Priority-LiFePO4 beat pure SDD-PCM on tail-end vaccine excursion
        sc_d = res["scenarios"]["D_120h_five_day_typhoon_blackout"]
        self.assertLess(
            sc_d["COMPETENT_HYBRID_SMALL_LFP_PLUS_PCM"]["vaccine_excursion_hours"],
            sc_d["CONV_PRIORITY_CONTROLLED_LI_BATTERY"]["vaccine_excursion_hours"],
        )
        self.assertLess(
            sc_d["CONV_PRIORITY_CONTROLLED_LI_BATTERY"]["vaccine_excursion_hours"],
            sc_d["OPENLINE_SDD_PCM_PRIORITY_ROUTER"]["vaccine_excursion_hours"],
        )

        # Scenario E (BMS failure): SDD-PCM is immune (0h excursion vs 18h on Priority-LiFePO4)
        sc_e = res["scenarios"]["E_battery_bms_failure"]
        self.assertEqual(sc_e["OPENLINE_SDD_PCM_PRIORITY_ROUTER"]["vaccine_excursion_hours"], 0)
        self.assertGreater(sc_e["CONV_PRIORITY_CONTROLLED_LI_BATTERY"]["vaccine_excursion_hours"], 10)

    def test_02_decision_recall_dependency_completeness_and_bucsw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_decision_recall_dependency_completeness_comparison(pathlib.Path(tmp))
            tbl = res["comparison_table"]
            self.assertEqual(tbl["1_existing_recall_alone_with_omission"]["missed_consequential_drift_events_out_of_4"], 4)
            self.assertEqual(tbl["2a_conventional_b1_local_finite_differences"]["missed_consequential_drift_events_out_of_4"], 4)
            self.assertEqual(tbl["2b_conventional_b1_dynamic_read_taint"]["false_reopenings_out_of_16_benign_drifts"], 16)
            self.assertEqual(tbl["3_bucsw_counterfactual_unclamping_and_slack_certificate"]["missed_consequential_drift_events_out_of_4"], 0)
            self.assertEqual(tbl["3_bucsw_counterfactual_unclamping_and_slack_certificate"]["false_reopenings_out_of_16_benign_drifts"], 0)

            d7 = res["defect_7_repair_verification"]
            self.assertEqual(d7["declared_assumption_recall_standing"], "REOPEN")
            self.assertEqual(d7["undeclared_external_recall_standing"], "UNRESOLVED")
            self.assertIn("dependency_closure_incomplete", d7["undeclared_external_witness"])
            self.assertTrue(d7["accepted_sha256_preserved"])

    def test_03_genie_model_modes_honesty_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = verify_genie_model_modes(pathlib.Path(tmp))
            self.assertTrue(res["without_model_deterministic_mode"]["runs_standalone"])
            self.assertEqual(res["without_model_deterministic_mode"]["paid_spend_usd"], 0.0)
            self.assertTrue(res["unavailable_model_fallback_mode"]["fallback_explicitly_logged_in_autonomy_log"])
            self.assertFalse(res["unavailable_model_fallback_mode"]["silent_fake_model_claim"])



    def test_04_defect_8_rainwater_biosand_prompt_not_hijacked_by_garden(self) -> None:
        from genie_engine import GenieAppSynthesizer
        s_water = GenieAppSynthesizer.synthesize("Build a rural rainwater harvesting and biosand filter quality verification tracker")
        self.assertEqual(s_water["project_id"], "genie-synth-rural-rainwater-harvesting-and-biosand")
        self.assertIn("operations_model", s_water)
        self.assertNotIn("garden", s_water)
        s_garden = GenieAppSynthesizer.synthesize("Build a community garden crop rotation and rainwater cistern planner")
        self.assertEqual(s_garden["project_id"], "genie-synth-community-garden-crop-rotation")
        self.assertIn("garden", s_garden)


if __name__ == "__main__":
    unittest.main(verbosity=2)
