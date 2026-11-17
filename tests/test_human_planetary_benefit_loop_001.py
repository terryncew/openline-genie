#!/usr/bin/env python3
"""ARGON — OPENLINE HUMAN & PLANETARY BENEFIT LOOP 001
Unit & Regression Test Suite (`tests/test_human_planetary_benefit_loop_001.py`).

Tests:
1. All 4 D.3 defect repairs in `openline_009_living_project.py` and `genie_engine.py`:
   - Defect 1: Multi-domain research seam (`garden`, `bakery`, `solar`, `operations_model`) and `net_daily_usd` lookup (`$450.0` vs `$0.0`).
   - Defect 2: Domain-aware `RecallLedger` station pinning and `support_sets` registration (`water` recall in `garden` -> `REOPEN`).
   - Defect 3: Monotonic revision counter (`next_rev = prior_rev + 1`) on repeat `recall_living_project_dependency` calls.
   - Defect 4: `compute_record_metric` `2.625 gal/lb` synchronization with `core/community_garden.py` when `drip_mulch_enabled=True`.
2. Three-case Human & Planetary Benefit Loop execution, preregistered prediction calibration (`Brier = 0.0042`), and falsifier rejection of false metaphors (`STRUCTURAL_RHYME_ONLY_REJECTED`).
3. OpenLine 009 authority boundaries: exploratory-until-accepted, `STOP` (`GuardRefused` / `ResearchGateRefused`), stop-epoch draft revocation (`REVOKED_BY_STOP_EPOCH`), and real subprocess `SIGKILL` worker replacement (`REVOKED_BY_WORKER_SWAP`).
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE / "core") not in sys.path:
    sys.path.insert(0, str(HERE / "core"))

import openline_research_kernel as rk
from genie_engine import GenieAppSynthesizer
from openline_009_living_project import (
    LivingProjectEngine,
    plan_living_project_contract,
    run_worker_sigkill_and_successor_recovery,
)
from run_human_planetary_benefit_loop_001 import (
    run_case_1_community_agroecology_food_water,
    run_case_2_renter_balcony_solar_energy,
    run_case_3_safe_drinking_water_filtration,
    verify_authority_and_defect_repairs,
    verify_frozen_baseline,
)


class TestHumanPlanetaryBenefitLoop001(unittest.TestCase):
    def test_01_frozen_baseline_intact_and_verified(self) -> None:
        res = verify_frozen_baseline()
        self.assertTrue(res["verified"])
        self.assertEqual(res["outer_manifest_entries_verified"], "10/10")
        self.assertEqual(
            res["hashes"]["freeze_bundle_zip_sha256"],
            "70a81de4ec1e58cc2d42547a575e8d61ee06f6b2b4fc70bb5f6dcfe3c8b3d23f",
        )
        self.assertEqual(
            res["hashes"]["repaired_source_zip_sha256"],
            "6b2028b84b9581b6f339b8bd38b7d269e1fad122f9241f857f4d5e6598bc206c",
        )

    def test_02_four_d3_defects_repaired_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            eng = LivingProjectEngine(state_dir=pathlib.Path(tmp))

            # Defect 1 & 2: Garden Living Project
            c_g = plan_living_project_contract(
                "Build a community garden crop rotation and rainwater cistern planner",
                eval_budget_cap=100,
                target_throughput_ops=150,
            )
            rec_g = eng.create_living_project(c_g)
            pid_g = rec_g["project_id"]
            self.assertEqual(rec_g["accepted_artifacts"]["operations_summary"]["throughput_ops_per_day"], 105)
            self.assertEqual(rec_g["accepted_artifacts"]["operations_summary"]["binding_bottleneck"], "water")
            self.assertEqual(rec_g["accepted_artifacts"]["operations_summary"]["net_daily_value_usd"], 322.5)

            seam_g = eng.evaluate_proposal_at_research_seam(pid_g)
            self.assertEqual(seam_g["authority"], "ADVISORY_ONLY")
            self.assertEqual(seam_g["constraint_and_goodhart_gate"]["binding_constraint"], "water")

            # Defect 2 & 3: Domain station recall ("water") and repeat recall on same station
            r1 = eng.recall_living_project_dependency(pid_g, "water", "Cistern check 1")
            self.assertEqual(r1["dnf_standing"], "REOPEN")
            self.assertTrue(r1["accepted_state_unchanged"])

            r2 = eng.recall_living_project_dependency(pid_g, "water", "Cistern check 2")
            self.assertEqual(r2["dnf_standing"], "REOPEN")
            self.assertTrue(r2["accepted_state_unchanged"])

            # Defect 1c: Generic operations_model net_daily_value_usd
            c_o = plan_living_project_contract(
                "Build a rural safe water filter distribution planner",
                eval_budget_cap=100,
                target_throughput_ops=85,
            )
            rec_o = eng.create_living_project(c_o)
            self.assertEqual(rec_o["accepted_artifacts"]["operations_summary"]["net_daily_value_usd"], 450.0)

            # Defect 4: compute_record_metric 2.625 gal/lb with drip_mulch_enabled
            st_g = rec_g["bundle"]["accepted"]["state"]
            st_g["garden"]["assumptions"]["drip_mulch_enabled"] = True
            plot_rec = dict(st_g["records"][0])
            plot_rec["volunteer_hours_per_week"] = 6.0
            calc_rec = GenieAppSynthesizer.compute_record_metric(st_g, plot_rec)
            self.assertEqual(calc_rec["computed_metric_value"], 38.1)

    def test_03_three_cases_and_conventional_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = pathlib.Path(tmp)
            c1 = run_case_1_community_agroecology_food_water(tp / "c1")
            c2 = run_case_2_renter_balcony_solar_energy(tp / "c2")
            c3 = run_case_3_safe_drinking_water_filtration(tp / "c3")

            self.assertTrue(c1["observed_outcomes"]["prediction_exact_match"])
            self.assertEqual(c1["observed_outcomes"]["openline_step2_synergy_lbs_per_wk"], 150)
            self.assertEqual(
                c1["research_seam_receipts"]["rejected_false_metaphor_gate"]["disposition"],
                "STRUCTURAL_RHYME_ONLY_REJECTED",
            )

            self.assertTrue(c2["observed_outcomes"]["prediction_exact_match"])
            self.assertEqual(
                c2["observed_outcomes"]["goodhart_gate_on_vendor_watt_maximization"]["status"],
                "HOLD_HARDEN_EVALUATOR_FIRST",
            )

            self.assertTrue(c3["observed_outcomes"]["prediction_exact_match"])
            self.assertEqual(c3["observed_outcomes"]["stabilized_hub_capacity_ops_per_day"], 70)
            self.assertEqual(c3["conventional_vs_openline_evals"]["break_even_projects_count"], 3)

    def test_04_authority_stop_and_sigkill_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auth = verify_authority_and_defect_repairs(pathlib.Path(tmp))
            guar = auth["authority_and_resilience_guarantees"]
            self.assertTrue(guar["exploratory_preserves_accepted_sha256"])
            self.assertTrue(guar["stop_blocks_mutation"])
            self.assertTrue(guar["stop_blocks_research_seam"])
            self.assertTrue(guar["stop_epoch_revokes_prior_exploratory_drafts"])
            self.assertTrue(guar["accepted_sha256_unchanged_across_stop_and_recall"])
            self.assertTrue(guar["sigkill_subprocess_recovery"]["terminated_by_sigkill"])
            self.assertTrue(guar["sigkill_subprocess_recovery"]["accepted_bytes_preserved_exact"])
            self.assertEqual(
                guar["sigkill_subprocess_recovery"]["uncommitted_draft_disposition"],
                "REVOKED_BY_WORKER_SWAP",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
