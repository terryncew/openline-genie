#!/usr/bin/env python3
"""
OPENLINE MIF-PWS v2 PHYSICAL EXPERIMENT & MANUFACTURING QUALIFICATION 004
Module: tests/test_physical_experiment_004.py

Independent unit and constitutive verification test suite.
Unlike static receipt-flag checks, every test invokes the underlying PDE/Laplace/routing/thermodynamic
solvers directly from scratch and verifies physical conservation laws and file geometry.
"""

from __future__ import annotations
import dataclasses
import hashlib
import json
import sys
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from physics_and_manufacturing_sim import (
    APPROACH_SPECS,
    solve_3d_pdn_resistance_and_joule_heating,
    evaluate_interconnect_pin_escape,
    compute_process_and_prototype_yield,
    evaluate_corrosion_and_dielectric_safety,
    evaluate_cte_fatigue_life,
    simulate_coupled_thermal_hydraulic_response,
    compute_pinch_bounded_med_distillate,
    evaluate_all_manufacturing_approaches,
)
from bom_and_supplier_matrix import export_bom_and_supplier_files
from generate_cad_and_drawings import build_all_cad_and_drawings
from independent_falsification_and_verification import generate_master_evidence


class TestMifPwsV2PhysicalExperiment004(unittest.TestCase):
    def test_01_3d_laplace_pdn_solver_no_assigned_flags(self) -> None:
        m0 = solve_3d_pdn_resistance_and_joule_heating(APPROACH_SPECS["M0_CONV_BASELINE"])
        m2 = solve_3d_pdn_resistance_and_joule_heating(APPROACH_SPECS["M2_HYBRID_CNC_CMC"])
        m3 = solve_3d_pdn_resistance_and_joule_heating(APPROACH_SPECS["M3_FULL_INTEGRATION"])
        s0 = solve_3d_pdn_resistance_and_joule_heating(APPROACH_SPECS["S0_SURROGATE_50W_50A"])
        self.assertGreater(m0["pdn_joule_loss_w"], 180.0)
        self.assertLess(m2["pdn_joule_loss_w"], 25.0)
        self.assertLess(m3["pdn_joule_loss_w"], 10.0)
        self.assertAlmostEqual(m2["pdn_resistance_mohm"], s0["pdn_resistance_mohm"], places=5)
        self.assertTrue(m2["passes_current_density_limit"])

    def test_02_hbm3e_pin_escape_falsification_and_coupon_routing(self) -> None:
        r_8um = evaluate_interconnect_pin_escape(8.0, 1)
        r_cowos_r = evaluate_interconnect_pin_escape(2.0, 6)
        r_cowos_l = evaluate_interconnect_pin_escape(0.8, 4)
        self.assertFalse(r_8um["can_replace_cowos_hbm3e_interposer"])
        self.assertEqual(r_8um["hbm3e_escaped_nets"], 343)
        self.assertEqual(r_8um["hbm3e_unrouted_nets"], 1407)
        self.assertTrue(r_cowos_r["can_replace_cowos_hbm3e_interposer"])
        self.assertTrue(r_cowos_l["can_replace_cowos_hbm3e_interposer"])
        self.assertTrue(r_8um["can_route_power_and_test_coupon"])

    def test_03_coupled_fvm_energy_conservation_and_blockage_survival(self) -> None:
        for key, spec in APPROACH_SPECS.items():
            nom = simulate_coupled_thermal_hydraulic_response(spec, 0.0, 0.0, 30.0)
            blk = simulate_coupled_thermal_hydraulic_response(spec, 0.90, 0.0, 30.0)
            self.assertLess(nom["energy_balance_rel_error"], 1e-12, msg=f"Energy error too high in {key} nominal")
            self.assertLess(blk["energy_balance_rel_error"], 1e-12, msg=f"Energy error too high in {key} blocked")

        m1_blk = simulate_coupled_thermal_hydraulic_response(APPROACH_SPECS["M1_COMMERCIAL_FIRST"], 0.90, 0.0, 30.0)
        m2_blk = simulate_coupled_thermal_hydraulic_response(APPROACH_SPECS["M2_HYBRID_CNC_CMC"], 0.90, 0.0, 30.0)
        m0_ctrl_blk = simulate_coupled_thermal_hydraulic_response(APPROACH_SPECS["M0_MATCHED_075_CONTROL"], 0.90, 0.0, 30.0)
        self.assertFalse(m1_blk["thermal_survived_95c"])
        self.assertTrue(m2_blk["thermal_survived_95c"])
        self.assertTrue(m0_ctrl_blk["thermal_survived_95c"])

    def test_04_corrosion_and_cte_constitutive_falsifiers(self) -> None:
        unshrouded = dataclasses.replace(
            APPROACH_SPECS["M2_HYBRID_CNC_CMC"],
            grounded_outer_shroud=False,
            wetted_dc_bias_v=0.80,
            parylene_c_thickness_um=0.0,
        )
        c_bad = evaluate_corrosion_and_dielectric_safety(unshrouded)
        c_good = evaluate_corrosion_and_dielectric_safety(APPROACH_SPECS["M2_HYBRID_CNC_CMC"])
        self.assertFalse(c_bad["passes_corrosion_and_leakage_gate"])
        self.assertGreater(c_bad["anodic_corrosion_rate_um_yr"], 250.0)
        self.assertTrue(c_good["passes_corrosion_and_leakage_gate"])

        unslotted = dataclasses.replace(
            APPROACH_SPECS["M2_HYBRID_CNC_CMC"],
            has_cmc_bridge=False,
            kerf_slot_pitch_mm=45.0,
            bond_shear_thickness_mm=0.050,
        )
        cte_bad = evaluate_cte_fatigue_life(unslotted)
        cte_good = evaluate_cte_fatigue_life(APPROACH_SPECS["M2_HYBRID_CNC_CMC"])
        self.assertFalse(cte_bad["passes_5000_cycle_gate"])
        self.assertLess(cte_bad["coffin_manson_cycles_to_failure"], 50)
        self.assertTrue(cte_good["passes_5000_cycle_gate"])
        self.assertGreater(cte_good["coffin_manson_cycles_to_failure"], 15000)

    def test_05_pinch_bounded_med_cutoff_below_65c(self) -> None:
        m40 = compute_pinch_bounded_med_distillate(40.0)
        m55 = compute_pinch_bounded_med_distillate(55.0)
        m69 = compute_pinch_bounded_med_distillate(69.0)
        m85 = compute_pinch_bounded_med_distillate(85.0)
        self.assertEqual(m40["distillate_produced_l_per_kwh"], 0.0)
        self.assertEqual(m55["distillate_produced_l_per_kwh"], 0.0)
        self.assertGreater(m69["distillate_produced_l_per_kwh"], 2.0)
        self.assertGreater(m85["distillate_produced_l_per_kwh"], m69["distillate_produced_l_per_kwh"])

    def test_06_bom_sourcing_and_cad_deliverable_integrity(self) -> None:
        bom = export_bom_and_supplier_files(ROOT)
        for app_id, spec in APPROACH_SPECS.items():
            t = bom["approach_cost_totals"][app_id]
            self.assertAlmostEqual(t["sourced_catalog_bom_usd"], spec.sourced_catalog_bom_usd, places=2)
            self.assertAlmostEqual(t["estimated_custom_fab_usd"], spec.estimated_custom_fab_usd, places=2)

        step_cp = (ROOT / "cad_and_drawings" / "mif_pws_v2_hybrid_coldplate.step").read_text(encoding="utf-8")
        self.assertIn("ISO-10303-21;", step_cp)
        self.assertIn("CH_59_HEADER_B_MINUS_X_MAX", step_cp)
        dxf_txt = (ROOT / "cad_and_drawings" / "mif_pws_v2_machining_drawing.dxf").read_text(encoding="utf-8")
        self.assertIn("MICROCHANNELS_60X_075PITCH", dxf_txt)
        self.assertIn("KERF_SLOTS_8X8_5625PITCH", dxf_txt)

    def test_07_ed25519_signature_and_10_of_10_falsifiers(self) -> None:
        ev = generate_master_evidence(ROOT)
        falsifiers = ev["independent_falsification_battery"]
        self.assertEqual(len(falsifiers), 10)
        for f in falsifiers:
            self.assertTrue(f["passed"], msg=f"Falsifier {f['falsifier_id']} failed")

        sig_block = ev["cryptographic_witness_signature"]
        body_copy = {k: v for k, v in ev.items() if k != "cryptographic_witness_signature"}
        canonical_bytes = json.dumps(body_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
        pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(sig_block["ed25519_public_key_hex"]))
        pub_key.verify(bytes.fromhex(sig_block["ed25519_signature_hex"]), canonical_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
