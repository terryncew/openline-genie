#!/usr/bin/env python3
"""OpenLine 011 — Guarded Executable Proof-Obligation Gate (`core/rgpo_obligation_gate.py`).

Reconciles Argon 011 with GPT-6's Independent Cross-Stack Audit:
1. Recursive `enforce_zero_oracle(payload)` rejects oracle keys across nested mappings,
   lists, and tuples with cycle detection.
2. Explicitly quarantines the prior 12/12 general autonomous invention claim
   (`RGPO_011_GENERAL_INVENTION_CLAIM = "HOLD_CONSTRUCTED_BENCHMARK_CONTAMINATED"`),
   recording that a static 7-flag dictionary passed the constructed benchmark.
3. Provides `ExecutableProofObligationGate`: evaluates real executable candidate callables
   against externally held executable proof obligations with a mandatory non-vacuous
   nominal coverage floor (`min_nominal_coverage >= 0.80`), rejecting both static flag
   dictionaries (`NOT_CALLABLE_OR_EXECUTABLE`) and `always-ABSTAIN` (`VACUOUS_COVERAGE_BELOW_FLOOR`).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any

RGPO_011_GENERAL_INVENTION_CLAIM = "HOLD_CONSTRUCTED_BENCHMARK_CONTAMINATED"
RGPO_NARROW_PRACTICE_STATUS = "ADOPT_GUARDED_EXECUTABLE_OBLIGATION_GATE"

FORBIDDEN_ORACLE_KEYS = frozenset({
    "ground_truth",
    "ground_truth_scale_um",
    "ground_truth_rf_1e13",
    "hidden_holdout_target",
    "oracle_label",
    "oracle_answer",
    "true_fouling_class",
    "evaluator_secret",
    "private_holdout_verdict",
    "sealed_answer",
})


class RGPOPolicyViolation(RuntimeError):
    """Raised when an input, candidate, or obligation violates zero-oracle or custody rules."""


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    if isinstance(obj, (bytes, bytearray)):
        return hashlib.sha256(obj).hexdigest()
    if isinstance(obj, str):
        return hashlib.sha256(obj.encode("utf-8")).hexdigest()
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def enforce_zero_oracle(payload: Any) -> None:
    """Reject known oracle field keys through mappings AND nested arrays/tuples.

    Includes cycle detection (`seen: set[int]`) so cyclic containers cannot cause infinite recursion.
    """
    seen: set[int] = set()

    def walk(value: Any) -> None:
        if not isinstance(value, (Mapping, list, tuple)):
            return
        identity = id(value)
        if identity in seen:
            return
        seen.add(identity)
        if isinstance(value, Mapping):
            for key, item in value.items():
                if isinstance(key, str) and key in FORBIDDEN_ORACLE_KEYS:
                    raise RGPOPolicyViolation(f"ZERO_ORACLE_VIOLATION:{key}")
                walk(item)
        else:
            for item in value:
                walk(item)

    walk(payload)


@dataclass(frozen=True)
class ExecutableProofObligation:
    obligation_id: str
    category: str  # "nominal_competence" | "boundary_invariant" | "adversarial_fail_closed"
    description: str
    test_vectors: tuple[dict[str, Any], ...]
    verifier_fn: Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]


@dataclass
class ObligationGateReport:
    task_id: str
    candidate_id: str
    is_executable_callable: bool
    nominal_total: int
    nominal_passed: int
    nominal_coverage_ratio: float
    min_nominal_coverage_floor: float
    meets_nominal_coverage_floor: bool
    boundary_obligations_total: int
    boundary_obligations_passed: int
    false_acceptances_on_hazards: int
    discovered_missing_obligations: list[str] = field(default_factory=list)
    independently_accepted: bool = False
    rejection_reason: str | None = None
    obligation_details: list[dict[str, Any]] = field(default_factory=list)
    report_sha256: str = ""


class ExecutableProofObligationGate:
    """Evaluates executable candidate functions against externally held proof obligations."""

    def __init__(self, min_nominal_coverage: float = 0.80) -> None:
        if not (0.50 <= min_nominal_coverage <= 1.0):
            raise ValueError("min_nominal_coverage must be in [0.50, 1.0]")
        self.min_nominal_coverage = float(min_nominal_coverage)

    def evaluate_candidate(
        self,
        task_id: str,
        candidate_id: str,
        candidate_fn: Any,
        obligations: Sequence[ExecutableProofObligation],
    ) -> ObligationGateReport:
        if isinstance(candidate_fn, Mapping) or not callable(candidate_fn):
            rep = ObligationGateReport(
                task_id=task_id,
                candidate_id=candidate_id,
                is_executable_callable=False,
                nominal_total=0,
                nominal_passed=0,
                nominal_coverage_ratio=0.0,
                min_nominal_coverage_floor=self.min_nominal_coverage,
                meets_nominal_coverage_floor=False,
                boundary_obligations_total=len(obligations),
                boundary_obligations_passed=0,
                false_acceptances_on_hazards=0,
                independently_accepted=False,
                rejection_reason="REJECTED_NON_EXECUTABLE_STATIC_OBJECT",
            )
            rep.report_sha256 = sha256_hex(rep.__dict__)
            return rep

        nominal_total = 0
        nominal_passed = 0
        boundary_total = 0
        boundary_passed = 0
        false_accepts = 0
        missing_obligations: list[str] = []
        details: list[dict[str, Any]] = []

        for ob in obligations:
            ob_passed = True
            ob_failures: list[str] = []
            for vec in ob.test_vectors:
                enforce_zero_oracle(vec)
                try:
                    out = candidate_fn(dict(vec))
                except Exception as exc:
                    out = {"status": "ERROR", "error": str(exc)}
                if not isinstance(out, Mapping):
                    ob_passed = False
                    ob_failures.append("non_mapping_output")
                    continue
                enforce_zero_oracle(out)
                ok, reason = ob.verifier_fn(vec, dict(out))
                if ob.category == "nominal_competence":
                    nominal_total += 1
                    if ok and out.get("status") == "COMMIT_VALID":
                        nominal_passed += 1
                    else:
                        ob_passed = False
                        ob_failures.append(reason)
                else:
                    if not ok:
                        ob_passed = False
                        ob_failures.append(reason)
                        if out.get("status") == "COMMIT_VALID":
                            false_accepts += 1

            if ob.category != "nominal_competence":
                boundary_total += 1
                if ob_passed:
                    boundary_passed += 1
                else:
                    missing_obligations.append(ob.obligation_id)

            details.append({
                "obligation_id": ob.obligation_id,
                "category": ob.category,
                "passed": ob_passed,
                "failures": ob_failures,
            })

        cov_ratio = (nominal_passed / nominal_total) if nominal_total > 0 else 0.0
        meets_floor = cov_ratio >= self.min_nominal_coverage
        accepted = bool(
            meets_floor
            and boundary_passed == boundary_total
            and false_accepts == 0
        )
        rej = None
        if not meets_floor:
            rej = f"REJECTED_VACUOUS_OR_LOW_NOMINAL_COVERAGE:{cov_ratio:.2f}<{self.min_nominal_coverage:.2f}"
        elif false_accepts > 0:
            rej = f"REJECTED_FALSE_ACCEPTANCE_ON_HAZARD:{false_accepts}"
        elif boundary_passed < boundary_total:
            rej = f"REJECTED_UNMET_PROOF_OBLIGATIONS:{','.join(missing_obligations)}"

        rep = ObligationGateReport(
            task_id=task_id,
            candidate_id=candidate_id,
            is_executable_callable=True,
            nominal_total=nominal_total,
            nominal_passed=nominal_passed,
            nominal_coverage_ratio=round(cov_ratio, 4),
            min_nominal_coverage_floor=self.min_nominal_coverage,
            meets_nominal_coverage_floor=meets_floor,
            boundary_obligations_total=boundary_total,
            boundary_obligations_passed=boundary_passed,
            false_acceptances_on_hazards=false_accepts,
            discovered_missing_obligations=missing_obligations,
            independently_accepted=accepted,
            rejection_reason=rej,
            obligation_details=details,
        )
        rep.report_sha256 = sha256_hex({
            "task_id": rep.task_id,
            "candidate_id": rep.candidate_id,
            "accepted": rep.independently_accepted,
            "nominal_coverage": rep.nominal_coverage_ratio,
            "boundary_passed": rep.boundary_obligations_passed,
            "false_accepts": rep.false_acceptances_on_hazards,
        })
        return rep


def build_independent_unseen_executable_benchmark() -> list[dict[str, Any]]:
    """Constructs 4 unseen executable engineering tasks with independent verifier functions."""
    tasks: list[dict[str, Any]] = []

    # Task U1: Temperature-normalized membrane specific flux with reference conductivity obligation
    ob_u1_nom = ExecutableProofObligation(
        obligation_id="OB-U1-NOMINAL-FLUX",
        category="nominal_competence",
        description="Compute viscosity-corrected specific flux on valid dual-reference telemetry",
        test_vectors=(
            {"flow_lpm": 4.2, "pressure_psi": 150.0, "osmotic_psi": 30.0, "temp_c": 25.0, "ref_cond_ok": True},
            {"flow_lpm": 3.8, "pressure_psi": 145.0, "osmotic_psi": 25.0, "temp_c": 20.0, "ref_cond_ok": True},
            {"flow_lpm": 4.5, "pressure_psi": 160.0, "osmotic_psi": 30.0, "temp_c": 30.0, "ref_cond_ok": True},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "COMMIT_VALID"
            and isinstance(out.get("specific_flux"), (int, float))
            and math.isfinite(float(out["specific_flux"]))
            and abs(
                float(out["specific_flux"])
                - (vec["flow_lpm"] / (vec["pressure_psi"] - vec["osmotic_psi"]))
                * math.exp(-0.024 * (vec["temp_c"] - 25.0))
            ) < 1e-4,
            "specific_flux_mismatch",
        ),
    )
    ob_u1_bound = ExecutableProofObligation(
        obligation_id="OB-U1-MISSING-REF-AND-NONPOSITIVE-FLOW",
        category="adversarial_fail_closed",
        description="Must abstain/reject when reference conductivity is missing or flow <= 0",
        test_vectors=(
            {"flow_lpm": 4.0, "pressure_psi": 150.0, "osmotic_psi": 30.0, "temp_c": 25.0, "ref_cond_ok": False},
            {"flow_lpm": -0.5, "pressure_psi": 150.0, "osmotic_psi": 30.0, "temp_c": 25.0, "ref_cond_ok": True},
            {"flow_lpm": 4.0, "pressure_psi": 25.0, "osmotic_psi": 30.0, "temp_c": 25.0, "ref_cond_ok": True},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") in ("ABSTAIN_UNVERIFIED", "REJECT_INVALID"),
            "hazard_falsely_committed",
        ),
    )
    tasks.append({"task_id": "U1_MEMBRANE_VISCOSITY_AND_REFERENCE_GATE", "obligations": [ob_u1_nom, ob_u1_bound]})

    # Task U2: Cold-chain priority slack allocation under solar dropout
    ob_u2_nom = ExecutableProofObligation(
        obligation_id="OB-U2-NOMINAL-ALLOCATION",
        category="nominal_competence",
        description="Allocate solar + PCM thermal reserve to preserve 100% critical vaccine load",
        test_vectors=(
            {"solar_kw": 3.5, "vaccine_kw": 1.2, "deferrable_kw": 1.8, "pcm_soc": 0.85, "sensor_epoch_valid": True},
            {"solar_kw": 1.5, "vaccine_kw": 1.2, "deferrable_kw": 1.5, "pcm_soc": 0.60, "sensor_epoch_valid": True},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "COMMIT_VALID"
            and float(out.get("vaccine_allocated_kw", 0.0)) >= vec["vaccine_kw"] - 1e-6
            and float(out.get("deferrable_allocated_kw", -1.0)) >= 0.0,
            "vaccine_shortfall",
        ),
    )
    ob_u2_bound = ExecutableProofObligation(
        obligation_id="OB-U2-SOLAR-DROPOUT-SHED-AND-EPOCH",
        category="boundary_invariant",
        description="Shed deferrable load completely when solar < vaccine_kw and reject stale sensor epoch",
        test_vectors=(
            {"solar_kw": 0.4, "vaccine_kw": 1.2, "deferrable_kw": 2.0, "pcm_soc": 0.50, "sensor_epoch_valid": True},
            {"solar_kw": 3.0, "vaccine_kw": 1.2, "deferrable_kw": 1.0, "pcm_soc": 0.80, "sensor_epoch_valid": False},
        ),
        verifier_fn=lambda vec, out: (
            (out.get("status") == "COMMIT_VALID" and float(out.get("deferrable_allocated_kw", 1.0)) == 0.0)
            if vec["sensor_epoch_valid"]
            else (out.get("status") in ("ABSTAIN_UNVERIFIED", "REJECT_INVALID")),
            "failed_load_shed_or_epoch_gate",
        ),
    )
    tasks.append({"task_id": "U2_COLD_CHAIN_PRIORITY_SLACK_GATE", "obligations": [ob_u2_nom, ob_u2_bound]})

    # Task U3: Multi-hop receiver mandate intersection under clock skew and replay
    ob_u3_nom = ExecutableProofObligation(
        obligation_id="OB-U3-NOMINAL-MANDATE",
        category="nominal_competence",
        description="Compute intersection of delegator and receiver budget/scope mandates",
        test_vectors=(
            {"delegator_cap": 250.0, "receiver_cap": 180.0, "requested": 150.0, "skew_s": 5.0, "replayed": False},
            {"delegator_cap": 100.0, "receiver_cap": 120.0, "requested": 95.0, "skew_s": 2.0, "replayed": False},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "COMMIT_VALID"
            and float(out.get("effective_cap", -1.0)) == min(vec["delegator_cap"], vec["receiver_cap"]),
            "mandate_intersection_mismatch",
        ),
    )
    ob_u3_bound = ExecutableProofObligation(
        obligation_id="OB-U3-REPLAY-AND-CLOCK-SKEW",
        category="adversarial_fail_closed",
        description="Fail closed on replay, clock skew > 30s, or request exceeding intersection cap",
        test_vectors=(
            {"delegator_cap": 250.0, "receiver_cap": 180.0, "requested": 200.0, "skew_s": 5.0, "replayed": False},
            {"delegator_cap": 250.0, "receiver_cap": 180.0, "requested": 100.0, "skew_s": 45.0, "replayed": False},
            {"delegator_cap": 250.0, "receiver_cap": 180.0, "requested": 100.0, "skew_s": 5.0, "replayed": True},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "REJECT_INVALID",
            "permitted_unauthorized_or_replayed_mandate",
        ),
    )
    tasks.append({"task_id": "U3_RECEIVER_MANDATE_INTERSECTION_GATE", "obligations": [ob_u3_nom, ob_u3_bound]})

    # Task U4: STS3215 actuator bus delay & voltage sag torque clamping
    ob_u4_nom = ExecutableProofObligation(
        obligation_id="OB-U4-NOMINAL-TORQUE",
        category="nominal_competence",
        description="Compute phase-lead damped torque within voltage-derated STS3215 stall envelope",
        test_vectors=(
            {"q_err": 0.25, "dq": -0.10, "voltage_v": 7.4, "delay_ms": 12.0, "estop": False},
            {"q_err": -0.20, "dq": 0.05, "voltage_v": 7.0, "delay_ms": 15.0, "estop": False},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "COMMIT_VALID"
            and abs(float(out.get("torque_nm", 99.0))) <= 2.95 * (vec["voltage_v"] / 7.4),
            "torque_outside_safe_envelope",
        ),
    )
    ob_u4_bound = ExecutableProofObligation(
        obligation_id="OB-U4-VOLTAGE-SAG-AND-ESTOP",
        category="adversarial_fail_closed",
        description="Reject command when E-STOP is active or battery voltage sags below 5.5V brownout floor",
        test_vectors=(
            {"q_err": 0.80, "dq": 0.0, "voltage_v": 7.4, "delay_ms": 12.0, "estop": True},
            {"q_err": 0.80, "dq": 0.0, "voltage_v": 5.1, "delay_ms": 12.0, "estop": False},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "REJECT_INVALID" and float(out.get("torque_nm", -1.0)) == 0.0,
            "actuated_during_estop_or_brownout",
        ),
    )
    tasks.append({"task_id": "U4_STS3215_DELAY_AND_BROWNOUT_GATE", "obligations": [ob_u4_nom, ob_u4_bound]})

    return tasks


def run_loop_b_independent_qualification() -> dict[str, Any]:
    """Runs the 4-arm comparison on the 4 unseen executable tasks."""
    gate = ExecutableProofObligationGate(min_nominal_coverage=0.80)
    tasks = build_independent_unseen_executable_benchmark()

    # Arm 1: Static 7-flag dictionary shortcut (passed the prior constructed 12/12 benchmark)
    static_7_flag_shortcut = {
        "refine_consistent": True,
        "non_circular_evidence": True,
        "physical_units_checked": True,
        "confounder_2x2_identifiable": True,
        "abstain_when_underdetermined": True,
        "fail_closed_on_corrupt_input": True,
        "valid_nominal_output": True,
    }

    # Arm 2: Always-ABSTAIN candidate
    def always_abstain_fn(vec: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ABSTAIN_UNVERIFIED"}

    # Arm 3: Naive nominal candidate (passes standard unit tests, fails boundary/adversarial proof obligations)
    def make_naive_candidate(task_id: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        if task_id == "U1_MEMBRANE_VISCOSITY_AND_REFERENCE_GATE":
            return lambda v: {
                "status": "COMMIT_VALID",
                "specific_flux": (v["flow_lpm"] / max(1.0, v["pressure_psi"] - v["osmotic_psi"]))
                * math.exp(-0.024 * (v["temp_c"] - 25.0)),
            }
        if task_id == "U2_COLD_CHAIN_PRIORITY_SLACK_GATE":
            return lambda v: {
                "status": "COMMIT_VALID",
                "vaccine_allocated_kw": v["vaccine_kw"],
                "deferrable_allocated_kw": max(0.0, v["solar_kw"] - v["vaccine_kw"]),
            }
        if task_id == "U3_RECEIVER_MANDATE_INTERSECTION_GATE":
            return lambda v: {
                "status": "COMMIT_VALID",
                "effective_cap": min(v["delegator_cap"], v["receiver_cap"]),
            }
        return lambda v: {
            "status": "COMMIT_VALID",
            "torque_nm": max(-2.5, min(2.5, 4.0 * v["q_err"] - 0.3 * v["dq"])),
        }

    # Arm 4: Guarded RGPO candidate (repaired after obligation discovery)
    def make_repaired_rgpo_candidate(task_id: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        if task_id == "U1_MEMBRANE_VISCOSITY_AND_REFERENCE_GATE":
            def fn_u1(v: dict[str, Any]) -> dict[str, Any]:
                if not v.get("ref_cond_ok", False):
                    return {"status": "ABSTAIN_UNVERIFIED", "reason": "missing_reference_conductivity"}
                net_dp = float(v["pressure_psi"]) - float(v["osmotic_psi"])
                if float(v["flow_lpm"]) <= 0.0 or net_dp <= 0.0:
                    return {"status": "REJECT_INVALID", "reason": "nonpositive_flow_or_net_pressure"}
                sf = (float(v["flow_lpm"]) / net_dp) * math.exp(-0.024 * (float(v["temp_c"]) - 25.0))
                return {"status": "COMMIT_VALID", "specific_flux": sf}
            return fn_u1

        if task_id == "U2_COLD_CHAIN_PRIORITY_SLACK_GATE":
            def fn_u2(v: dict[str, Any]) -> dict[str, Any]:
                if not v.get("sensor_epoch_valid", False):
                    return {"status": "REJECT_INVALID", "reason": "stale_sensor_epoch"}
                vac = float(v["vaccine_kw"])
                sol = float(v["solar_kw"])
                def_kw = 0.0 if sol < vac else min(float(v["deferrable_kw"]), sol - vac)
                return {"status": "COMMIT_VALID", "vaccine_allocated_kw": vac, "deferrable_allocated_kw": def_kw}
            return fn_u2

        if task_id == "U3_RECEIVER_MANDATE_INTERSECTION_GATE":
            def fn_u3(v: dict[str, Any]) -> dict[str, Any]:
                cap = min(float(v["delegator_cap"]), float(v["receiver_cap"]))
                if v.get("replayed", False) or float(v.get("skew_s", 0.0)) > 30.0 or float(v["requested"]) > cap:
                    return {"status": "REJECT_INVALID", "reason": "mandate_or_freshness_violation"}
                return {"status": "COMMIT_VALID", "effective_cap": cap}
            return fn_u3

        def fn_u4(v: dict[str, Any]) -> dict[str, Any]:
            if v.get("estop", False) or float(v.get("voltage_v", 0.0)) < 5.5:
                return {"status": "REJECT_INVALID", "torque_nm": 0.0}
            tau_lim = 2.95 * (float(v["voltage_v"]) / 7.4)
            raw_tau = 4.2 * (float(v["q_err"]) + 0.001 * float(v["delay_ms"]) * float(v["dq"])) - 0.35 * float(v["dq"])
            tau = max(-tau_lim, min(tau_lim, raw_tau))
            return {"status": "COMMIT_VALID", "torque_nm": tau}
        return fn_u4

    arm_summary: dict[str, dict[str, Any]] = {}
    for arm_name in (
        "Arm1_Static_7Flag_Shortcut",
        "Arm2_Always_Abstain",
        "Arm3_Naive_Standard_Unit_Tests",
        "Arm4_Guarded_Executable_RGPO",
    ):
        accepted_count = 0
        false_accepts_total = 0
        nominal_cov_sum = 0.0
        task_reports = []
        for t in tasks:
            tid = t["task_id"]
            obs = t["obligations"]
            if arm_name == "Arm1_Static_7Flag_Shortcut":
                cand = static_7_flag_shortcut
            elif arm_name == "Arm2_Always_Abstain":
                cand = always_abstain_fn
            elif arm_name == "Arm3_Naive_Standard_Unit_Tests":
                cand = make_naive_candidate(tid)
            else:
                # Step 1: Diagnose missing obligations on naive candidate, Step 2: Repair and verify
                diag_rep = gate.evaluate_candidate(tid, f"{arm_name}_pre_repair", make_naive_candidate(tid), obs)
                assert len(diag_rep.discovered_missing_obligations) >= 1
                cand = make_repaired_rgpo_candidate(tid)
            rep = gate.evaluate_candidate(tid, arm_name, cand, obs)
            if rep.independently_accepted:
                accepted_count += 1
            false_accepts_total += rep.false_acceptances_on_hazards
            nominal_cov_sum += rep.nominal_coverage_ratio
            task_reports.append({
                "task_id": tid,
                "independently_accepted": rep.independently_accepted,
                "nominal_coverage_ratio": rep.nominal_coverage_ratio,
                "false_acceptances_on_hazards": rep.false_acceptances_on_hazards,
                "discovered_missing_obligations": rep.discovered_missing_obligations,
                "rejection_reason": rep.rejection_reason,
                "report_sha256": rep.report_sha256,
            })
        arm_summary[arm_name] = {
            "tasks_total": len(tasks),
            "tasks_independently_accepted": accepted_count,
            "mean_nominal_coverage_ratio": round(nominal_cov_sum / len(tasks), 4),
            "total_false_acceptances_on_hazards": false_accepts_total,
            "task_reports": task_reports,
        }

    return {
        "experiment_id": "LOOP-B-INDEPENDENT-RGPO-011-QUALIFICATION",
        "general_invention_claim_disposition": RGPO_011_GENERAL_INVENTION_CLAIM,
        "narrow_practice_disposition": RGPO_NARROW_PRACTICE_STATUS,
        "static_7_flag_dict_passes_prior_constructed_benchmark": True,
        "static_7_flag_dict_passes_executable_obligation_gate": False,
        "always_abstain_passes_executable_obligation_gate": False,
        "arm_comparison": arm_summary,
    }
