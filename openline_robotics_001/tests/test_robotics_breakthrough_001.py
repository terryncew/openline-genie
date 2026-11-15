#!/usr/bin/env python3
"""OpenLine Robotics Breakthrough 001 — Comprehensive Unit, Adversarial & E2E Test Suite."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import threading
import tempfile
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import numpy as np

from openline_robotics_001.physics_sim import (
    EnvironmentPerturbation,
    LEROBOT_SO101_ARM_SPEC,
    OPEN_DUCK_MINI_V2_SPEC,
    STS3215ActuatorBus,
    so101_forward_kinematics,
    so101_inverse_kinematics,
)
from openline_robotics_001.emergence_mechanism import (
    ActuatorBusReflexCapsule,
    diagnose_and_repair_skill,
    simulate_open_duck_episode,
    simulate_so101_arm_episode,
)
from openline_robotics_001.hardware_safety_adapter import (
    HardwareCommandEnvelope,
    HardwareSafetyBoundaryAdapter,
    HardwareSafetyRefused,
)
from openline_robotics_001.robotics_studio_engine import OpenLineRoboticsProductEngine
from openline_robotics_001.unfamiliar_dogfood_suite import run_unfamiliar_dogfood_suite
from openline_robotics_001.independent_evaluator import run_independent_acceptance_evaluation
from openline_robotics_001.robotics_studio_server import HTTPServer, make_handler


class TestOpenLineRoboticsBreakthrough001(unittest.TestCase):
    def test_01_sts3215_actuator_bus_and_ik_accuracy(self) -> None:
        pert = EnvironmentPerturbation(uart_delay_ms=20.0, stiction_nm=0.10, backlash_rad=0.01)
        bus = STS3215ActuatorBus(OPEN_DUCK_MINI_V2_SPEC, pert)
        q0 = np.zeros(14, dtype=float)
        bus.reset(q0)
        tau, metrics = bus.step_actuators(np.ones(14) * 0.2, np.zeros(14), q0, np.zeros(14))
        self.assertEqual(len(tau), 14)
        self.assertGreaterEqual(metrics["effective_stall_limit_nm"], 1.5)

        for target in [(0.24, -0.10, 0.06), (0.22, 0.14, 0.08), (0.20, 0.15, 0.085)]:
            arr = np.array(target, dtype=float)
            q_ik = so101_inverse_kinematics(arr)
            fk = so101_forward_kinematics(q_ik)["ee_xyz"]
            self.assertLess(float(np.linalg.norm(fk - arr)), 1e-4)

    def test_02_emergence_diagnosis_falsification_and_repair(self) -> None:
        pert = EnvironmentPerturbation(
            uart_delay_ms=44.0,
            stiction_nm=0.22,
            backlash_rad=0.018,
            battery_voltage_v=6.5,
            payload_mass_kg=0.32,
            terrain_slope_deg=7.5,
            terrain_step_height_m=0.022,
            imu_dropout_prob=0.08,
            external_push_force_n=1.2,
        )
        diag = diagnose_and_repair_skill("open_duck_mini_v2", pert)
        alts = diag["alternatives_comparison"]
        self.assertFalse(alts["B0_NOMINAL"]["task_success"])
        self.assertFalse(alts["B1_HIGH_GAIN_PID_TWISTMUX"]["task_success"])
        self.assertFalse(alts["C1_NAIVE_UNCOMPENSATED_DOB"]["task_success"])
        self.assertTrue(alts["C2_PR_CRDO_INVENTION"]["task_success"])
        self.assertEqual(diag["certification"]["final_disposition"], "ADOPT_CERTIFIED_DISCOVERY")
        self.assertEqual(
            diag["causal_isomorphism_gate"]["cross_robot_sts3215_transfer"]["disposition"],
            "VERIFIED_CAUSAL_ISOMORPHISM",
        )
        self.assertEqual(
            diag["causal_isomorphism_gate"]["rejected_false_metaphor_control"]["disposition"],
            "STRUCTURAL_RHYME_ONLY_REJECTED",
        )

    def test_03_hardware_safety_boundary_adapter_invariants(self) -> None:
        adapter = HardwareSafetyBoundaryAdapter("lerobot_so101_arm")
        base_cmd = HardwareCommandEnvelope(
            robot_id="lerobot_so101_arm",
            sequence_id=1,
            timestamp_monotonic_ms=1000.0,
            operator_authorized=True,
            permit_id="permit-1",
            permit_signature_valid=True,
            policy_verified_in_sim=True,
            capsule_sha256="hash-1",
            expected_capsule_sha256="hash-1",
            target_positions_rad=[0.0, 0.3, 0.8, 0.4, 0.0, 0.5],
            target_velocities_rad_s=[0.5] * 6,
            target_torques_nm=[0.3] * 6,
        )
        res = adapter.validate_and_frame_command(base_cmd, now_monotonic_ms=1010.0)
        self.assertEqual(res["status"], "ADMITTED_TO_ADAPTER")
        self.assertFalse(res["real_world_transfer_claimed"])

        # Replayed sequence ID refused
        with self.assertRaises(HardwareSafetyRefused):
            adapter.validate_and_frame_command(base_cmd, now_monotonic_ms=1015.0)

        # Joint limit violation refused
        bad_pos = copy.deepcopy(base_cmd)
        bad_pos.sequence_id = 2
        bad_pos.target_positions_rad[0] = 3.14  # Exceeds 1.92 rad shoulder_pan limit
        with self.assertRaises(HardwareSafetyRefused):
            adapter.validate_and_frame_command(bad_pos, now_monotonic_ms=1020.0)

        # Unverified policy refused
        unver = copy.deepcopy(base_cmd)
        unver.sequence_id = 3
        unver.policy_verified_in_sim = False
        with self.assertRaises(HardwareSafetyRefused):
            adapter.validate_and_frame_command(unver, now_monotonic_ms=1025.0)

    def test_04_product_engine_reject_preserves_accepted_and_cross_robot_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            eng1 = OpenLineRoboticsProductEngine(tmp1)
            d0 = eng1.get_project_detail("proj-open-duck-mini-v2")
            sha0 = d0["accepted_sha256"]

            # Stage and reject proposal -> accepted sha256 must be 100% unchanged
            eng1.define_goal_and_environment("proj-open-duck-mini-v2", goal_updates={"target_distance_m": 0.99})
            eng1.reject_proposal("proj-open-duck-mini-v2", reason="Test rejection")
            d1 = eng1.get_project_detail("proj-open-duck-mini-v2")
            self.assertEqual(d1["accepted_sha256"], sha0)
            self.assertGreaterEqual(len(d1["rejected"]), 1)

            # Diagnose, repair, accept, and export
            eng1.diagnose_and_repair("proj-open-duck-mini-v2")
            acc = eng1.accept_proposal("proj-open-duck-mini-v2")
            self.assertNotEqual(acc["state_sha256"], sha0)

            bundle = eng1.export_skill_bundle("proj-open-duck-mini-v2")
            eng2 = OpenLineRoboticsProductEngine(tmp2)
            xfer = eng2.import_skill_bundle(bundle, target_project_id="proj-lerobot-so101-arm")
            self.assertEqual(xfer["mode"], "CROSS_ROBOT_SKILL_TRANSFER")
            self.assertLessEqual(xfer["transfer_diagnosis"]["evaluation_calls_spent"], 8)

    def test_05_unfamiliar_dogfood_and_independent_acceptance_suites(self) -> None:
        dogfood = run_unfamiliar_dogfood_suite()
        self.assertEqual(dogfood["controller_scoreboard"]["C2_PR_CRDO_INVENTION"]["tasks_succeeded"], 6)
        self.assertEqual(dogfood["controller_scoreboard"]["C2_PR_CRDO_INVENTION"]["total_constraint_violations"], 0)
        self.assertTrue(dogfood["resilience_and_fault_tests"]["sigkill_worker_interruption_and_recovery"]["accepted_sha256_preserved_exact"])
        self.assertTrue(dogfood["resilience_and_fault_tests"]["emergency_stop_and_latch"]["engine_mutation_blocked_while_stopped"])
        self.assertEqual(dogfood["resilience_and_fault_tests"]["decision_recall_on_calibration_change"]["recall_standing_after_change"], "REOPEN")
        self.assertTrue(dogfood["resilience_and_fault_tests"]["corrupted_bundle_and_clean_install_transfer"]["tampered_capsule_rejected_fail_closed"])

        acceptance = run_independent_acceptance_evaluation()
        self.assertTrue(acceptance["overall_acceptance_passed"])

    def test_06_live_http_server_and_csrf_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            eng = OpenLineRoboticsProductEngine(tmp)
            html_p = Path(tmp) / "index.html"
            html_p.write_text("<html><body>Robotics Studio</body></html>", encoding="utf-8")
            server = HTTPServer(("127.0.0.1", 0), make_handler(eng, html_p))
            port = server.server_port
            th = threading.Thread(target=server.serve_forever, daemon=True)
            th.start()
            try:
                # 1. GET state
                with urlopen(f"http://127.0.0.1:{port}/api/robotics/state") as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(len(data["projects"]), 2)

                # 2. Cross-origin POST must be refused (403)
                req_csrf = Request(
                    f"http://127.0.0.1:{port}/api/robotics/diagnose_repair",
                    data=b'{"project_id":"proj-open-duck-mini-v2"}',
                    headers={"Content-Type": "application/json", "Origin": "https://evil.example.com"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req_csrf)
                self.assertEqual(ctx.exception.code, 403)

                # 3. Valid loopback POST diagnose_repair + accept
                req_ok = Request(
                    f"http://127.0.0.1:{port}/api/robotics/diagnose_repair",
                    data=b'{"project_id":"proj-open-duck-mini-v2"}',
                    headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"},
                    method="POST",
                )
                with urlopen(req_ok) as resp:
                    self.assertEqual(resp.status, 200)
                    r_json = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(r_json["repaired_episode"]["task_success"])
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
