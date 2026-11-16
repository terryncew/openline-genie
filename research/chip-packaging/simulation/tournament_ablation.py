#!/usr/bin/env python3
"""Independent diagnostic ablations of the tournament model.

Runs the author's tournament model on seven controlled variants: the
conventional design as configured, the conventional design given the same
cooling geometry as the proposed design, an existing direct-to-silicon
control, the proposed design as configured, and the proposed design with
its power-delivery and cost advantages removed one at a time and together.
It then runs one severe operating case for four of the variants, and
computes an algebraic parity check: what the proposed design's score
becomes when its assigned yield and amortized tooling cost are also
equalized with the conventional design.

These are parametric counterfactuals inside the author's model. They are
NOT independent hardware measurements, and they do not establish that any
of the modeled advantages exist in a real device.

Adapted for this public tree from the original independent ablation script
(see SOURCES.md for the original file and its SHA-256). The original read
the model from a frozen source archive; this version imports the same
module from the local tournament_model package, which is a verbatim copy
of that module. The arm definitions, the severe case, the parity
calculation, and the output format are unchanged.
"""
import hashlib
import json, sys, argparse
from pathlib import Path
from dataclasses import replace

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tournament_model.coupled_electro_thermo_wafer_sim import (
    RATCHET_ARMS,
    simulate_coupled_module_physics,
    evaluate_arm_across_scales_and_holdouts,
)

parser = argparse.ArgumentParser(
    description="Independent ablations of the tournament model in this tree"
)
parser.add_argument("--output", default="ablation_results.json")
args = parser.parse_args()

a = RATCHET_ARMS["A0_CONV_COWOS_COLDPLATE"]
a1 = RATCHET_ARMS["A1_CONV_DIRECT_TO_SI_PILLAR"]
g = RATCHET_ARMS["G2_V2_REPAIRED_MIF_PWS"]
control = {
    "A0_original": a,
    "A0_same_075_pitch_metal_geometry": replace(
        a, cooling_pitch_mm=0.75, counter_flow_interleaved=True,
        dual_independent_strainers=True, substrate_thickness_mm=4.0,
        substrate_k_xy_w_mk=395.0, substrate_k_z_w_mk=395.0),
    "A1_existing_direct_to_Si_075_pitch_control": replace(
        a1, cooling_pitch_mm=0.75, counter_flow_interleaved=True,
        dual_independent_strainers=True),
    "G2_original": g,
    "G2_if_PDN_is_038_milliohm": replace(g, pdn_resistance_mohm=0.380),
    "G2_if_die_pkg_cost_equal_A0": replace(
        g, silicon_die_cost_per_module_usd=a.silicon_die_cost_per_module_usd,
        packaging_and_substrate_bom_usd=a.packaging_and_substrate_bom_usd),
    "G2_if_both_cost_and_PDN_not_improved": replace(
        g, pdn_resistance_mohm=0.380,
        silicon_die_cost_per_module_usd=a.silicon_die_cost_per_module_usd,
        packaging_and_substrate_bom_usd=a.packaging_and_substrate_bom_usd),
}
res = {}
for k, arm in control.items():
    r = evaluate_arm_across_scales_and_holdouts(arm)
    s = r["by_scale"]["N2500"]
    res[k] = {
        "tflops_per_5yr_dollar_N2500": s["verified_tflops_per_lifecycle_dollar"],
        "model_lifecycle_5yr_usd": s["lifecycle_5yr_cost_per_module_usd"],
        "survival_percent": r["holdout_survival_rate_pct"],
        "mean_peak_tj_c": r["mean_peak_tj_c"],
        "pdn_loss_w": r["pdn_joule_loss_w"],
        "mfg_yield_model_assigned": r["manufacturing_compound_yield"],
        "heat_conservation_max_relative_error": r["max_energy_rel_error"],
    }
    print(k, json.dumps(res[k]), flush=True)

# The yield and cost figures in the model are assigned by flags, not
# measured from a wafer process. The score therefore reflects the model's
# assumptions, not a physical result.
base = res["A0_original"]["tflops_per_5yr_dollar_N2500"]
for item in res.values():
    item["ratio_vs_original_A0"] = round(
        item["tflops_per_5yr_dollar_N2500"] / base, 4)

# Single severe case selected in the original suite: sensitivity to a
# stronger conventional geometry.
severe = [0.95, 0.12, 0.84, 0.10]
sev = {}
for k in ["A0_original", "A0_same_075_pitch_metal_geometry",
          "A1_existing_direct_to_Si_075_pitch_control", "G2_original"]:
    r = simulate_coupled_module_physics(control[k], severe, 0.35, 0.05, 1.28, 35.0)
    sev[k] = {key: r[key] for key in [
        "peak_tj_c", "thermal_survived", "overall_survived",
        "effective_compute_fraction", "relative_energy_error"]}

module_sha = hashlib.sha256(
    (ROOT / "tournament_model" / "coupled_electro_thermo_wafer_sim.py")
    .read_bytes()).hexdigest()
out = {
    "schema": "openline.civilization_ratchet_003.gpt6_independent_ablation.v1",
    "claim": "Parametric ablations of authors own model; no hardware validation, no independent constitutive model",
    # The archive the tournament module was copied from (see SOURCES.md).
    "source_zip_sha256": "72802ddb9237cab72b3c219f31b2d3ac38684ed770b629b090b547957c3f8beb",
    "source_module_sha256": module_sha,
    "controls": res, "severe_case": sev,
    "null_laws": [
        "No measured wafer yield. Author assigns 0.945 yield to postmetrology+interposer-deletion flags, otherwise 0.865 for A0.",
        "PDN R and silicon die price are arm parameters, not outcomes of solved circuit packaging layout.",
        "Physical 3D coolant/electrical compatibility, fine-pitch HBM links, liquid sealing and industrial process yield unverified.",
    ],
}
# Algebraic yield/NRE parity after the same-model PDN and prices are equalized.
g_both = res["G2_if_both_cost_and_PDN_not_improved"]
price_equalized = (a.silicon_die_cost_per_module_usd
                   + a.packaging_and_substrate_bom_usd
                   + g.cooling_hardware_bom_usd)
extra_yield_cost = price_equalized * (1 / 0.865 - 1 / 0.945)
equalized_cost = g_both["model_lifecycle_5yr_usd"] + extra_yield_cost
equalized_score = (g_both["tflops_per_5yr_dollar_N2500"]
                   * g_both["model_lifecycle_5yr_usd"] / equalized_cost)
extra_nre = (a.mask_or_interposer_nre_usd - 0.30 * g.tool_capex_usd) / 2500
equalized_cost_and_nre = equalized_cost + extra_nre
equalized_score_and_nre = (g_both["tflops_per_5yr_dollar_N2500"]
                           * g_both["model_lifecycle_5yr_usd"]
                           / equalized_cost_and_nre)
out["algebraic_assumption_parity"] = {
    "equalize_yield_only_score": round(equalized_score, 6),
    "equalize_die_pkg_PDN_yield_NRE_score": round(equalized_score_and_nre, 6),
    "matched_channel_conventional_score":
        res["A0_same_075_pitch_metal_geometry"]["tflops_per_5yr_dollar_N2500"],
    "relative_gain_after_parity_percent": round(
        100 * (equalized_score_and_nre
               / res["A0_same_075_pitch_metal_geometry"]
               ["tflops_per_5yr_dollar_N2500"] - 1), 3),
    "note": "Algebraic counterfactual only; equalizing putative benefits does not by itself establish their impossibility.",
}
Path(args.output).write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
print("WROTE", args.output)
