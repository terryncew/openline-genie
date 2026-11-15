# OpenLine Robotics Studio — Sim2Real Skill Forge & Verified Reflex Runtime (`openline_robotics_001`)

- **Program**: `ARGON — OPENLINE ROBOTICS BREAKTHROUGH 001`
- **Candidate Version**: `1.0.0-rc1` (integrated into this repository; does not modify the frozen six-application Genie release or Advocate Case Packet 001)
- **License**: `Apache-2.0`
- **Paid External API / Hardware Cost**: `$0.00` (100% local-first Python + `onnxruntime` + browser HTML5 Canvas visualizer)

> **In plain language:** Design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls. Pick a robot, set a goal, try different ways of controlling it in a simulator, see what fails and why, fix the failure, keep the result only when you accept it, and move a working skill from one robot to another. Nothing here drives a physical robot.

## 1. What this is (`THE PRODUCT`)

**OpenLine Robotics Studio** is a complete, local-first open-source robotics application and runtime that lets students, researchers, and robotics builders:
1. **Select or Create a Robot Project**: Out-of-the-box support for two substantially different open-source robots sharing the [Feetech STS3215](https://orobot.io/o/program/BROKER-2/open-duck-mini) 1:345 serial servo bus:
   - **[Open Duck Mini v2](https://github.com/apirrone/Open_Duck_Mini)** ([Runtime](https://github.com/apirrone/Open_Duck_Mini_Runtime), 14-DoF Bipedal BDX Droid: 10 leg servos + 4 neck/head servos, BNO055 I2C IMU, 4 foot switches).
   - **[Hugging Face LeRobot SO-101](https://github.com/huggingface/lerobot)** ([SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100), 6-DoF Articulated Follower Arm: 5 arm joints + 1 gripper).
2. **Define a Goal & Physical Reality-Gap Perturbations**: Configure walking distance, 3D pick/place coordinates, UART serial bus latency (`0–60 ms`), Coulomb stiction, gear backlash, 2S battery voltage sag (`5.8–7.4 V`), payload mass, terrain slope, curb steps, and 3D workspace obstacles.
3. **Build or Import a Robot Skill**: Execute analytical Placo/IK controllers, real `onnxruntime` (`IR v8`, `Opset 13`) neural policies, or portable `PR-CRDO` Reflex Capsules.
4. **Execute in a Real Physics Simulator**: Continuous-time sub-stepped Lagrangian & viscoelastic contact dynamics (`physics_sim.py`, $\Delta t = 2\text{ ms}$, $50\text{ Hz}$ control loop) + interactive HTML5 Canvas visualizer (`openline_robotics_studio.html`).
5. **Inspect Physical Constraints & Negative Findings**: View `BUCSW` binding constraint slack (`check_constraint_and_goodhart_gate`), phase-stability trajectories, and the append-only Negative Findings Ledger.
6. **Diagnose & Repair Failures**: One-click counterfactual bottleneck unclamping across 5 physical disturbance axes (`diagnose_and_repair_skill`) that automatically synthesizes and stages a repaired `PR-CRDO` skill capsule.
7. **Preserve a Verified Result Under Receiver Authority**: Stage drafts in `EXPLORATORY`, commit to `ACCEPTED` with an Ed25519 receipt signed by `ReceiverGuard` (`genie_state.sqlite`), trigger `Decision Recall` (`CURRENT -> REOPEN`) when sensor calibration or payload assumptions shift, and enforce monotonic `STOP`.
8. **Export & Transfer Across Robots**: Export a SHA-256-verified `openline.robotics.skill_bundle.v1` JSON + ONNX bundle and transfer the learned STS3215 actuator-bus & reflex capsule from `Open Duck Mini v2` directly to `LeRobot SO-101 Arm` (cutting adaptation evaluations from `21 -> 8` and calibration probes from `16 -> 2`, an **`8.0x` probe reduction**).

### Two simulations, read this first

There are two simulations in this package, and they are not the same thing:

- **The Python engine is authoritative.** `robotics_studio_engine.py` runs the real physics simulator (`physics_sim.py`) and the real ONNX policy through `onnxruntime`. Every verified result, receipt, export, and import comes from this engine — via the studio server API or `python3 -m openline_robotics_001.robotics_studio_server --verify-all`.
- **The page in your browser is a simplified visualization.** `openline_robotics_studio.html` replays the same ideas with a small JavaScript model so you can see the robot move and try settings quickly. Its numbers are illustrative: its Accept/Reject buttons change only the page's own copy of the project, its hardware-adapter panel shows a canned packet, and its draft export carries a browser-side draft check value (not a SHA-256) that the server will not import. Use **Get Server-Verified Export** in the export tab for a bundle the server can import. The page says so in its safety banner.

## 2. Quick 30-Second Installation & Launch

```bash
# 1. From the repository root, install the extra runtime dependency
#    (numpy is already in requirements.txt; onnxruntime is robotics-only)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt onnxruntime
#    or, without a venv: pip install --user onnxruntime

# 2. Run the automated verification suite (Dogfood + 9-Gate Independent Acceptance)
.venv/bin/python -m openline_robotics_001.robotics_studio_server --verify-all

# 3. Run the unit, adversarial & HTTP E2E test suite (normal and -O optimized)
.venv/bin/python -m unittest discover -s openline_robotics_001/tests -p "test_*.py" -v
.venv/bin/python -O -m unittest discover -s openline_robotics_001/tests -p "test_*.py" -v

# 4. Launch the interactive local web studio on http://127.0.0.1:8796/robotics
./run_robotics_studio.sh
```

The studio is also linked from the Genie applications launcher: start the applications server (`applications/genie_server.py`, port 8795), open `http://127.0.0.1:8795/products`, and follow the **Robotics Studio** entry (route `/robotics`), which points at the studio on port 8796.

### Sample projects

Two ready-made projects load on first launch:

- **Open Duck Mini v2 — Uneven Slope & Curb Locomotion** (`proj-open-duck-mini-v2`): walk 0.58 m in 4 s over a 7.5° slope with a 2.2 cm curb step, 44 ms bus delay, and a 0.32 kg payload.
- **LeRobot SO-101 Arm — Obstacle-Aware Valve Pick & Place** (`proj-lerobot-so101-arm`): pick at (0.24, -0.10, 0.06) and place at (0.22, 0.14, 0.08) past a pipe obstacle, within 0.028 m.

Exported example bundles live in `openline_robotics_001/examples/` (`open_duck_mini_v2_repaired_bundle.json`, `lerobot_so101_transferred_bundle.json`). Import one through `POST /api/robotics/import` (see the API list in `robotics_studio_server.py`).

### A note on the page's styling

The workbench page loads its styling, fonts, and chart library from public CDNs (Tailwind, Chart.js, Google Fonts). With no network it still loads and runs; it looks plainer and the telemetry chart is skipped. The Python engine and API need no network at all.

## 3. Physical Safety Boundary (`SIMULATED_VERIFIED` vs. Hardware)

- **Simulation Acceptance != Physical Hardware Safety**: Results verified in simulation (`SIMULATED_VERIFIED`) never establish physical safety (ISO 10218 / IEC 61508). Physical-hardware behavior is **unverified**: the hardware adapter has been verified in dry-run only. No result in this package is a claim about a physical robot.
- **Hardware Integration Adapter (`openline_robotics_001/hardware_safety_adapter.py`)**:
  - Enforces joint position limits, velocity caps ($\le 6.28\text{ rad/s}$), and torque caps ($\le 1.86\text{ N}\cdot\text{m}$).
  - Refuses stale commands ($\text{age} > 100\text{ ms}$) and out-of-order/replayed sequence numbers.
  - Enforces a $150\text{ ms}$ communication heartbeat watchdog (`COMM_LOST_SAFE_HOLD_ZERO_VELOCITY`) and latching local Emergency Stop (`ESTOP_LATCHED_SAFE_HOLD`).
  - Requires explicit human operator authorization, `CURRENT` Recall standing, and simulation verification before framing any `Feetech STS3215 SYNC_WRITE (0x83)` or `ROS 2 JointTrajectory` message.
  - Permanently refuses to bypass manufacturer servo thermal/overload limits.
  - The adapter only **frames** messages in memory for inspection. It opens no serial port and talks to no hardware.

## 4. Security model (same as Genie)

- **Loopback only.** The studio server binds `127.0.0.1` (port 8796) and refuses any other `--host`, mirroring `genie_server.py`. Host and Origin checks apply to the API endpoints.
- **Single local operator.** Anyone who can reach the loopback port is the operator. There is no login; never expose the port beyond your own computer.
- **Human control is the product.** Simulation results are staged as drafts; nothing becomes accepted state until the operator accepts it, and accepting issues a signed receipt. STOP freezes state and blocks mutation until the operator clears it. There is no auto-accept path.
- **No paid calls, no network.** The engine runs locally with a $0 budget. It makes no outbound network calls.

## 5. What is vendored and why (`vendor_009/`)

The engine reuses the OpenLine 009 living-project machinery (`LivingProjectEngine`, `ReceiverGuard`, `RecallLedger`, `openline_research_kernel`) from `vendor_009/`, a verbatim copy of the 009 source this robotics work was built and tested against. It is **not** the same file as `applications/openline_009_living_project.py`: the applications copy is newer (it adds Neighborhood workspaces and a triage fix), so the robotics engine keeps its own tested copy rather than silently switching foundations. Do not edit `vendor_009/` to "sync" it with `applications/`; if the foundation ever changes, re-run the full robotics test suite and the independent acceptance evaluator first.

## 6. Evidence

- `ROBOTICS_BREAKTHROUGH_001_RECEIPTS.json` — the recorded dogfood + independent-acceptance receipts from the candidate (supporting evidence only; re-run `--verify-all` to reproduce them here).
- `SHA256SUMS.txt` — checksums for the files in this package (regenerate from inside this directory: `find . -type f ! -path "./SHA256SUMS.txt" | sort | xargs sha256sum > SHA256SUMS.txt`).
- `THIRD_PARTY_NOTICES.md` — upstream robotics projects and licenses.
