#!/usr/bin/env python3
"""OpenLine Frontier Research Qualification 001 — `openline_research_kernel.py`

The smallest effective consolidated frontier-research module (~180 LOC), retaining ONLY
the three mechanisms from OpenLine's 10 research documents and D.3 that measurably
improve verified discoveries per unit cost over the competent baseline:

1. `check_constraint_and_goodhart_gate` (Consolidated from `C-ULT v1.2` + `Strategist Rule 3` + `BUCSW`):
   - Computes exact binding constraint slack `S_k = Capacity_k - Demand` (identifying `BOOM`,
     `CRUNCH`, or `CRASH_OR_CLAMPED` regimes) and enforces the Goodhart / Zero-Oracle Gate (`R_g`),
     refusing label leakage, self-certification, or uncalibrated proxy optimization before search.
2. `verify_causal_isomorphism` (Consolidated from `GameChg Step 5` + `SEM Step 2 PRI` + `TW Pre-Mortem`):
   - Replaces `GameChg`'s hardcoded regex templates and `SEM`'s uncalibrated `E(t)` formula with an
     executable two-gate test:
     (a) Operator & Conservation Bijection: verifies that source and target domains share the same
         mathematical operator family, measurable variables, timescale alignment, and conservation bounds.
     (b) Quantitative Perturbation & Permutation Robustness (`PRI`): verifies that empirical correlation
         or intervention contrast survives sign/parameter perturbation and exceeds the 99th percentile
         of `n_permutations` shuffled null trials (`z_score >= 2.58`). Otherwise rejects as
         `STRUCTURAL_RHYME_ONLY_REJECTED`.
3. `select_decisive_receipt_and_certify` (Consolidated from `Parathinker` "Missing Receipt" +
   `Epiphany Criterion Stage 2/3` [with Stage 1 mandatory kappa-spike removed] + `D.3 Economic Gate`):
   - Selects the single minimum-cost discriminating experiment (`Missing Receipt`) that maximizes
     expected hypothesis separation per unit cost (`info_gain / cost`).
   - Certifies a candidate discovery or capability ONLY if post-intervention viability slack remains
     non-negative (`slack_after >= 0`) AND repeat-exposure cost/recovery improves (`reuse_cost < base_cost`
     and `recovery_ratio < 1.0`) without error blowout (`delta_error <= 0.0`).
   - Demotes `kappa` discontinuity spikes to a non-required descriptive telemetry field per Falsification
     Conditions 1, 2, and 4 of `epiphany_criterion_patch_v1.md`.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

FORBIDDEN_ORACLE_KEYS = frozenset({
    "gold_action", "gold_lang", "incident_next", "true_cause", "protected_answer", "oracle_label"
})


class ResearchGateRefused(RuntimeError):
    """Fail-closed refusal when Goodhart, oracle-leakage, STOP, or budget boundaries fail."""


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    return hashlib.sha256(obj if isinstance(obj, bytes) else canonical_json(obj)).hexdigest()


# ============================================================================
# 1. CONSTRAINT-SLACK & GOODHART GATE (From C-ULT v1.2 + Strategist Rule 3)
# ============================================================================

def check_constraint_and_goodhart_gate(
    capacities: Mapping[str, float],
    demand: float,
    *,
    goodhart_pressure_rg: float = 0.0,
    evaluator_independent: bool = True,
    task_envelope: Mapping[str, Any] | None = None,
    stopped: bool = False,
) -> dict[str, Any]:
    """Identifies the binding constraint (`min slack`), classifies operational regime,
    and blocks execution if `STOP` is active, oracle labels leak, or high Goodhart
    pressure (`R_g >= 0.7`) lacks independent evaluator custody."""
    if stopped:
        raise ResearchGateRefused("STOP_BINDING_HALT")
    if task_envelope and any(k in task_envelope for k in FORBIDDEN_ORACLE_KEYS):
        raise ResearchGateRefused("GOODHART_ORACLE_LABEL_LEAKAGE_REFUSED")
    if not capacities or not math.isfinite(float(demand)) or float(demand) < 0:
        raise ResearchGateRefused("INVALID_CAPACITY_OR_DEMAND")

    slacks: dict[str, float] = {}
    for k, cap in capacities.items():
        val = float(cap)
        if not math.isfinite(val):
            raise ResearchGateRefused(f"NONFINITE_CAPACITY:{k}")
        slacks[str(k)] = round(val - float(demand), 6)

    binding_wall = min(slacks, key=lambda k: slacks[k])
    min_slack = slacks[binding_wall]
    rel_slack = min_slack / max(1e-9, float(demand))

    if goodhart_pressure_rg >= 0.70 and not evaluator_independent:
        return {
            "status": "HOLD_HARDEN_EVALUATOR_FIRST",
            "binding_constraint": binding_wall,
            "min_slack": min_slack,
            "regime": "HIGH_GOODHART_UNPROTECTED",
            "action": "HARDEN_NEGATIVE_CONTROLS_AND_SEPARATE_EVALUATOR_BEFORE_OPTIMIZING",
            "falsifier": "Verify candidate on sealed holdout with zero oracle keys before promotion.",
        }

    if min_slack < 0:
        regime = "NEGATIVE_SLACK_CLAMPED"
    elif rel_slack < 0.15:
        regime = "LOW_SLACK_CRUNCH"
    else:
        regime = "HIGH_SLACK_VIABLE"

    return {
        "status": "PASS",
        "binding_constraint": binding_wall,
        "min_slack": min_slack,
        "relative_slack": round(rel_slack, 4),
        "all_slacks": slacks,
        "regime": regime,
        "action": f"RELIEVE_BINDING_WALL:{binding_wall}" if min_slack <= 0 else "OPERATE_WITHIN_SLACK",
        "falsifier": f"Perturb {binding_wall} vs non-binding stations; output must track min(capacities).",
    }


# ============================================================================
# 2. CAUSAL ISOMORPHISM & QUANTITATIVE PRI FALSIFIER (From GameChg + SEM Step 2)
# ============================================================================

def verify_causal_isomorphism(
    *,
    source_operator: str,
    target_operator: str,
    has_measurable_variables: bool,
    honors_conservation_laws: bool,
    timescale_aligned: bool,
    source_series: Sequence[float],
    target_series: Sequence[float],
    n_permutations: int = 200,
    seed: int = 20261114,
) -> dict[str, Any]:
    """Separates genuine cross-domain causal mechanisms from superficial metaphor (`structural rhyme`).

    Requires:
    1. Exact match of normalized mathematical operator family (`source_operator == target_operator`),
       measurable variables, conservation laws, and timescale alignment.
    2. Quantitative Perturbation Robustness Index (`PRI`): empirical correlation between source and
       target trajectories must exceed the 99th percentile of `n_permutations` shuffled null trials
       (`z_null >= 2.58`) AND survive 5% additive perturbation noise.
    """
    structural_checks = {
        "operator_match": (source_operator.strip().lower() == target_operator.strip().lower() and bool(source_operator.strip())),
        "measurable_variables": bool(has_measurable_variables),
        "conservation_honored": bool(honors_conservation_laws),
        "timescale_aligned": bool(timescale_aligned),
    }
    structural_score = sum(structural_checks.values())

    x = np.asarray(source_series, dtype=float)
    y = np.asarray(target_series, dtype=float)
    if len(x) != len(y) or len(x) < 6 or not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        raise ResearchGateRefused("INVALID_SERIES_FOR_ISOMORPHISM_TEST")

    if not all(structural_checks.values()):
        return {
            "disposition": "STRUCTURAL_RHYME_ONLY_REJECTED",
            "structural_checks": structural_checks,
            "structural_score": f"{structural_score}/4",
            "z_null": 0.0,
            "perturbed_retention": 0.0,
            "reason": "FAILED_STRUCTURAL_OPERATOR_OR_CONSERVATION_GATE",
        }

    x_std = (x - np.mean(x)) / max(1e-12, float(np.std(x)))
    y_std = (y - np.mean(y)) / max(1e-12, float(np.std(y)))
    obs_corr = abs(float(np.mean(x_std * y_std)))

    rng = np.random.default_rng(seed)
    null_corrs = np.zeros(n_permutations)
    for i in range(n_permutations):
        perm_y = rng.permutation(y_std)
        null_corrs[i] = abs(float(np.mean(x_std * perm_y)))

    null_mean = float(np.mean(null_corrs))
    null_std = max(1e-9, float(np.std(null_corrs)))
    z_null = (obs_corr - null_mean) / null_std
    q99_null = float(np.quantile(null_corrs, 0.99))

    # Perturbation robustness check (5% noise injection)
    noisy_y = y_std + rng.normal(0.0, 0.05, size=len(y_std))
    noisy_y = (noisy_y - np.mean(noisy_y)) / max(1e-12, float(np.std(noisy_y)))
    pert_corr = abs(float(np.mean(x_std * noisy_y)))

    passes_pri = (obs_corr > q99_null) and (z_null >= 2.58) and (pert_corr >= 0.70)
    return {
        "disposition": "VERIFIED_CAUSAL_ISOMORPHISM" if passes_pri else "STRUCTURAL_RHYME_ONLY_REJECTED",
        "structural_checks": structural_checks,
        "structural_score": f"{structural_score}/4",
        "observed_alignment": round(obs_corr, 4),
        "null_q99": round(q99_null, 4),
        "z_null": round(z_null, 3),
        "perturbed_retention": round(pert_corr, 4),
        "reason": "PASSED_OPERATOR_AND_PERMUTATION_NULL_GATE" if passes_pri else "FAILED_PERMUTATION_OR_PERTURBATION_GATE",
    }


# ============================================================================
# 3. DECISIVE RECEIPT & RECOVERY CERTIFIER (From Parathinker + Epiphany Stg 2/3 + D.3)
# ============================================================================

def select_decisive_receipt_and_certify(
    candidate_tests: Sequence[Mapping[str, Any]],
    *,
    viability_slack_after: float,
    error_before: float,
    error_after: float,
    recovery_steps_first_exposure: float,
    recovery_steps_repeat_exposure: float,
    creation_cost: float,
    baseline_cost_per_use: float,
    reuse_cost_per_use: float,
    expected_uses: int = 10,
    kappa_spike_observed: bool = False,
) -> dict[str, Any]:
    """1. Selects the Single Missing Decisive Receipt (`max expected_disambiguation / cost`).
    2. Evaluates Stage 2 (Survival Confirmation: `viability_slack_after >= 0` and no error blowout)
       and Stage 3 (Repeat-Exposure Certification: `recovery_steps_repeat < recovery_steps_first`
       and positive net economic savings across `expected_uses`), WITHOUT requiring `kappa_spike_observed`.
    """
    if not candidate_tests:
        raise ResearchGateRefused("NO_CANDIDATE_DISCRIMINATING_TESTS")

    ranked = sorted(
        candidate_tests,
        key=lambda t: float(t["expected_disambiguation"]) / max(1e-6, float(t["cost"])),
        reverse=True,
    )
    decisive_receipt = dict(ranked[0])
    decisive_receipt["efficiency_ratio"] = round(
        float(decisive_receipt["expected_disambiguation"]) / max(1e-6, float(decisive_receipt["cost"])), 4
    )

    delta_error = float(error_after) - float(error_before)
    stage2_confirmed = (float(viability_slack_after) >= 0.0) and (delta_error <= 0.02)
    recovery_ratio = float(recovery_steps_repeat_exposure) / max(1e-9, float(recovery_steps_first_exposure))
    stage3_recovery_certified = stage2_confirmed and (recovery_ratio < 0.85) and (delta_error <= 0.0)

    marginal_saving = float(baseline_cost_per_use) - float(reuse_cost_per_use)
    if marginal_saving <= 0:
        break_even_uses = None
        net_savings_at_horizon = -float(creation_cost) + float(expected_uses) * marginal_saving
        economically_qualified = False
    else:
        break_even_uses = int(math.ceil(float(creation_cost) / marginal_saving))
        net_savings_at_horizon = float(expected_uses) * marginal_saving - float(creation_cost)
        economically_qualified = (net_savings_at_horizon > 0.0)

    certified = stage2_confirmed and stage3_recovery_certified and economically_qualified
    return {
        "decisive_missing_receipt": decisive_receipt,
        "stage1_kappa_spike_observed": bool(kappa_spike_observed),
        "stage1_kappa_required_for_certification": False,
        "stage2_viability_confirmed": stage2_confirmed,
        "stage3_recovery_certified": stage3_recovery_certified,
        "recovery_step_ratio": round(recovery_ratio, 4),
        "delta_error": round(delta_error, 4),
        "economic_gate": {
            "creation_cost": creation_cost,
            "marginal_saving_per_use": round(marginal_saving, 4),
            "break_even_uses_n_be": break_even_uses,
            "expected_uses": expected_uses,
            "net_savings_at_expected_uses": round(net_savings_at_horizon, 4),
            "economically_qualified": economically_qualified,
        },
        "final_disposition": (
            "ADOPT_CERTIFIED_DISCOVERY"
            if certified
            else ("PARK_ECONOMIC_PLATEAU" if (stage2_confirmed and not economically_qualified) else "REJECT_FAILED_CONFIRMATION_OR_RECOVERY")
        ),
    }
