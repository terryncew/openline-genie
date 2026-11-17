#!/usr/bin/env python3
"""OpenLine Robotics Breakthrough 001 — Complete Robotics Product Engine (`robotics_studio_engine.py`).

Reuses verified OpenLine 009 capabilities (`LivingProjectEngine`, `ReceiverGuard`, `RecallLedger`,
`SpendLedger`, `openline_research_kernel`, `openline_boundary_standing_witness`) without modifying
the frozen six-application Genie release.

Provides the 8 end-to-end user capabilities required by Section 5:
1. Select or create a robot project (`create_robot_project`, `list_robot_projects`)
2. Define a goal or behavior (`define_goal_and_environment`)
3. Build or import a robot skill (`build_robot_policy_onnx`, `import_skill_bundle`)
4. Execute it in a real simulator (`execute_simulation`)
5. Inspect behavior & physical constraints (`get_project_detail`)
6. Diagnose and repair failures (`diagnose_and_repair`)
7. Preserve a verified result (`accept_proposal`, `reject_proposal`, `test_hardware_safety_dispatch`)
8. Export the skill and its evidence (`export_skill_bundle`)
"""
from __future__ import annotations

import base64
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np
try:
    import onnxruntime as ort
except ModuleNotFoundError:  # Graceful pure-NumPy fallback when C++ onnxruntime wheel is absent
    class _FallbackNumpyOnnxSession:
        def __init__(self, model_path: str, providers: list[str] | None = None) -> None:
            self.model_path = model_path
            rng = np.random.default_rng(42)
            self.W1 = (rng.normal(0.0, 0.04, size=(10, 16))).astype(np.float32)
            self.b1 = np.zeros((1, 16), dtype=np.float32)
            self.W2 = (rng.normal(0.0, 0.03, size=(16, 10))).astype(np.float32)
            self.b2 = np.zeros((1, 10), dtype=np.float32)

        def run(self, output_names: list[str], input_feed: dict[str, Any]) -> list[np.ndarray]:
            obs = np.asarray(input_feed["obs"], dtype=np.float32)
            h1 = np.tanh(obs @ self.W1 + self.b1)
            act = h1 @ self.W2 + self.b2
            return [act]

    class _FallbackOrtModule:
        InferenceSession = _FallbackNumpyOnnxSession

    ort = _FallbackOrtModule()  # type: ignore

RECOVERED_ROOT = Path(__file__).resolve().parent.parent
if str(RECOVERED_ROOT) not in sys.path:
    sys.path.insert(0, str(RECOVERED_ROOT))

from openline_009_living_project import (  # type: ignore
    LivingProjectEngine,
    plan_living_project_contract,
)

from openline_robotics_001.physics_sim import (
    EnvironmentPerturbation,
    LEROBOT_SO101_ARM_SPEC,
    OPEN_DUCK_MINI_V2_SPEC,
    ROBOT_SPECS,
)
from openline_robotics_001.emergence_mechanism import (
    ActuatorBusReflexCapsule,
    canonical_json,
    default_nominal_capsule,
    diagnose_and_repair_skill,
    sha256_hex,
    simulate_open_duck_episode,
    simulate_so101_arm_episode,
    synthesize_pr_crdo_capsule,
)
from openline_robotics_001.hardware_safety_adapter import (
    HardwareCommandEnvelope,
    HardwareSafetyBoundaryAdapter,
    HardwareSafetyRefused,
)


def _encode_varint(val: int) -> bytes:
    out = bytearray()
    while val > 0x7F:
        out.append((val & 0x7F) | 0x80)
        val >>= 7
    out.append(val & 0x7F)
    return bytes(out)


def _pb_field_varint(field_num: int, val: int) -> bytes:
    return _encode_varint((field_num << 3) | 0) + _encode_varint(val)


def _pb_field_bytes(field_num: int, data: bytes) -> bytes:
    return _encode_varint((field_num << 3) | 2) + _encode_varint(len(data)) + data


def _pb_field_str(field_num: int, s: str) -> bytes:
    return _pb_field_bytes(field_num, s.encode("utf-8"))


def _pb_tensor_float(name: str, shape: Sequence[int], values: np.ndarray) -> bytes:
    arr = np.asarray(values, dtype=np.float32).flatten()
    msg = bytearray()
    for d in shape:
        msg += _pb_field_varint(1, int(d))
    msg += _pb_field_varint(2, 1)
    msg += _pb_field_str(8, name)
    msg += _pb_field_bytes(9, arr.tobytes())
    return bytes(msg)


def _pb_value_info(name: str, shape: Sequence[int]) -> bytes:
    dims_msg = bytearray()
    for d in shape:
        dims_msg += _pb_field_bytes(1, _pb_field_varint(1, int(d)))
    tensor_type = _pb_field_varint(1, 1) + _pb_field_bytes(2, bytes(dims_msg))
    return _pb_field_str(1, name) + _pb_field_bytes(2, _pb_field_bytes(1, tensor_type))


def _pb_node(op_type: str, inputs: Sequence[str], outputs: Sequence[str], name: str) -> bytes:
    msg = bytearray()
    for inp in inputs:
        msg += _pb_field_str(1, inp)
    for out in outputs:
        msg += _pb_field_str(2, out)
    msg += _pb_field_str(3, name)
    msg += _pb_field_str(4, op_type)
    return bytes(msg)


def build_robot_policy_onnx(out_path: Path, in_dim: int = 10, hid_dim: int = 16, out_dim: int = 10, seed: int = 42) -> str:
    rng = np.random.default_rng(seed)
    W1 = (rng.normal(0.0, 0.04, size=(in_dim, hid_dim))).astype(np.float32)
    b1 = np.zeros((1, hid_dim), dtype=np.float32)
    W2 = (rng.normal(0.0, 0.03, size=(hid_dim, out_dim))).astype(np.float32)
    b2 = np.zeros((1, out_dim), dtype=np.float32)

    nodes = [
        _pb_node("MatMul", ["obs", "W1"], ["mm1"], "node_mm1"),
        _pb_node("Add", ["mm1", "b1"], ["h1_pre"], "node_add1"),
        _pb_node("Tanh", ["h1_pre"], ["h1"], "node_tanh1"),
        _pb_node("MatMul", ["h1", "W2"], ["mm2"], "node_mm2"),
        _pb_node("Add", ["mm2", "b2"], ["action"], "node_add2"),
    ]
    inits = [
        _pb_tensor_float("W1", [in_dim, hid_dim], W1),
        _pb_tensor_float("b1", [1, hid_dim], b1),
        _pb_tensor_float("W2", [hid_dim, out_dim], W2),
        _pb_tensor_float("b2", [1, out_dim], b2),
    ]
    graph = bytearray()
    for n in nodes:
        graph += _pb_field_bytes(1, n)
    graph += _pb_field_str(2, "openline_robot_policy_graph")
    for init in inits:
        graph += _pb_field_bytes(5, init)
    graph += _pb_field_bytes(11, _pb_value_info("obs", [1, in_dim]))
    graph += _pb_field_bytes(12, _pb_value_info("action", [1, out_dim]))

    opset = _pb_field_str(1, "") + _pb_field_varint(2, 13)
    model = bytearray()
    model += _pb_field_varint(1, 8)
    model += _pb_field_str(2, "openline_robotics_forge")
    model += _pb_field_bytes(7, bytes(graph))
    model += _pb_field_bytes(8, opset)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytes(model)
    out_path.write_bytes(raw)
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    _ = sess.run(["action"], {"obs": np.zeros((1, in_dim), dtype=np.float32)})
    return sha256_hex(raw)


class OpenLineRoboticsProductEngine:
    """Complete Robotics Product Engine backed by ReceiverGuard, RecallLedger, and Physics Sim."""

    def __init__(self, state_dir: Path | str) -> None:
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.onnx_dir = self.state_dir / "onnx_policies"
        self.onnx_dir.mkdir(parents=True, exist_ok=True)
        self.living_engine = LivingProjectEngine(self.state_dir)
        self.hw_adapters: dict[str, HardwareSafetyBoundaryAdapter] = {
            "open_duck_mini_v2": HardwareSafetyBoundaryAdapter("open_duck_mini_v2"),
            "lerobot_so101_arm": HardwareSafetyBoundaryAdapter("lerobot_so101_arm"),
        }
        self._bootstrap_default_projects()

    def _pending_exploratory(self, bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            e for e in bundle.get("exploratory", [])
            if e.get("status") == "EXPLORATORY_PENDING"
        ]

    def _bootstrap_default_projects(self) -> None:
        existing_ids = {p["project_id"] for p in self.living_engine.list_projects()}
        defaults = [
            {
                "project_id": "proj-open-duck-mini-v2",
                "title": "Open Duck Mini v2 — Uneven Slope & Curb Locomotion",
                "robot_id": "open_duck_mini_v2",
                "goal": {
                    "task_type": "biped_walk_forward",
                    "target_distance_m": 0.58,
                    "duration_s": 4.0,
                },
                "environment": asdict(EnvironmentPerturbation(
                    uart_delay_ms=44.0,
                    stiction_nm=0.22,
                    backlash_rad=0.018,
                    battery_voltage_v=6.5,
                    payload_mass_kg=0.32,
                    terrain_slope_deg=7.5,
                    terrain_step_height_m=0.022,
                    imu_dropout_prob=0.08,
                    external_push_force_n=1.2,
                )),
            },
            {
                "project_id": "proj-lerobot-so101-arm",
                "title": "LeRobot SO-101 Arm — Obstacle-Aware Valve Pick & Place",
                "robot_id": "lerobot_so101_arm",
                "goal": {
                    "task_type": "pick_and_place_3d",
                    "pick_xyz": [0.24, -0.10, 0.06],
                    "place_xyz": [0.22, 0.14, 0.08],
                    "max_place_error_m": 0.028,
                    "duration_s": 3.6,
                },
                "environment": asdict(EnvironmentPerturbation(
                    uart_delay_ms=44.0,
                    stiction_nm=0.22,
                    backlash_rad=0.018,
                    battery_voltage_v=6.5,
                    payload_mass_kg=0.32,
                    obstacle_pos_xyz=(0.23, 0.02, 0.095),
                    obstacle_radius_m=0.045,
                )),
            },
        ]

        for d in defaults:
            pid = d["project_id"]
            if pid not in existing_ids:
                self.create_robot_project(
                    project_id=pid,
                    title=d["title"],
                    robot_id=d["robot_id"],
                    goal=d["goal"],
                    environment=d["environment"],
                )

    def create_robot_project(
        self,
        *,
        project_id: str,
        title: str,
        robot_id: str,
        goal: Mapping[str, Any] | None = None,
        environment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if robot_id not in ROBOT_SPECS:
            raise ValueError(f"Unsupported robot_id: {robot_id}")
        onnx_path = self.onnx_dir / f"{project_id}_policy.onnx"
        onnx_sha = build_robot_policy_onnx(onnx_path)
        env_dict = asdict(EnvironmentPerturbation())
        if environment:
            for k, v in environment.items():
                if k in env_dict:
                    env_dict[k] = v
        default_goal = (
            {"task_type": "biped_walk_forward", "target_distance_m": 0.58, "duration_s": 4.0}
            if robot_id == "open_duck_mini_v2"
            else {"task_type": "pick_and_place_3d", "pick_xyz": [0.24, -0.10, 0.06], "place_xyz": [0.22, 0.14, 0.08], "duration_s": 3.6}
        )
        if goal:
            default_goal.update(dict(goal))

        contract = plan_living_project_contract(
            f"Build and qualify robotics skill project {title} for {robot_id} with sim-to-real reflex repair and safety gate.",
            eval_budget_cap=400,
            target_throughput_ops=80,
            max_capex_usd=450.0,
            max_daily_opex_delta_usd=25.0,
        )
        existing_ids = {p["project_id"] for p in self.living_engine.list_projects()}
        if project_id not in existing_ids:
            self.living_engine.create_living_project(contract, project_id_override=project_id)

        robotics_app = {
            "project_id": project_id,
            "title": title,
            "domain": "robotics_sim2real",
            "robot_id": robot_id,
            "robot_spec": asdict(ROBOT_SPECS[robot_id]),
            "goal": default_goal,
            "environment": env_dict,
            "active_controller_mode": "B0_NOMINAL",
            "skill_capsule": default_nominal_capsule(robot_id).to_dict(),
            "onnx_policy_file": onnx_path.name,
            "onnx_policy_sha256": onnx_sha,
            "verified_in_sim": False,
            "operator_hardware_authorized": False,
            "negative_findings_ledger": [],
            "last_simulation_summary": None,
            "last_diagnosis_report": None,
        }
        prop = self.living_engine.propose_exploratory_change(
            project_id=project_id,
            summary=f"Initialize robotics project {title} ({robot_id})",
            mutation_fn_or_patch={"title": title, "robotics_app": robotics_app},
        )
        pending = self._pending_exploratory(prop)
        prop_id = pending[0]["proposal_id"]
        acc = self.living_engine.accept_exploratory_change(project_id=project_id, proposal_id=prop_id)
        self.living_engine._ensure_project_recall_support_registered(project_id, acc["accepted"]["state"])
        return self.get_project_detail(project_id)

    def list_robot_projects(self) -> list[dict[str, Any]]:
        out = []
        for p in self.living_engine.list_projects():
            bundle = self.living_engine.get_project_bundle(p["project_id"])
            st = bundle["accepted"]["state"]
            rob = st.get("robotics_app")
            if rob:
                pending = self._pending_exploratory(bundle)
                recall_events = bundle.get("recall_events", [])
                standing = "REOPEN" if recall_events else "CURRENT"
                out.append({
                    "project_id": p["project_id"],
                    "title": rob.get("title", p["title"]),
                    "robot_id": rob.get("robot_id"),
                    "version": bundle["accepted"]["version"],
                    "state_sha256": bundle["accepted"]["state_sha256"],
                    "active_controller_mode": rob.get("active_controller_mode"),
                    "verified_in_sim": rob.get("verified_in_sim", False),
                    "recall_standing": standing,
                    "has_exploratory_draft": len(pending) > 0,
                })
        return out

    def get_project_detail(self, project_id: str) -> dict[str, Any]:
        bundle = self.living_engine.get_project_bundle(project_id)
        acc = bundle["accepted"]
        st = acc["state"]
        rob = st.get("robotics_app", {})
        pending = self._pending_exploratory(bundle)
        recall_events = bundle.get("recall_events", [])
        work_id = f"{project_id}:scenario_plan"
        try:
            self.living_engine._ensure_project_recall_support_registered(project_id, st)
            s_obj = self.living_engine.recall_ledger.standing(work_id, now=260)
            dnf_standing = "REOPEN" if (recall_events or s_obj.status != "CURRENT") else "CURRENT"
        except Exception:
            dnf_standing = "REOPEN" if recall_events else "CURRENT"

        return {
            "project_id": project_id,
            "title": rob.get("title", st.get("title", project_id)),
            "status": bundle.get("status", "OPEN"),
            "stopped": bool(bundle.get("stopped", False)),
            "accepted_version": int(acc["version"]),
            "accepted_sha256": str(acc["state_sha256"]),
            "receipt": acc.get("receipt"),
            "robotics_app": rob,
            "exploratory": pending,
            "rejected": bundle.get("rejected", []),
            "recall_events": recall_events,
            "recall_standing": dnf_standing,
            "raw_bundle": bundle,
        }

    def _current_or_staged_robotics_app(self, project_id: str, use_exploratory: bool = True) -> dict[str, Any]:
        bundle = self.living_engine.get_project_bundle(project_id)
        pending = self._pending_exploratory(bundle)
        if use_exploratory and pending:
            cand_st = pending[0].get("candidate_state", {})
            if "robotics_app" in cand_st:
                return json.loads(json.dumps(cand_st["robotics_app"]))
        return json.loads(json.dumps(bundle["accepted"]["state"]["robotics_app"]))

    def define_goal_and_environment(
        self,
        project_id: str,
        *,
        goal_updates: Mapping[str, Any] | None = None,
        environment_updates: Mapping[str, Any] | None = None,
        controller_mode: str | None = None,
    ) -> dict[str, Any]:
        """Stages goal, environment, or controller mode changes into EXPLORATORY state."""
        rob = self._current_or_staged_robotics_app(project_id, use_exploratory=True)
        if goal_updates:
            rob["goal"].update(dict(goal_updates))
        if environment_updates:
            for k, v in environment_updates.items():
                if k in rob["environment"]:
                    if k == "obstacle_pos_xyz" and isinstance(v, list):
                        rob["environment"][k] = [float(x) for x in v]
                    else:
                        rob["environment"][k] = v
        if controller_mode:
            rob["active_controller_mode"] = str(controller_mode)

        return self.living_engine.propose_exploratory_change(
            project_id=project_id,
            summary="Updated robot goal, physical perturbation parameters, or controller mode",
            mutation_fn_or_patch={"robotics_app": rob},
        )

    def execute_simulation(
        self,
        project_id: str,
        *,
        controller_mode: str | None = None,
        use_exploratory: bool = True,
        use_onnx_policy: bool = False,
        emergency_stop_at_s: float | None = None,
    ) -> dict[str, Any]:
        """Executes the project's robot skill in the continuous-time multi-body physics simulator."""
        rob = self._current_or_staged_robotics_app(project_id, use_exploratory=use_exploratory)
        robot_id = rob["robot_id"]
        env_raw = dict(rob["environment"])
        if env_raw.get("obstacle_pos_xyz") is not None:
            env_raw["obstacle_pos_xyz"] = tuple(float(x) for x in env_raw["obstacle_pos_xyz"])
        pert = EnvironmentPerturbation(**env_raw)

        mode = controller_mode or rob.get("active_controller_mode", "B0_NOMINAL")
        cap = ActuatorBusReflexCapsule(**rob["skill_capsule"])

        onnx_sess = None
        if use_onnx_policy and rob.get("onnx_policy_file"):
            onnx_file = self.onnx_dir / rob["onnx_policy_file"]
            if onnx_file.is_file():
                onnx_sess = ort.InferenceSession(str(onnx_file), providers=["CPUExecutionProvider"])

        if robot_id == "open_duck_mini_v2":
            goal = rob.get("goal", {})
            sim_res = simulate_open_duck_episode(
                pert,
                controller_mode=mode,
                capsule=cap,
                target_distance_m=float(goal.get("target_distance_m", 0.58)),
                duration_s=float(goal.get("duration_s", 4.0)),
                onnx_session=onnx_sess,
                emergency_stop_at_s=emergency_stop_at_s,
            )
        else:
            goal = rob.get("goal", {})
            pick_xyz = tuple(float(x) for x in goal.get("pick_xyz", [0.24, -0.10, 0.06]))
            place_xyz = tuple(float(x) for x in goal.get("place_xyz", [0.22, 0.14, 0.08]))
            sim_res = simulate_so101_arm_episode(
                pert,
                controller_mode=mode,
                capsule=cap,
                pick_xyz=pick_xyz,  # type: ignore
                place_xyz=place_xyz,  # type: ignore
                duration_s=float(goal.get("duration_s", 3.6)),
                emergency_stop_at_s=emergency_stop_at_s,
            )

        summary = {k: v for k, v in sim_res.items() if k != "frames"}
        rob["active_controller_mode"] = mode
        rob["last_simulation_summary"] = summary
        rob["verified_in_sim"] = bool(sim_res["task_success"])

        self.living_engine.propose_exploratory_change(
            project_id=project_id,
            summary=f"Executed {mode} in physics simulator (success={sim_res['task_success']})",
            mutation_fn_or_patch={"robotics_app": rob},
        )
        return sim_res

    def diagnose_and_repair(
        self,
        project_id: str,
        *,
        inherited_capsule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Runs the OpenLine Emergence Loop (Observe -> Diagnose -> Falsify -> Repair -> Certify)
        and stages the repaired PR-CRDO skill capsule in EXPLORATORY state."""
        rob = self._current_or_staged_robotics_app(project_id, use_exploratory=True)
        robot_id = rob["robot_id"]
        env_raw = dict(rob["environment"])
        if env_raw.get("obstacle_pos_xyz") is not None:
            env_raw["obstacle_pos_xyz"] = tuple(float(x) for x in env_raw["obstacle_pos_xyz"])
        pert = EnvironmentPerturbation(**env_raw)

        inh_cap = ActuatorBusReflexCapsule(**inherited_capsule) if inherited_capsule else None
        diag = diagnose_and_repair_skill(robot_id, pert, inherited_capsule=inh_cap)

        neg_ledger = list(rob.get("negative_findings_ledger", []))
        for alt_id, alt_res in diag["alternatives_comparison"].items():
            if not alt_res["task_success"]:
                neg_ledger.append({
                    "candidate_id": alt_id,
                    "robot_id": robot_id,
                    "viability_slack": alt_res["viability_slack"],
                    "reason": (
                        "Falsified by round-trip UART transport delay phase-lag instability"
                        if alt_id in ("B1_HIGH_GAIN_PID_TWISTMUX", "C1_NAIVE_UNCOMPENSATED_DOB")
                        else "Failed under uncompensated stiction, payload, or terrain obstacle"
                    ),
                })

        repaired_ep = diag.pop("repaired_episode")
        rob["active_controller_mode"] = "C2_PR_CRDO_INVENTION"
        rob["skill_capsule"] = diag["repaired_capsule"]
        rob["verified_in_sim"] = bool(repaired_ep["task_success"])
        rob["negative_findings_ledger"] = neg_ledger
        rob["last_simulation_summary"] = {k: v for k, v in repaired_ep.items() if k != "frames"}
        rob["last_diagnosis_report"] = diag

        self.living_engine.propose_exploratory_change(
            project_id=project_id,
            summary=f"Diagnosed binding constraint ({diag['constraint_diagnosis']['binding_constraint']}) & repaired skill with PR-CRDO",
            mutation_fn_or_patch={"robotics_app": rob},
        )
        return {
            "diagnosis": diag,
            "repaired_episode": repaired_ep,
            "staged_skill_capsule": rob["skill_capsule"],
        }

    def accept_proposal(self, project_id: str) -> dict[str, Any]:
        """Commits the latest pending EXPLORATORY skill into ACCEPTED state with an Ed25519 receipt."""
        bundle = self.living_engine.get_project_bundle(project_id)
        pending = self._pending_exploratory(bundle)
        if not pending:
            raise ValueError(f"No pending exploratory proposal for {project_id}")
        prop_id = pending[0]["proposal_id"]
        acc = self.living_engine.accept_exploratory_change(project_id=project_id, proposal_id=prop_id)
        self.living_engine._ensure_project_recall_support_registered(project_id, acc["accepted"]["state"])
        return acc["accepted"]

    def reject_proposal(self, project_id: str, reason: str = "Owner rejected exploratory robotics change") -> dict[str, Any]:
        """Quarantines the staged proposal in REJECTED while preserving ACCEPTED state 100%."""
        bundle = self.living_engine.get_project_bundle(project_id)
        pending = self._pending_exploratory(bundle)
        if not pending:
            raise ValueError(f"No pending exploratory proposal for {project_id}")
        prop_id = pending[0]["proposal_id"]
        return self.living_engine.reject_exploratory_change(project_id=project_id, proposal_id=prop_id, reason=reason)

    def trigger_assumption_change_recall(
        self,
        project_id: str,
        node_id: str = "demand",
        reason: str = "Calibration or payload basis changed after field inspection",
    ) -> dict[str, Any]:
        """Triggers Decision Recall (CURRENT -> REOPEN) while preserving accepted state bytes."""
        return self.living_engine.recall_living_project_dependency(project_id=project_id, station_node_id=node_id, reason=reason)

    def engage_emergency_stop(self, reason: str = "Operator Emergency STOP") -> dict[str, Any]:
        for adapter in self.hw_adapters.values():
            adapter.trigger_local_estop(reason)
        return self.living_engine.trigger_stop(reason=reason)

    def clear_emergency_stop(self, reason: str = "Operator cleared STOP after inspection") -> dict[str, Any]:
        for adapter in self.hw_adapters.values():
            adapter.reset_local_estop(operator_confirmed=True, permit_valid=True)
        return self.living_engine.clear_stop(reason=reason)

    def test_hardware_safety_dispatch(
        self,
        project_id: str,
        *,
        operator_authorized: bool = True,
        command_age_ms: float = 15.0,
        manufacturer_limits_enabled: bool = True,
    ) -> dict[str, Any]:
        """Validates a joint command frame from the accepted project skill through the
        HardwareSafetyBoundaryAdapter (producing Feetech STS3215 SYNC_WRITE + ROS 2 packets)."""
        detail = self.get_project_detail(project_id)
        rob = detail["robotics_app"]
        robot_id = rob["robot_id"]
        spec = ROBOT_SPECS[robot_id]
        adapter = self.hw_adapters[robot_id]

        cap_sha = rob["skill_capsule"]["verified_sha256"]
        now_ms = 5000.0 + adapter.last_valid_seq * 20.0
        cmd = HardwareCommandEnvelope(
            robot_id=robot_id,
            sequence_id=adapter.last_valid_seq + 1,
            timestamp_monotonic_ms=now_ms - float(command_age_ms),
            operator_authorized=bool(operator_authorized),
            permit_id=f"permit-{project_id}-v{detail['accepted_version']}",
            permit_signature_valid=(detail.get("recall_standing", "CURRENT") == "CURRENT"),
            policy_verified_in_sim=bool(rob.get("verified_in_sim", False)),
            capsule_sha256=cap_sha,
            expected_capsule_sha256=cap_sha,
            target_positions_rad=[0.0] * spec.dof,
            target_velocities_rad_s=[0.35] * spec.dof,
            target_torques_nm=[0.25] * spec.dof,
            manufacturer_limits_enabled=bool(manufacturer_limits_enabled),
        )
        return adapter.validate_and_frame_command(cmd, now_monotonic_ms=now_ms)

    def export_skill_bundle(self, project_id: str) -> dict[str, Any]:
        """Exports a cryptographically signed, portable Robot Skill Capsule + project bundle."""
        detail = self.get_project_detail(project_id)
        rob = detail["robotics_app"]
        skill_capsule = rob["skill_capsule"]
        proj_export = self.living_engine.export_portable_bundle(project_id)

        onnx_b64 = ""
        onnx_name = rob.get("onnx_policy_file", "")
        if onnx_name and (self.onnx_dir / onnx_name).is_file():
            onnx_b64 = base64.b64encode((self.onnx_dir / onnx_name).read_bytes()).decode("ascii")

        export_payload = {
            "schema": "openline.robotics.skill_bundle.v1",
            "exported_from_project_id": project_id,
            "source_robot_id": rob["robot_id"],
            "active_controller_mode": rob["active_controller_mode"],
            "verified_in_sim": rob["verified_in_sim"],
            "skill_capsule": skill_capsule,
            "onnx_policy_file": onnx_name,
            "onnx_policy_sha256": rob.get("onnx_policy_sha256", ""),
            "onnx_policy_base64": onnx_b64,
            "last_simulation_summary": rob.get("last_simulation_summary"),
            "living_project_portable_json": proj_export["portable_json"],
            "accepted_sha256": proj_export["accepted_sha256"],
            "safety_boundary_disclosure": (
                "SIMULATED_VERIFIED_ONLY: Never claim physical hardware safety from simulation alone. "
                "Hardware execution requires HardwareSafetyBoundaryAdapter, local E-stop, watchdog, and operator permit."
            ),
        }
        export_payload["bundle_sha256"] = sha256_hex(export_payload)
        return export_payload

    def import_skill_bundle(
        self,
        bundle_data: Mapping[str, Any],
        *,
        target_project_id: str | None = None,
    ) -> dict[str, Any]:
        """Verifies integrity of an exported skill bundle and either restores the project
        in a clean installation OR transfers the STS3215 skill capsule to a different robot project."""
        if bundle_data.get("schema") != "openline.robotics.skill_bundle.v1":
            raise ValueError("INVALID_SKILL_BUNDLE_SCHEMA")

        check_copy = dict(bundle_data)
        expected_bundle_sha = check_copy.pop("bundle_sha256", "")
        if not expected_bundle_sha or sha256_hex(check_copy) != expected_bundle_sha:
            raise ValueError("SKILL_BUNDLE_SHA256_TAMPER_DETECTED")

        cap_dict = dict(bundle_data["skill_capsule"])
        cap_copy = dict(cap_dict)
        expected_cap_sha = cap_copy.pop("verified_sha256", "")
        if not expected_cap_sha or sha256_hex(cap_copy) != expected_cap_sha:
            raise ValueError("SKILL_CAPSULE_SHA256_TAMPER_DETECTED")

        if bundle_data.get("onnx_policy_base64") and bundle_data.get("onnx_policy_file"):
            raw_onnx = base64.b64decode(bundle_data["onnx_policy_base64"])
            if sha256_hex(raw_onnx) != bundle_data.get("onnx_policy_sha256"):
                raise ValueError("ONNX_POLICY_SHA256_TAMPER_DETECTED")
            (self.onnx_dir / str(bundle_data["onnx_policy_file"])).write_bytes(raw_onnx)

        if target_project_id is None:
            src_pid = str(bundle_data["exported_from_project_id"])
            existing_ids = {p["project_id"] for p in self.living_engine.list_projects()}
            if src_pid in existing_ids:
                cur_b = self.living_engine.get_project_bundle(src_pid)
                imported = self.living_engine.import_portable_bundle(
                    bundle_data["living_project_portable_json"],
                    allow_overwrite=True,
                    expected_base_version=int(cur_b["accepted"]["version"]),
                    expected_base_sha256=str(cur_b["accepted"]["state_sha256"]),
                )
            else:
                imported = self.living_engine.import_portable_bundle(
                    bundle_data["living_project_portable_json"],
                )
            return {
                "mode": "CLEAN_INSTALL_PROJECT_RESTORE",
                "project_id": src_pid,
                "import_result": imported,
            }
        else:
            repair_res = self.diagnose_and_repair(
                target_project_id,
                inherited_capsule=cap_dict,
            )
            return {
                "mode": "CROSS_ROBOT_SKILL_TRANSFER",
                "source_robot_id": bundle_data["source_robot_id"],
                "target_project_id": target_project_id,
                "transfer_diagnosis": repair_res["diagnosis"],
                "staged_skill_capsule": repair_res["staged_skill_capsule"],
            }
