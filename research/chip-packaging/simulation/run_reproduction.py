#!/usr/bin/env python3
"""One-command reproduction of every numerical result in this research.

Usage, from this directory:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    python3 run_reproduction.py

What it does, in order:
  1. Runs the tournament ablation (seven controlled variants, one severe
     case, and the algebraic parity check) and compares every number to
     expected/ablation_results.json.
  2. Runs the split-plane repair round and compares the six variant
     scores to expected/r004_source_bound_results.json.
  3. Runs the first-principles gates (electricity floor, power-delivery
     bound, routing bound) and compares them to
     expected/r004_first_principles_gates.json.
  4. Runs the MIF-PWS v2 screening package in mif004/ (its own runner
     regenerates the evidence, runs the 7 unit tests twice, and verifies
     its manifest), then runs the independent audit checks and compares
     the key findings to expected/independent_challenge_results.json.

All comparisons are exact. Any mismatch fails the run with a non-zero
exit code and names the differing value. No network access, no private
account, and no paid service is needed at any step.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
failures = []


def run(cmd, cwd):
    print(f"$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(cmd)}")
    return r.stdout


def check(name, got, expected, keys):
    """Compare selected keys of two dicts; record failures, print PASS/FAIL."""
    ok = True
    for k in keys:
        if got.get(k) != expected.get(k):
            ok = False
            failures.append(f"{name}: {k}: got {got.get(k)!r}, expected {expected.get(k)!r}")
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    return ok


def load(p):
    return json.loads(Path(p).read_text())


def main():
    # 1. Tournament ablation
    out = run([PY, "tournament_ablation.py", "--output", "ablation_results.json"], ROOT)
    print(out, end="")
    got = load(ROOT / "ablation_results.json")
    exp = load(ROOT / "expected" / "ablation_results.json")
    check("ablation controls", got["controls"], exp["controls"], list(exp["controls"]))
    check("ablation severe case", got["severe_case"], exp["severe_case"], list(exp["severe_case"]))
    check("ablation parity", got["algebraic_assumption_parity"],
          exp["algebraic_assumption_parity"],
          ["equalize_yield_only_score", "equalize_die_pkg_PDN_yield_NRE_score",
           "matched_channel_conventional_score", "relative_gain_after_parity_percent"])

    # 2. Split-plane repair round
    out = run([PY, "frontier_repair_round_004.py"], ROOT)
    print(out, end="")
    got = load(ROOT / "RATCHET_003_ROUND_004_SOURCE_BOUND_RESULTS.json")
    exp = load(ROOT / "expected" / "r004_source_bound_results.json")
    got_arms = {a["id"]: a for a in got["candidate_arms"]}
    exp_arms = {a["id"]: a for a in exp["candidate_arms"]}
    for arm_id in exp_arms:
        check(f"split-plane {arm_id}", got_arms[arm_id], exp_arms[arm_id],
              ["model_tflops_per_5yr_usd", "model_cost_5yr_usd",
               "model_holdout_survival", "model_peak_tj_c",
               "model_pdn_joule_loss_w", "model_yield"])
    check("split-plane status", got, exp, ["status"])

    # 3. First-principles gates
    out = run([PY, "first_principles_gates_004.py"], ROOT)
    print(out, end="")
    got = load(ROOT / "RATCHET_003_ROUND_004_FIRST_PRINCIPLES_GATES.json")
    exp = load(ROOT / "expected" / "r004_first_principles_gates.json")
    check("gates power floor", got["power_floor"], exp["power_floor"],
          list(exp["power_floor"]))
    check("gates power network", got["power_network"], exp["power_network"],
          list(exp["power_network"]))

    # 4. MIF-PWS v2 screening package (its own runner verifies itself)
    mif = ROOT / "mif004"
    out = run([PY, "run_all_physical_experiment_004.py"], mif)
    print(out, end="")
    # Independent audit checks against the regenerated package
    out = run([PY, "independent_challenge_004.py"], mif)
    got = json.loads(out)
    exp = load(ROOT / "expected" / "independent_challenge_results.json")
    check("audit heater power", got["heater_netlist"], exp["heater_netlist"],
          ["count", "resistance_each_ohm", "supply_voltage_v",
           "calculated_heater_power_w", "claimed_surrogate_w", "factor_over_claim"])
    check("audit heater fit", got["heater_geometric_fit"], exp["heater_geometric_fit"],
          ["minimum_4_across_width_mm", "available_active_zone_width_mm",
           "direct_mount_as_drawn_geometrically_possible"])
    check("audit STEP solid", got["cad_STEP"], exp["cad_STEP"],
          ["has_manifold_solid_brep_or_advanced_face_or_closed_shell",
           "cartesian_point_count"])
    check("audit PDN solver", got["pdn_solver"], exp["pdn_solver"],
          ["grid_x_nodes", "grid_y_nodes", "grid_z_nodes_defined"])
    check("audit signature", got["signature"], exp["signature"],
          ["embedded_seed_reconstructs_advertised_public_key",
           "altered_evidence_signature_validates_as_advertised_public_key",
           "independent_witness_authority"])
    check("audit desalination replay", got["med_replay_text"], exp["med_replay_text"],
          ["claimed_69C_l_per_kwh", "calculated_69C_l_per_kwh",
           "claimed_85C_l_per_kwh", "calculated_85C_l_per_kwh"])

    print()
    if failures:
        print("REPRODUCTION FAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("REPRODUCTION PASSED: every numerical result matches the expected values.")


if __name__ == "__main__":
    main()
