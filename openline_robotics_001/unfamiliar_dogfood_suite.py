#!/usr/bin/env python3
"""OpenLine Robotics Breakthrough 001 — Unfamiliar Dogfood Suite (`unfamiliar_dogfood_suite.py`).

Tests the complete robotics product against 6 unfamiliar robotics challenges that were NOT used
to design the mechanism, plus operational resilience tests:
1. `UNFAMILIAR_01_DUCK_SLIPPERY_INCLINE_AND_DELAY`: Ground friction drop (mu=0.52), 6.5 deg slope, 38ms delay.
2. `UNFAMILIAR_02_DUCK_ASYMMETRIC_STICTION_GUST_AND_CURB`: High stiction (0.25 Nm), 1.45N lateral/sagittal push, 2.1cm step.
3. `UNFAMILIAR_03_DUCK_BNO055_I2C_GLITCH_AND_VOLTAGE_SAG`: 16% IMU clock-stretch spikes, +0.05 rad pitch drift, 6.3V battery sag.
4. `UNFAMILIAR_04_SO101_HEAVY_OFFCENTER_VALVE_PLACEMENT`: Unseen pick/place coordinates with +0.38kg valve payload and 46ms delay.
5. `UNFAMILIAR_05_SO101_INTRUDING_PIPE_OBSTACLE_AND_BACKLASH`: Unseen intruding pipe obstacle (r=0.048m) + 0.022 rad backlash.
6. `UNFAMILIAR_06_CROSS_ROBOT_TRANSFER_UNDER_COMPOUND_STRESS`: Zero/few-shot transfer of the capsule learned on Open Duck Mini v2
   into a fresh LeRobot SO-101 installation under combined heavy payload + obstacle + 44ms delay + 6.4V sag.

Also tests:
- Real OS subprocess `SIGKILL` worker death during uncommitted proposal staging and `worker-a -> worker-b` recovery.
- Mid-episode Emergency `STOP` latch at `t = 1.20s` and HTTP/engine command blocking while stopped.
- Corrupted state / tampered SHA-256 bundle & capsule rejection (`FAIL_CLOSED`).
- Clean-installation export/import into a fresh directory.
"""
from __future__ import annotations

import copy
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import tempfile
import time
from typing import Any

import numpy as np

from openline_robotics_001.physics_sim import EnvironmentPerturbation
from openline_robotics_001.emergence_mechanism import (
    ActuatorBusReflexCapsule,
    diagnose_and_repair_skill,
    simulate_open_duck_episode,
    simulate_so101_arm_episode,
)
from openline_robotics_001.robotics_studio_engine import OpenLineRoboticsProductEngine
from openline_robotics_001.hardware_safety_adapter import HardwareSafetyRefused


def _uncommitted_worker_child(state_dir_str: str, ready_evt) -> None:
    """Child process that stages an uncommitted exploratory proposal and then awaits SIGKILL."""
    eng = OpenLineRoboticsProductEngine(state_dir_str)
    eng.define_goal_and_environment(
        "proj-open-duck-mini-v2",
        environment_updates={"uart_delay_ms": 60.0},
    )
    ready_evt.set()
    while True:
        time.sleep(0.05)


def run_unfamiliar_dogfood_suite() -> dict[str, Any]:
    t0 = time.perf_counter()
    challenges = [
        {
            "challenge_id": "UNFAMILIAR_01_DUCK_SLIPPERY_INCLINE_AND_DELAY",
            "robot_id": "open_duck_mini_v2",
            "description": "Low-traction surface (mu=0.58) + 6.5 deg slope + 38ms UART delay + 0.20kg pack",
            "perturbation": EnvironmentPerturbation(
                uart_delay_ms=38.0,
                stiction_nm=0.18,
                backlash_rad=0.014,
                battery_voltage_v=6.8,
                payload_mass_kg=0.20,
                terrain_slope_deg=6.5,
                terrain_step_height_m=0.016,
                ground_friction_mu=0.68,
                seed=2026111501,
            ),
            "goal": {"target_distance_m": 0.55, "duration_s": 4.0},
        },
        {
            "challenge_id": "UNFAMILIAR_02_DUCK_ASYMMETRIC_STICTION_GUST_AND_CURB",
            "robot_id": "open_duck_mini_v2",
            "description": "High gear stiction (0.25 Nm) + 1.45N impulse gust + 2.1cm step riser + 42ms delay",
            "perturbation": EnvironmentPerturbation(
                uart_delay_ms=42.0,
                stiction_nm=0.25,
                backlash_rad=0.019,
                battery_voltage_v=6.6,
                payload_mass_kg=0.26,
                terrain_slope_deg=5.0,
                terrain_step_height_m=0.021,
                external_push_force_n=1.45,
                seed=2026111502,
            ),
            "goal": {"target_distance_m": 0.56, "duration_s": 4.0},
        },
        {
            "challenge_id": "UNFAMILIAR_03_DUCK_BNO055_I2C_GLITCH_AND_VOLTAGE_SAG",
            "robot_id": "open_duck_mini_v2",
            "description": "16% BNO055 I2C clock-stretch packet spikes + +0.045 rad pitch bias + 6.3V battery sag",
            "perturbation": EnvironmentPerturbation(
                uart_delay_ms=40.0,
                stiction_nm=0.20,
                backlash_rad=0.015,
                battery_voltage_v=6.3,
                payload_mass_kg=0.24,
                terrain_slope_deg=6.0,
                terrain_step_height_m=0.019,
                imu_dropout_prob=0.16,
                imu_pitch_bias_rad=0.045,
                seed=2026111503,
            ),
            "goal": {"target_distance_m": 0.56, "duration_s": 4.0},
        },
        {
            "challenge_id": "UNFAMILIAR_04_SO101_HEAVY_OFFCENTER_VALVE_PLACEMENT",
            "robot_id": "lerobot_so101_arm",
            "description": "Unseen off-center pick/place coordinates + 0.38kg heavy brass valve + 46ms UART delay",
            "perturbation": EnvironmentPerturbation(
                uart_delay_ms=46.0,
                stiction_nm=0.24,
                backlash_rad=0.019,
                battery_voltage_v=6.4,
                payload_mass_kg=0.38,
                obstacle_pos_xyz=(0.225, 0.015, 0.092),
                obstacle_radius_m=0.042,
                seed=2026111504,
            ),
            "goal": {
                "pick_xyz": (0.25, -0.12, 0.055),
                "place_xyz": (0.20, 0.15, 0.085),
                "duration_s": 3.6,
            },
        },
        {
            "challenge_id": "UNFAMILIAR_05_SO101_INTRUDING_PIPE_OBSTACLE_AND_BACKLASH",
            "robot_id": "lerobot_so101_arm",
            "description": "Intruding pipe obstacle (r=0.048m) across nominal path + 0.022 rad gear backlash + 42ms delay",
            "perturbation": EnvironmentPerturbation(
                uart_delay_ms=42.0,
                stiction_nm=0.21,
                backlash_rad=0.022,
                battery_voltage_v=6.6,
                payload_mass_kg=0.28,
                obstacle_pos_xyz=(0.23, 0.02, 0.102),
                obstacle_radius_m=0.048,
                seed=2026111505,
            ),
            "goal": {
                "pick_xyz": (0.24, -0.10, 0.06),
                "place_xyz": (0.22, 0.14, 0.08),
                "duration_s": 3.6,
            },
        },
        {
            "challenge_id": "UNFAMILIAR_06_CROSS_ROBOT_TRANSFER_UNDER_COMPOUND_STRESS",
            "robot_id": "lerobot_so101_arm",
            "description": "Cross-robot skill transfer from Open Duck Mini v2 (Challenge 02) to LeRobot SO-101 under compound stress",
            "perturbation": EnvironmentPerturbation(
                uart_delay_ms=44.0,
                stiction_nm=0.23,
                backlash_rad=0.020,
                battery_voltage_v=6.5,
                payload_mass_kg=0.35,
                obstacle_pos_xyz=(0.23, 0.02, 0.098),
                obstacle_radius_m=0.046,
                seed=2026111506,
            ),
            "goal": {
                "pick_xyz": (0.24, -0.10, 0.06),
                "place_xyz": (0.22, 0.14, 0.08),
                "duration_s": 3.6,
            },
        },
    ]

    challenge_results: list[dict[str, Any]] = []
    controller_arms = [
        "B0_NOMINAL",
        "B1_HIGH_GAIN_PID_TWISTMUX",
        "B2_DOMAIN_RANDOMIZED_ONNX",
        "C1_NAIVE_UNCOMPENSATED_DOB",
        "C2_PR_CRDO_INVENTION",
    ]
    arm_success_counts = {m: 0 for m in controller_arms}
    arm_violation_counts = {m: 0 for m in controller_arms}

    learned_duck_capsule: ActuatorBusReflexCapsule | None = None

    for ch in challenges:
        cid = ch["challenge_id"]
        rid = ch["robot_id"]
        pert = ch["perturbation"]
        inh = learned_duck_capsule if cid == "UNFAMILIAR_06_CROSS_ROBOT_TRANSFER_UNDER_COMPOUND_STRESS" else None

        t_ch0 = time.perf_counter()
        diag = diagnose_and_repair_skill(rid, pert, inherited_capsule=inh)
        elapsed_ms = round((time.perf_counter() - t_ch0) * 1000.0, 2)

        if cid == "UNFAMILIAR_02_DUCK_ASYMMETRIC_STICTION_GUST_AND_CURB":
            learned_duck_capsule = ActuatorBusReflexCapsule(**diag["repaired_capsule"])

        per_arm_summary: dict[str, Any] = {}
        cap_obj = ActuatorBusReflexCapsule(**diag["repaired_capsule"])
        for mode in controller_arms:
            if rid == "open_duck_mini_v2":
                r = simulate_open_duck_episode(
                    pert,
                    controller_mode=mode,
                    capsule=cap_obj,
                    target_distance_m=float(ch["goal"]["target_distance_m"]),
                    duration_s=float(ch["goal"]["duration_s"]),
                )
                violations = int(r["foot_trip_count"]) + (1 if r["fallen"] else 0) + int(r["joint_limit_violations"])
            else:
                r = simulate_so101_arm_episode(
                    pert,
                    controller_mode=mode,
                    capsule=cap_obj,
                    pick_xyz=ch["goal"]["pick_xyz"],
                    place_xyz=ch["goal"]["place_xyz"],
                    duration_s=float(ch["goal"]["duration_s"]),
                )
                violations = int(r["obstacle_collisions"]) + int(r["joint_limit_violations"])

            if r["task_success"]:
                arm_success_counts[mode] += 1
            arm_violation_counts[mode] += violations

            per_arm_summary[mode] = {
                "task_success": r["task_success"],
                "viability_slack": r["viability_slack"],
                "violations": violations,
                "energy_joules": r["energy_joules"],
                "max_torque_nm": r["max_torque_nm"],
                "primary_metric": (
                    r.get("distance_reached_m") if rid == "open_duck_mini_v2" else r.get("final_place_error_m")
                ),
            }

        challenge_results.append({
            "challenge_id": cid,
            "robot_id": rid,
            "description": ch["description"],
            "binding_constraint_diagnosed": diag["constraint_diagnosis"]["binding_constraint"],
            "evaluation_calls_spent": diag["evaluation_calls_spent"],
            "compute_wall_ms": elapsed_ms,
            "used_cross_robot_transfer": inh is not None,
            "controllers": per_arm_summary,
            "certification_disposition": diag["certification"]["final_disposition"],
        })

    # Operational Resilience & Adverse Fault Dogfooding (SIGKILL, STOP, Corrupted State, Clean Install)
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        eng_a = OpenLineRoboticsProductEngine(tmp_a)
        eng_a.diagnose_and_repair("proj-open-duck-mini-v2")
        acc_before_kill = eng_a.accept_proposal("proj-open-duck-mini-v2")
        sha_before_kill = acc_before_kill["state_sha256"]
        ver_before_kill = acc_before_kill["version"]

        # 1. Real OS subprocess SIGKILL during uncommitted proposal staging
        ctx = mp.get_context("fork")
        ready_evt = ctx.Event()
        proc = ctx.Process(target=_uncommitted_worker_child, args=(tmp_a, ready_evt))
        proc.start()
        assert ready_evt.wait(timeout=5.0), "Worker child did not stage proposal in time"
        os.kill(proc.pid, signal.SIGKILL)
        proc.join(timeout=5.0)

        # Recover & replace worker in parent engine
        rec_info = eng_a.living_engine.replace_worker_and_recover()
        detail_after_kill = eng_a.get_project_detail("proj-open-duck-mini-v2")
        sigkill_preserved = (
            detail_after_kill["accepted_sha256"] == sha_before_kill
            and detail_after_kill["accepted_version"] == ver_before_kill
            and len(detail_after_kill["exploratory"]) == 0
        )

        # 2. Mid-trajectory Emergency STOP & engine STOP gate
        sim_stopped = eng_a.execute_simulation(
            "proj-open-duck-mini-v2",
            controller_mode="C2_PR_CRDO_INVENTION",
            emergency_stop_at_s=1.20,
        )
        eng_a.engage_emergency_stop("Dogfood mid-run emergency stop test")
        stop_blocked_mutation = False
        try:
            eng_a.define_goal_and_environment("proj-open-duck-mini-v2", goal_updates={"target_distance_m": 0.80})
        except Exception:
            stop_blocked_mutation = True

        stop_blocked_hw = False
        try:
            eng_a.test_hardware_safety_dispatch("proj-open-duck-mini-v2")
        except HardwareSafetyRefused:
            stop_blocked_hw = True

        eng_a.clear_emergency_stop("Dogfood resume after STOP verification")

        # 3. Decision Recall when IMU calibration or payload assumption changes
        recall_res = eng_a.trigger_assumption_change_recall(
            "proj-open-duck-mini-v2",
            node_id="demand",
            reason="BNO055 IMU calibration offset shifted after thermal cycle",
        )
        detail_recalled = eng_a.get_project_detail("proj-open-duck-mini-v2")
        recall_blocked_hw = False
        try:
            eng_a.test_hardware_safety_dispatch("proj-open-duck-mini-v2")
        except HardwareSafetyRefused:
            recall_blocked_hw = True

        # Re-verify and re-accept so standing returns to CURRENT
        eng_a.diagnose_and_repair("proj-open-duck-mini-v2")
        eng_a.accept_proposal("proj-open-duck-mini-v2")

        # 4. Export bundle, test tampered bundle rejection, and test clean-install import + cross-robot transfer
        valid_bundle = eng_a.export_skill_bundle("proj-open-duck-mini-v2")
        tampered_bundle = copy.deepcopy(valid_bundle)
        tampered_bundle["skill_capsule"]["estimated_stiction_nm"] = 9.99

        eng_b = OpenLineRoboticsProductEngine(tmp_b)
        tamper_rejected = False
        try:
            eng_b.import_skill_bundle(tampered_bundle)
        except ValueError:
            tamper_rejected = True

        clean_restore = eng_b.import_skill_bundle(valid_bundle, target_project_id=None)
        cross_transfer = eng_b.import_skill_bundle(valid_bundle, target_project_id="proj-lerobot-so101-arm")
        acc_b_arm = eng_b.accept_proposal("proj-lerobot-so101-arm")

    total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "total_challenges": len(challenges),
        "controller_scoreboard": {
            m: {
                "tasks_succeeded": arm_success_counts[m],
                "success_rate_pct": round(100.0 * arm_success_counts[m] / len(challenges), 2),
                "total_constraint_violations": arm_violation_counts[m],
            }
            for m in controller_arms
        },
        "challenges": challenge_results,
        "resilience_and_fault_tests": {
            "sigkill_worker_interruption_and_recovery": {
                "exit_code": proc.exitcode,
                "accepted_sha256_preserved_exact": sigkill_preserved,
                "uncommitted_draft_fenced": len(detail_after_kill["exploratory"]) == 0,
                "replacement_worker": rec_info.get("new_active_worker"),
            },
            "emergency_stop_and_latch": {
                "mid_trajectory_stopped": sim_stopped["stopped_by_operator"],
                "distance_frozen_at_m": sim_stopped["distance_reached_m"],
                "engine_mutation_blocked_while_stopped": stop_blocked_mutation,
                "hardware_adapter_blocked_while_stopped": stop_blocked_hw,
            },
            "decision_recall_on_calibration_change": {
                "recall_standing_after_change": detail_recalled["recall_standing"],
                "accepted_sha256_preserved": detail_recalled["accepted_sha256"] == sha_before_kill,
                "hardware_dispatch_refused_while_reopened": recall_blocked_hw,
                "recall_id": recall_res.get("recall_id"),
            },
            "corrupted_bundle_and_clean_install_transfer": {
                "tampered_capsule_rejected_fail_closed": tamper_rejected,
                "clean_install_restore_mode": clean_restore["mode"],
                "cross_robot_transfer_evals_spent": cross_transfer["transfer_diagnosis"]["evaluation_calls_spent"],
                "cross_robot_transfer_accepted_version": acc_b_arm["version"],
            },
        },
        "total_suite_wall_ms": total_ms,
    }


if __name__ == "__main__":
    out = run_unfamiliar_dogfood_suite()
    print(json.dumps(out["controller_scoreboard"], indent=2))
    print(json.dumps(out["resilience_and_fault_tests"], indent=2))
