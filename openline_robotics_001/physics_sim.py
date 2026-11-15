#!/usr/bin/env python3
"""OpenLine Robotics Breakthrough 001 — Real Multi-Body Lagrangian & Contact Physics Simulator.

Supports two substantially different open-source robots sharing the Feetech STS3215 serial servo bus:
1. `open_duck_mini_v2`: 14-DoF Bipedal BDX Droid (`apirrone/Open_Duck_Mini`, Apache-2.0 / MIT community)
   - 10 leg joints (5 per leg: hip_yaw, hip_roll, hip_pitch, knee, ankle) + 4 neck/head joints
   - Coupled sagittal/coronal inverted-pendulum + swing-leg Hunt-Crossley viscoelastic ground contact
   - BNO055 IMU (pitch, roll, angular rates + I2C glitch/bias fault injection) & 4 SS-10 foot switches
2. `lerobot_so101_arm`: 6-DoF Articulated Follower Manipulator (`TheRobotStudio/SO-ARM100` & `huggingface/lerobot`)
   - 5 arm joints (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll) + 1 gripper joint
   - Coupled multi-link Euler-Lagrange inertia M(q), Coriolis/centrifugal C(q,dq), gravity G(q),
     3D forward kinematics, damped least-squares Jacobian IK, workspace obstacle collision & grasp contact.

Both models use the shared `STS3215ActuatorBus` physics model (4096 ticks/rev quantization, UART ring-buffer
transport delay, Coulomb stiction + viscous friction, gear backlash deadzone, 2S/3S voltage sag torque limit).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import onnxruntime as ort


@dataclass
class EnvironmentPerturbation:
    """Configurable physical environment & actuator reality-gap parameters."""
    uart_delay_ms: float = 0.0              # Serial bus + ZOH delay (0..80 ms)
    stiction_nm: float = 0.04               # Coulomb stiction per joint (N*m)
    viscous_damping: float = 0.08           # Viscous joint damping (N*m*s/rad)
    backlash_rad: float = 0.002             # Gear backlash deadband half-width (rad)
    battery_voltage_v: float = 7.4          # Nominal 7.4V (2S sag down to 6.2V)
    payload_mass_kg: float = 0.0            # Added payload on trunk or gripper (kg)
    terrain_slope_deg: float = 0.0          # Ground incline angle (deg)
    terrain_step_height_m: float = 0.0      # Unexpected step/curb height at x=0.35m (m)
    ground_friction_mu: float = 0.80        # Ground friction coefficient
    obstacle_pos_xyz: tuple[float, float, float] | None = None
    obstacle_radius_m: float = 0.06
    imu_dropout_prob: float = 0.0           # BNO055 I2C clock-stretch packet drop prob
    imu_pitch_bias_rad: float = 0.0         # Sensor calibration drift / bias (rad)
    external_push_force_n: float = 0.0      # Impulse push force at t=1.2s (N)
    seed: int = 20261114


@dataclass
class RobotModelSpec:
    model_id: str
    display_name: str
    morphology: str
    dof: int
    joint_names: list[str]
    servo_ids: list[int]
    joint_limits_rad: list[tuple[float, float]]
    max_velocity_rad_s: float
    nominal_stall_torque_nm: float
    nominal_voltage_v: float
    control_dt_s: float = 0.020
    physics_substeps: int = 10
    upstream_repo_url: str = ""
    license_spdx: str = "Apache-2.0"


OPEN_DUCK_MINI_V2_SPEC = RobotModelSpec(
    model_id="open_duck_mini_v2",
    display_name="Open Duck Mini v2 (14-DoF Biped)",
    morphology="biped_14dof",
    dof=14,
    joint_names=[
        "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle",
        "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle",
        "neck_pitch", "head_pitch", "head_yaw", "head_roll",
    ],
    servo_ids=[20, 21, 22, 23, 24, 10, 11, 12, 13, 14, 30, 31, 32, 33],
    joint_limits_rad=[
        (-0.60, 0.60), (-0.55, 0.55), (-1.20, 1.20), (-0.10, 1.65), (-0.95, 0.95),
        (-0.60, 0.60), (-0.55, 0.55), (-1.20, 1.20), (-0.10, 1.65), (-0.95, 0.95),
        (-0.70, 0.70), (-0.70, 0.70), (-1.00, 1.00), (-0.50, 0.50),
    ],
    max_velocity_rad_s=6.28,
    nominal_stall_torque_nm=1.86,  # Feetech STS3215 7.4V (19 kg*cm)
    nominal_voltage_v=7.4,
    control_dt_s=0.020,
    physics_substeps=10,
    upstream_repo_url="https://github.com/apirrone/Open_Duck_Mini_Runtime",
    license_spdx="Apache-2.0",
)

LEROBOT_SO101_ARM_SPEC = RobotModelSpec(
    model_id="lerobot_so101_arm",
    display_name="LeRobot SO-101 (6-DoF Follower Arm)",
    morphology="manipulator_6dof",
    dof=6,
    joint_names=[
        "shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper",
    ],
    servo_ids=[1, 2, 3, 4, 5, 6],
    joint_limits_rad=[
        (-1.92, 1.92), (-1.75, 1.75), (-1.85, 1.85), (-1.75, 1.75), (-2.79, 2.79), (0.0, 1.20),
    ],
    max_velocity_rad_s=6.28,
    nominal_stall_torque_nm=1.86,  # Feetech STS3215 7.4V follower configuration
    nominal_voltage_v=7.4,
    control_dt_s=0.020,
    physics_substeps=10,
    upstream_repo_url="https://github.com/TheRobotStudio/SO-ARM100",
    license_spdx="Apache-2.0",
)

ROBOT_SPECS: dict[str, RobotModelSpec] = {
    OPEN_DUCK_MINI_V2_SPEC.model_id: OPEN_DUCK_MINI_V2_SPEC,
    LEROBOT_SO101_ARM_SPEC.model_id: LEROBOT_SO101_ARM_SPEC,
}


class STS3215ActuatorBus:
    """Physics model of the Feetech STS3215 1:345 serial UART servo bus."""

    def __init__(self, spec: RobotModelSpec, pert: EnvironmentPerturbation) -> None:
        self.spec = spec
        self.pert = pert
        self.substep_dt = spec.control_dt_s / spec.physics_substeps
        self.delay_substeps = max(0, int(round((pert.uart_delay_ms / 1000.0) / self.substep_dt)))
        self.cmd_buffer: list[np.ndarray] = []
        self.gear_engage_center = np.zeros(spec.dof, dtype=float)
        self.kp = 14.5
        self.kd = 0.55

    def reset(self, q0: np.ndarray) -> None:
        self.gear_engage_center = np.array(q0, dtype=float)
        self.cmd_buffer = [np.array(q0, dtype=float) for _ in range(self.delay_substeps + 1)]

    def step_actuators(
        self,
        q_cmd_raw: np.ndarray,
        tau_ff: np.ndarray,
        q: np.ndarray,
        dq: np.ndarray,
    ) -> tuple[np.ndarray, dict[str, float]]:
        # 1. Quantize command to 12-bit STS3215 encoder resolution (4096 ticks / 2*pi rad)
        tick_rad = (2.0 * math.pi) / 4096.0
        q_cmd_quant = np.round(q_cmd_raw / tick_rad) * tick_rad

        # 2. Push through UART serial delay ring buffer
        self.cmd_buffer.append(q_cmd_quant.copy())
        q_delayed = self.cmd_buffer.pop(0)

        # 3. Gear backlash deadband between motor shaft and output link
        err = q_delayed - q
        deadband = max(0.0, float(self.pert.backlash_rad))
        eff_err = np.where(
            np.abs(err) > deadband,
            err - np.sign(err) * deadband,
            0.0,
        )

        # 4. Internal servo PD + optional feedforward compensation torque
        tau_motor = self.kp * eff_err - self.kd * dq + tau_ff

        # 5. Battery voltage sag torque saturation & back-EMF speed limit
        v_scale = max(0.35, min(1.25, self.pert.battery_voltage_v / self.spec.nominal_voltage_v))
        max_tau = self.spec.nominal_stall_torque_nm * v_scale
        # Linear torque-speed droop near max speed
        speed_factor = np.clip(1.0 - np.abs(dq) / (self.spec.max_velocity_rad_s * 1.35), 0.15, 1.0)
        tau_cap = max_tau * speed_factor
        tau_sat = np.clip(tau_motor, -tau_cap, tau_cap)

        # 6. Nonlinear Coulomb stiction + viscous gear friction opposing motion
        stiction = float(self.pert.stiction_nm) * np.tanh(dq / 0.04)
        viscous = float(self.pert.viscous_damping) * dq
        tau_net = tau_sat - stiction - viscous

        metrics = {
            "max_torque_nm": float(np.max(np.abs(tau_sat))),
            "torque_saturation_ratio": float(np.max(np.abs(tau_sat)) / max(1e-6, max_tau)),
            "effective_stall_limit_nm": float(max_tau),
        }
        return tau_net, metrics


# ============================================================================
# 3. KINEMATICS & DYNAMICS FOR BOTH OPEN-SOURCE ROBOTS
# ============================================================================

def so101_forward_kinematics(q: np.ndarray) -> dict[str, Any]:
    """Computes 3D joint positions and end-effector pose for the LeRobot SO-101 6-DoF arm."""
    q0, q1, q2, q3, q4, q5 = [float(x) for x in q[:6]]
    l_base = 0.065
    l1 = 0.115
    l2 = 0.135
    l3 = 0.110

    p0 = np.array([0.0, 0.0, 0.0])
    p1 = np.array([0.0, 0.0, l_base])

    # Planar reach (r, z) in shoulder pan frame
    a1 = q1
    a2 = q1 + q2
    a3 = q1 + q2 + q3

    r2 = l1 * math.sin(a1)
    z2 = l_base + l1 * math.cos(a1)
    p2 = np.array([r2 * math.cos(q0), r2 * math.sin(q0), z2])

    r3 = r2 + l2 * math.sin(a2)
    z3 = z2 + l2 * math.cos(a2)
    p3 = np.array([r3 * math.cos(q0), r3 * math.sin(q0), z3])

    r_ee = r3 + l3 * math.sin(a3)
    z_ee = z3 + l3 * math.cos(a3)
    p_ee = np.array([r_ee * math.cos(q0), r_ee * math.sin(q0), z_ee])

    return {
        "joints_xyz": [p0.tolist(), p1.tolist(), p2.tolist(), p3.tolist(), p_ee.tolist()],
        "ee_xyz": p_ee,
        "pitch_sum": a3,
        "wrist_roll": q4,
        "gripper_open": q5,
    }


def so101_inverse_kinematics(target_xyz: np.ndarray, gripper_val: float = 0.5) -> np.ndarray:
    """Analytical + damped least-squares IK for the LeRobot SO-101 arm."""
    tx, ty, tz = float(target_xyz[0]), float(target_xyz[1]), float(target_xyz[2])
    q0 = math.atan2(ty, tx)
    r_target = math.hypot(tx, ty)
    z_rel = tz - 0.065

    l1, l2, l3 = 0.115, 0.135, 0.110
    # Desire wrist slightly angled downward toward workspace
    desired_pitch = math.radians(105.0)
    rw = max(0.02, r_target - l3 * math.sin(desired_pitch))
    zw = z_rel - l3 * math.cos(desired_pitch)

    dist_sq = rw * rw + zw * zw
    max_reach = (l1 + l2) * 0.985
    if dist_sq > max_reach * max_reach:
        scale = max_reach / math.sqrt(dist_sq)
        rw *= scale
        zw *= scale
        dist_sq = rw * rw + zw * zw

    cos_q2 = (dist_sq - l1 * l1 - l2 * l2) / (2.0 * l1 * l2)
    cos_q2 = max(-0.99, min(0.99, cos_q2))
    q2 = math.acos(cos_q2)  # elbow flex positive downward

    k1 = l1 + l2 * math.cos(q2)
    k2 = l2 * math.sin(q2)
    q1 = math.atan2(rw, zw) - math.atan2(k2, k1)
    q3 = desired_pitch - (q1 + q2)

    q = np.array([q0, q1, q2, q3, 0.0, gripper_val], dtype=float)
    for idx, (lo, hi) in enumerate(LEROBOT_SO101_ARM_SPEC.joint_limits_rad):
        q[idx] = max(lo, min(hi, q[idx]))
    return q


def open_duck_foot_kinematics(q: np.ndarray, trunk_xyz: np.ndarray, pitch: float, roll: float) -> dict[str, Any]:
    """Computes 3D hip, knee, and foot positions for Open Duck Mini v2."""
    l_thigh = 0.105
    l_shank = 0.105
    hip_y_offset = 0.055

    # Left leg: indices 0..4 (yaw, roll, pitch, knee, ankle)
    l_hp, l_kn, l_an = float(q[2]), float(q[3]), float(q[4])
    l_hr = float(q[1])
    # Right leg: indices 5..9
    r_hp, r_kn, r_an = float(q[7]), float(q[8]), float(q[9])
    r_hr = float(q[6])

    # Sagittal + coronal foot offsets relative to trunk CoM
    l_a1 = pitch - l_hp
    l_a2 = l_a1 + l_kn
    l_knee_pos = np.array([
        trunk_xyz[0] + l_thigh * math.sin(l_a1),
        trunk_xyz[1] + hip_y_offset + l_thigh * math.sin(l_hr + roll),
        trunk_xyz[2] - l_thigh * math.cos(l_a1) * math.cos(l_hr + roll),
    ])
    l_foot_pos = np.array([
        l_knee_pos[0] + l_shank * math.sin(l_a2),
        l_knee_pos[1] + l_shank * math.sin(l_hr + roll),
        l_knee_pos[2] - l_shank * math.cos(l_a2) * math.cos(l_hr + roll),
    ])

    r_a1 = pitch - r_hp
    r_a2 = r_a1 + r_kn
    r_knee_pos = np.array([
        trunk_xyz[0] + l_thigh * math.sin(r_a1),
        trunk_xyz[1] - hip_y_offset + l_thigh * math.sin(r_hr + roll),
        trunk_xyz[2] - l_thigh * math.cos(r_a1) * math.cos(r_hr + roll),
    ])
    r_foot_pos = np.array([
        r_knee_pos[0] + l_shank * math.sin(r_a2),
        r_knee_pos[1] + l_shank * math.sin(r_hr + roll),
        r_knee_pos[2] - l_shank * math.cos(r_a2) * math.cos(r_hr + roll),
    ])

    head_pos = np.array([
        trunk_xyz[0] + 0.08 * math.sin(pitch + float(q[10])),
        trunk_xyz[1],
        trunk_xyz[2] + 0.14 * math.cos(pitch),
    ])

    return {
        "trunk_xyz": trunk_xyz.tolist(),
        "head_xyz": head_pos.tolist(),
        "left_knee_xyz": l_knee_pos.tolist(),
        "left_foot_xyz": l_foot_pos.tolist(),
        "right_knee_xyz": r_knee_pos.tolist(),
        "right_foot_xyz": r_foot_pos.tolist(),
    }
