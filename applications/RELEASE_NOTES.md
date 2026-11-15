# OpenLine Genie v1.1.0-RC1 — Public Release Notes

## Highlights
- **Advocate Case Packets (new, inside Advocate)**: Portable, verifiable case records. Original documents are kept byte-for-byte with SHA-256 checksums; claims carry exact source citations; rule authority is checked in four tiers (verified, user-supplied, outdated/superseded, unverified); deadlines are never invented (fail-closed to `NO_KNOWN_DEADLINE_DO_NOT_INVENT`); new evidence reopens affected conclusions through Decision Recall while the original record stays intact. A packet exports as an offline-readable HTML dossier plus a self-contained signed `.zip` bundle, and imports into a clean installation with the original record reconstructed from the packet alone. A signature proves record integrity and human approval at a point in time — not legal truth, not legal advice, no guaranteed outcome.
- **Robotics Studio (new, seventh application)**: Design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls, for Open Duck Mini v2 and LeRobot SO-101. Runs as its own loopback-only server on port 8796 (`./run_robotics_studio.sh`), linked from the applications launcher. **Simulation only**: every result is verified in simulation and never establishes physical hardware safety; the hardware adapter is verified in dry-run only and nothing here drives a physical robot.
- **All six v1.0.0-rc1 applications preserved** with their workflows, receipts, and limitations unchanged.

## Measured results (2026-11-15, this tree)
- Applications suite: 186 Python tests ran, 175 passed, 1 failure, 5 errors, 5 skipped; Node 11 passed, 0 failed. The 1 failure and 5 errors are browser tests needing Chrome (not installed here) and 2 tests checking external archive files not in the package — recorded NOT VERIFIED, never passed.
- Robotics suite: 6 passed, 0 failed, including the unfamiliar dogfood suite and the 9-gate independent acceptance (controller comparisons reproduced, cross-robot transfer in 8 evaluations vs 21 de novo, STOP, authorization refusal, corrupted-import rejection).
- Case Packet module: 4-case Installation A → Installation B handoffs pass; 12/12 adversarial vectors blocked; tampered packets rejected. A fresh fictional dispute was dogfooded end to end (export, clean-install import, contradictory evidence, Decision Recall, original record preserved).
- Live smoke on the release tree: applications server binds loopback-only; `/products`, `/robotics`, and `/api/advocate/case_packets` return 200; Neighborhood identity re-attack byte-identical across claimed identities; foreign Host returns 403. Robotics server binds loopback-only; `/robotics` returns 200; real simulations succeed for both robots.

## Limitations (unchanged from v1.0.0-rc1, plus)
- Browser end-to-end tests need Chrome/Chromium (not verified here). macOS/Windows installs, iPhone Safari, and uncoached human testing remain not tested.
- Robotics results are simulation only. Physical-hardware behavior is unverified; do not connect this software to a physical robot on the strength of these results.
- The Case Packet workbench browser test needs Chromium (not verified here); the packet engine itself is verified by the passing module tests and the dogfood run.

---

# OpenLine Genie v1.0.0-RC1 — Public Release Notes

## Highlights
- **Five Complete Applications in One Local Suite (`/products`)**:
  1. **Energy Commons**: 10-year cooperative energy & hot-water cash-flow comparison with a calculation cross-check (each 10-year cost recomputed from the reported figures; agreement within $0.05), 6-scenario sensitivity matrix, and 4 built-in guards against unrealistic vendor assumptions.
  2. **Advocate**: Institutional appeal packet organizer with conservative deadline calculation, three-bucket evidence separation (`Verified fact`, `Unverified claim`, `Missing information`), rule effective-date verification, and automatic PII redaction.
  3. **Capability Commons**: Portable library of executable community projects (Water Filtration Hub, Cooperative Childcare & Kitchen, Building Weatherization & Workshop) plus one-prompt custom project creation and cross-machine export/restore.
  4. **Science**: Reproducible research environment with AIC/MDL complexity penalties, permanent negative-result preservation (`0` erased findings), dataset drift flagging, and independent zero-trust replay.
  5. **Civic**: Public infrastructure comparison under P10/P50/P90 uncertainty, evidence-linked citizen challenges, and one-click standalone HTML decision dossier export.
  6. **Neighborhood (ClearCovenant)**: Understand HOA rules, resolve disputes, compare costs, and manage community records — as a local single-user tool. The server binds loopback only, client-supplied identity is ignored (the local operator is the only actor), and multi-household separation is not a supported deployment. Includes 12 HOA conflict scenarios, draft responses, vendor/reserve comparison, and portable export.
- **Plain User-Facing Language**: Replaced internal engineering codes with clear status indicators (`Waiting for your review`, `Accept changes`, `Needs another review`, `Some supporting information is missing`, `Approval required`) while keeping full cryptographic receipts and SHA-256 checksums accessible in the expandable **Technical & Audit Details** drawer.
- **One-Command Local Launch**: Added `launch_genie.py` and `run_openline_genie.sh` for zero-cost (`$0`) local operation without API keys, plus 5 ready-to-import sample projects in `examples/`.
