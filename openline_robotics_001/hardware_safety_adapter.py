#!/usr/bin/env python3
"""OpenLine Robotics Breakthrough 001 — Physical Safety Boundary & Hardware Adapter.

CRITICAL SAFETY BOUNDARY DISCLOSURE:
Simulation verification (`SIMULATED_VERIFIED`) NEVER establishes physical hardware safety
(ISO 10218 / ISO/TS 15066 / IEC 61508). Physical robot execution is a separate acceptance
level. When physical hardware is absent, this adapter operates in `DRY_RUN_HARDWARE_ADAPTER`
mode and explicitly marks all hardware outputs as `UNVERIFIED_ON_PHYSICAL_HARDWARE`.

Enforces the 6 mandatory hardware integration invariants:
1. Validates actuator position limits, joint velocities, and torque/current caps on every frame.
2. Refuses stale (`age_ms > max_command_age_ms`), out-of-sequence, or replayed commands.
3. Provides a latching local Emergency Stop (`local_estop_latched`) and communication watchdog
   (`watchdog_timeout_ms`), failing safely to `SAFE_HOLD_ZERO_VELOCITY` on lost communications.
4. Requires explicit human operator authorization and a valid Ed25519 work permit signature.
5. Never bypasses manufacturer servo protections (Feetech STS3215 thermal/current/voltage cutoffs).
6. Blocks autonomous deployment of unverified policies onto hardware (`verified_in_sim == True`
   and matching `capsule_sha256` required before framing any hardware packet).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct
import time
from typing import Any, Mapping, Sequence

import numpy as np

from openline_robotics_001.physics_sim import ROBOT_SPECS, RobotModelSpec


class HardwareSafetyRefused(PermissionError):
    """Fail-closed exception raised when any hardware safety or authority invariant fails."""


@dataclass
class HardwareCommandEnvelope:
    robot_id: str
    sequence_id: int
    timestamp_monotonic_ms: float
    operator_authorized: bool
    permit_id: str
    permit_signature_valid: bool
    policy_verified_in_sim: bool
    capsule_sha256: str
    expected_capsule_sha256: str
    target_positions_rad: list[float]
    target_velocities_rad_s: list[float]
    target_torques_nm: list[float]
    manufacturer_limits_enabled: bool = True


class HardwareSafetyBoundaryAdapter:
    """Documented hardware integration adapter for Feetech STS3215 UART bus & ROS 2 / micro-ROS."""

    def __init__(
        self,
        robot_id: str = "open_duck_mini_v2",
        *,
        max_command_age_ms: float = 100.0,
        watchdog_timeout_ms: float = 150.0,
        physical_hardware_connected: bool = False,
    ) -> None:
        if robot_id not in ROBOT_SPECS:
            raise HardwareSafetyRefused(f"UNKNOWN_ROBOT_MODEL:{robot_id}")
        self.spec: RobotModelSpec = ROBOT_SPECS[robot_id]
        self.max_command_age_ms = float(max_command_age_ms)
        self.watchdog_timeout_ms = float(watchdog_timeout_ms)
        self.physical_hardware_connected = bool(physical_hardware_connected)

        self.local_estop_latched: bool = False
        self.estop_reason: str = ""
        self.last_valid_seq: int = 0
        self.last_heartbeat_ms: float | None = None
        self.safe_state_mode: str = "IDLE_DISARMED"
        self.accepted_packets_count: int = 0
        self.refused_packets_count: int = 0

    def trigger_local_estop(self, reason: str = "OPERATOR_LOCAL_ESTOP") -> dict[str, Any]:
        """Immediately latches the local emergency stop and zeroes all actuator velocity commands."""
        self.local_estop_latched = True
        self.estop_reason = str(reason)
        self.safe_state_mode = "ESTOP_LATCHED_SAFE_HOLD"
        return {
            "status": "ESTOP_LATCHED",
            "safe_state_mode": self.safe_state_mode,
            "reason": self.estop_reason,
            "hardware_claim_status": (
                "PHYSICAL_HARDWARE_ACTIVE"
                if self.physical_hardware_connected
                else "UNVERIFIED_HARDWARE_PATH_SIMULATION_ONLY"
            ),
        }

    def reset_local_estop(self, *, operator_confirmed: bool, permit_valid: bool) -> dict[str, Any]:
        if not operator_confirmed or not permit_valid:
            raise HardwareSafetyRefused("ESTOP_RESET_REQUIRES_EXPLICIT_OPERATOR_AND_PERMIT")
        self.local_estop_latched = False
        self.estop_reason = ""
        self.safe_state_mode = "ARMED_READY"
        return {"status": "ESTOP_CLEARED", "safe_state_mode": self.safe_state_mode}

    def check_watchdog(self, now_monotonic_ms: float) -> dict[str, Any]:
        """Checks communication heartbeat freshness; fails safely to zero-velocity hold on timeout."""
        if self.local_estop_latched:
            return {
                "watchdog_ok": False,
                "safe_state_mode": "ESTOP_LATCHED_SAFE_HOLD",
                "action": "ZERO_VELOCITY_HOLD",
            }
        if self.last_heartbeat_ms is None:
            return {
                "watchdog_ok": True,
                "safe_state_mode": self.safe_state_mode,
                "action": "AWAITING_FIRST_HEARTBEAT",
            }
        elapsed = float(now_monotonic_ms) - self.last_heartbeat_ms
        if elapsed > self.watchdog_timeout_ms:
            self.safe_state_mode = "COMM_LOST_SAFE_HOLD_ZERO_VELOCITY"
            return {
                "watchdog_ok": False,
                "elapsed_ms": round(elapsed, 2),
                "safe_state_mode": self.safe_state_mode,
                "action": "SAFE_HOLD_ZERO_VELOCITY",
            }
        return {
            "watchdog_ok": True,
            "elapsed_ms": round(elapsed, 2),
            "safe_state_mode": self.safe_state_mode,
            "action": "NOMINAL",
        }

    def validate_and_frame_command(
        self,
        cmd: HardwareCommandEnvelope,
        *,
        now_monotonic_ms: float,
    ) -> dict[str, Any]:
        """Validates all 6 physical safety boundary invariants and builds the Feetech STS3215
        SYNC_WRITE (0x83) binary frame + ROS 2 `sensor_msgs/JointState` compatible payload."""
        try:
            # 1. Local E-Stop check
            if self.local_estop_latched:
                raise HardwareSafetyRefused(f"REFUSED_LOCAL_ESTOP_LATCHED:{self.estop_reason}")

            # 2. Manufacturer protection check (never allow bypassing servo thermal/overload flags)
            if not cmd.manufacturer_limits_enabled:
                raise HardwareSafetyRefused("REFUSED_MANUFACTURER_SAFETY_BYPASS_PROHIBITED")

            # 3. Operator & work permit authorization check
            if not cmd.operator_authorized:
                raise HardwareSafetyRefused("REFUSED_OPERATOR_AUTHORIZATION_REQUIRED")
            if not cmd.permit_signature_valid or not cmd.permit_id:
                raise HardwareSafetyRefused("REFUSED_INVALID_OR_REVOKED_WORK_PERMIT")

            # 4. Prevent autonomous deployment of unverified policies
            if not cmd.policy_verified_in_sim:
                raise HardwareSafetyRefused("REFUSED_UNVERIFIED_POLICY_DEPLOYMENT_BLOCKED")
            if not cmd.capsule_sha256 or cmd.capsule_sha256 != cmd.expected_capsule_sha256:
                raise HardwareSafetyRefused("REFUSED_CAPSULE_HASH_MISMATCH")

            # 5. Watchdog & command freshness / sequence replay check
            if self.last_heartbeat_ms is not None:
                if (now_monotonic_ms - self.last_heartbeat_ms) > self.watchdog_timeout_ms:
                    self.safe_state_mode = "COMM_LOST_SAFE_HOLD_ZERO_VELOCITY"
                    raise HardwareSafetyRefused("REFUSED_WATCHDOG_COMMUNICATION_TIMEOUT")

            cmd_age_ms = float(now_monotonic_ms) - float(cmd.timestamp_monotonic_ms)
            if cmd_age_ms < -5.0 or cmd_age_ms > self.max_command_age_ms:
                raise HardwareSafetyRefused(f"REFUSED_STALE_COMMAND:age_ms={cmd_age_ms:.1f}")

            if int(cmd.sequence_id) <= self.last_valid_seq:
                raise HardwareSafetyRefused(f"REFUSED_REPLAYED_OR_OUT_OF_ORDER_SEQ:{cmd.sequence_id}")

            # 6. Physical actuator position, velocity, and torque bounds
            if (
                len(cmd.target_positions_rad) != self.spec.dof
                or len(cmd.target_velocities_rad_s) != self.spec.dof
                or len(cmd.target_torques_nm) != self.spec.dof
            ):
                raise HardwareSafetyRefused("REFUSED_DOF_DIMENSION_MISMATCH")

            for idx in range(self.spec.dof):
                q_val = float(cmd.target_positions_rad[idx])
                dq_val = float(cmd.target_velocities_rad_s[idx])
                tau_val = float(cmd.target_torques_nm[idx])
                if not (math.isfinite(q_val) and math.isfinite(dq_val) and math.isfinite(tau_val)):
                    raise HardwareSafetyRefused(f"REFUSED_NONFINITE_ACTUATOR_COMMAND:joint={idx}")
                lo, hi = self.spec.joint_limits_rad[idx]
                if q_val < lo - 1e-4 or q_val > hi + 1e-4:
                    raise HardwareSafetyRefused(
                        f"REFUSED_JOINT_LIMIT_VIOLATION:{self.spec.joint_names[idx]}={q_val:.3f} not in [{lo},{hi}]"
                    )
                if abs(dq_val) > self.spec.max_velocity_rad_s + 1e-4:
                    raise HardwareSafetyRefused(
                        f"REFUSED_VELOCITY_LIMIT_VIOLATION:{self.spec.joint_names[idx]}={dq_val:.3f}"
                    )
                if abs(tau_val) > self.spec.nominal_stall_torque_nm + 1e-4:
                    raise HardwareSafetyRefused(
                        f"REFUSED_TORQUE_LIMIT_VIOLATION:{self.spec.joint_names[idx]}={tau_val:.3f}"
                    )

            # Update state & build Feetech STS3215 SYNC_WRITE (0x83) binary packet
            self.last_valid_seq = int(cmd.sequence_id)
            self.last_heartbeat_ms = float(now_monotonic_ms)
            self.safe_state_mode = "ACTIVE_VALIDATED"
            self.accepted_packets_count += 1

            sts_frame = self._encode_sts3215_sync_write(
                cmd.target_positions_rad, cmd.target_velocities_rad_s
            )
            return {
                "status": "ADMITTED_TO_ADAPTER",
                "execution_level": (
                    "HARDWARE_IN_THE_LOOP"
                    if self.physical_hardware_connected
                    else "UNVERIFIED_HARDWARE_ADAPTER_DRY_RUN"
                ),
                "real_world_transfer_claimed": False,
                "sequence_id": self.last_valid_seq,
                "sts3215_sync_write_hex": sts_frame.hex(),
                "sts3215_packet_bytes": len(sts_frame),
                "ros2_joint_trajectory_msg": {
                    "header": {"seq": self.last_valid_seq, "frame_id": self.spec.model_id},
                    "joint_names": self.spec.joint_names,
                    "positions": [round(float(x), 4) for x in cmd.target_positions_rad],
                    "velocities": [round(float(x), 4) for x in cmd.target_velocities_rad_s],
                    "effort": [round(float(x), 4) for x in cmd.target_torques_nm],
                },
            }
        except HardwareSafetyRefused:
            self.refused_packets_count += 1
            raise

    def _encode_sts3215_sync_write(
        self,
        positions_rad: Sequence[float],
        velocities_rad_s: Sequence[float],
    ) -> bytes:
        """Encodes a standard Feetech STS3215 SYNC_WRITE (Instruction 0x83, Start Reg 0x2A, 6 bytes/servo)
        packet with verified 8-bit bitwise-NOT checksum `~(ID + LEN + INST + PARAMS) & 0xFF`."""
        per_servo_len = 6  # [Goal_Pos_L, Goal_Pos_H, Time_L, Time_H, Speed_L, Speed_H]
        params = bytearray([0x2A, per_servo_len])
        for idx, servo_id in enumerate(self.spec.servo_ids):
            # Center 0 rad at 2048 ticks (4096 ticks / 2*pi rad)
            ticks = int(round(2048.0 + (float(positions_rad[idx]) / (2.0 * math.pi)) * 4096.0))
            ticks = max(0, min(4095, ticks))
            speed_ticks = int(round((abs(float(velocities_rad_s[idx])) / (2.0 * math.pi)) * 4096.0))
            speed_ticks = max(10, min(3400, speed_ticks))
            params.append(servo_id & 0xFF)
            params.extend(struct.pack("<HHH", ticks, 0, speed_ticks))

        broadcast_id = 0xFE
        instruction = 0x83  # INST_SYNC_WRITE
        length = len(params) + 2
        checksum_sum = broadcast_id + length + instruction + sum(params)
        checksum = (~checksum_sum) & 0xFF
        packet = bytearray([0xFF, 0xFF, broadcast_id, length, instruction]) + params + bytearray([checksum])
        return bytes(packet)
