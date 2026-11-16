# OpenLine Argon Robotics Studio — Sim2Real Skill Forge & Verified Reflex Runtime (`openline_robotics_001`)

- **Program**: `ARGON — OPENLINE ROBOTICS BREAKTHROUGH 001`
- **Candidate Version**: `1.0.0-rc1` (Preserved as a separate development candidate; does not modify the frozen six-application Genie release or Advocate Case Packet 001)
- **License**: `Apache-2.0`
- **Paid External API / Hardware Lock-In Cost**: `$0.00` (100% local-first Python + C++ `onnxruntime` + browser HTML5 Canvas simulator)

---

## 1. What Was Built (`THE PRODUCT`)

**OpenLine Argon Robotics Studio** is a complete, local-first open-source robotics application and runtime that lets students, researchers, and robotics builders:
1. **Select or Create a Robot Project**: Out-of-the-box support for two substantially different open-source robots sharing the [Feetech STS3215](https://orobot.io/o/program/BROKER-2/open-duck-mini) 1:345 serial servo bus:
   - **[Open Duck Mini v2](https://github.com/apirrone/Open_Duck_Mini)** ([Runtime](https://github.com/apirrone/Open_Duck_Mini_Runtime), 14-DoF Bipedal BDX Droid: 10 leg servos + 4 neck/head servos, BNO055 I2C IMU, 4 foot switches).
   - **[Hugging Face LeRobot SO-101](https://github.com/huggingface/lerobot)** ([SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100), 6-DoF Articulated Follower Arm: 5 arm joints + 1 gripper).
2. **Define a Goal & Physical Reality-Gap Perturbations**: Configure walking distance, 3D pick/place coordinates, UART serial bus latency (`0–60 ms`), Coulomb stiction, gear backlash, 2S battery voltage sag (`5.8–7.4 V`), payload mass, terrain slope, curb steps, and 3D workspace obstacles.
3. **Build or Import a Robot Skill**: Execute analytical Placo/IK controllers, real C++ `onnxruntime` (`IR v8`, `Opset 13`) neural policies, or portable `PR-CRDO` Reflex Capsules.
4. **Execute in a Real Physics Simulator**: Continuous-time sub-stepped Lagrangian & viscoelastic contact dynamics (`physics_sim.py`, $\Delta t = 2\text{ ms}$, $50\text{ Hz}$ control loop) + interactive HTML5 Canvas visualizer (`openline_robotics_studio.html`).
5. **Inspect Physical Constraints & Negative Findings**: View `BUCSW` binding constraint slack (`check_constraint_and_goodhart_gate`), phase-stability trajectories, and the append-only Negative Findings Ledger.
6. **Diagnose & Repair Failures**: One-click counterfactual bottleneck unclamping across 5 physical disturbance axes (`diagnose_and_repair_skill`) that automatically synthesizes and stages a repaired `PR-CRDO` skill capsule.
7. **Preserve a Verified Result Under Receiver Authority**: Stage drafts in `EXPLORATORY`, commit to `ACCEPTED` with an Ed25519 receipt signed by `ReceiverGuard` (`genie_state.sqlite`), trigger `Decision Recall` (`CURRENT -> REOPEN`) when sensor calibration or payload assumptions shift, and enforce monotonic `STOP`.
8. **Export & Transfer Across Robots**: Export a SHA-256-verified `openline.robotics.skill_bundle.v1` JSON + ONNX bundle and transfer the learned STS3215 actuator-bus & reflex capsule from `Open Duck Mini v2` directly to `LeRobot SO-101 Arm` (cutting adaptation evaluations from `21 -> 8` and calibration probes from `16 -> 2`, an **`8.0x` probe reduction**).

---

## 2. Quick 30-Second Installation & Launch

```bash
# 1. Unpack the standalone candidate archive into a clean directory
mkdir -p ~/openline_robotics_candidate
unzip -q OPENLINE_ROBOTICS_BREAKTHROUGH_001_CANDIDATE.zip -d ~/openline_robotics_candidate
cd ~/openline_robotics_candidate

# 2. Run the automated verification suite (Dogfood + 9-Gate Independent Acceptance)
python3 -m openline_robotics_001.robotics_studio_server --verify-all

# 3. Run the unit, adversarial & HTTP E2E test suite (normal and -O optimized)
python3 -m unittest discover -s openline_robotics_001/tests -p "test_*.py" -v
python3 -O -m unittest discover -s openline_robotics_001/tests -p "test_*.py" -v

# 4. Launch the interactive local web studio on http://127.0.0.1:8796/robotics
./openline_robotics_001/run_robotics_studio.sh
```

---

## 3. Physical Safety Boundary (`SIMULATED_VERIFIED` vs. Hardware)

- **Simulation Acceptance != Physical Hardware Safety**: Results verified in simulation (`SIMULATED_VERIFIED`) never establish physical safety (ISO 10218 / IEC 61508).
- **Hardware Integration Adapter (`openline_robotics_001/hardware_safety_adapter.py`)**:
  - Enforces joint position limits, velocity caps ($\le 6.28\text{ rad/s}$), and torque caps ($\le 1.86\text{ N}\cdot\text{m}$).
  - Refuses stale commands ($\text{age} > 100\text{ ms}$) and out-of-order/replayed sequence numbers.
  - Enforces a $150\text{ ms}$ communication heartbeat watchdog (`COMM_LOST_SAFE_HOLD_ZERO_VELOCITY`) and latching local Emergency Stop (`ESTOP_LATCHED_SAFE_HOLD`).
  - Requires explicit human operator authorization, `CURRENT` Recall standing, and simulation verification before framing any `Feetech STS3215 SYNC_WRITE (0x83)` or `ROS 2 JointTrajectory` message.
  - Permanently refuses to bypass manufacturer servo thermal/overload limits.
