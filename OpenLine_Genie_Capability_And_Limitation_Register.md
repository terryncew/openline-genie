# OpenLine Genie — Honest Capability & Limitation Register

**Date:** November 10, 2026  
**Governing Standard:** OpenLine Agent Operating Law v1.0 (Zero fabricated passes, zero disguised simulations, explicit `PARITY` disclosure)

## 1. Verified Capabilities (Proven by Executable Tests & Receipts)

| Capability | Implementation File & Mechanism | Verification Test | Observed Metric / Result |
| :--- | :--- | :--- | :--- |
| **Demonstration A: Small Service Business Quoting & Invoicing** | `genie_engine.py` (`calculate_quote_totals`, `demo_a_*`) + `openline_genie.html` | `test_01_demonstration_a_quoting_invoicing_cent_math_and_export` | Cent-accurate subtotal, discount %, taxable subtotal, tax %, total, and 25% deposit; 1-click Quote-to-Invoice conversion (`Q-1003 -> INV-2002`); local SQLite + `localStorage` persistence; standalone HTML/CSV/JSON export. |
| **Demonstration B: Free Interactive Kids Robotics Environment** | `genie_engine.py` (`simulate_robot_academy_program`, `ROBOT_ACADEMY_LEVELS`) + `openline_genie.html` | `test_02_demonstration_b_robot_academy_levels_and_safety_permit` | 4 progressive levels (`MISSION_COMPLETE`), D-Pad & block programming, ultrasonic obstacle clearance (`>= 0.40 m`), workcell permit speed gate (`> 0.75 m/s` blocked), and human walkway boundary (`x <= 4.20 m`). |
| **Permanent Project Ownership (`ACCEPTED` / `EXPLORATORY` / `REJECTED`)** | `genie_engine.py` (`propose_exploratory_change`, `reject_exploratory_change`, `accept_exploratory_change`) | `test_03_rejected_proposals_never_overwrite_accepted_work_and_approved_promotes` | `0` overwrites of `ACCEPTED` state across rejected destructive proposals; `100%` state survival across browser reload and engine restart. |
| **Hundred-Yard Jump: Unfamiliar Request Micro-App Synthesizer** | `GenieAppSynthesizer` (`openline.genie.synthesized_app.v1`) | `test_04_hundred_yard_jump_unfamiliar_request_synthesis_and_falsifiers` | Compiles unfamiliar natural-language requests into working CRUD + live formula + status workflow apps in `~313 ms` (for 3 apps) with domain falsifiers. |
| **Adversarial Workflow Lab 4 Repairs (`D-01`/`D-01b`, `D-02`, `D-03`, `D-04`)** | `core/openline_guard.py`, `core/ipc_protocol.py`, `core/acs.py` | `test_05_adversarial_workflow_lab_four_repairs_and_external_reconciliation` | Two-phase external outbox (`UNKNOWN_RECONCILIATION_REQUIRED -> RECONCILED_DELIVERED` with `0` duplicate sends), `>=1s` clock-invariant `ipc_request_intent_sha256`, transitive `set_basis` reopen, and `FAILED_REALITY_CHECK` replay quarantine. |
| **iPhone Mobile (`390x844`) & Desktop (`1440x920`) Browser UX** | `openline_genie.html` (CSS Grid responsive breakpoint + `localStorage`) | `test_06_iphone_mobile_and_desktop_browser_customer_journey` | `0` console errors, `0` horizontal overflow (`scrollWidth <= clientWidth`), full interactive customer flow verified in headless Chromium. |

## 2. Fair Comparison Against Competent Conventional Coding Agent + Ordinary Tools

Measured in `record_and_benchmark_genie.py` (`evidence/INDEPENDENT_BENCHMARK_EVIDENCE.json`):

| Dimension | OpenLine Genie (`OpenLineGenieEngine` + `openline_genie.html`) | Competent Conventional Coding Agent + Git/Tests | Honest Verdict |
| :--- | :--- | :--- | :--- |
| **Single-Developer Stationary Code & Math** | Cent-accurate Python/JS calculation & unit tests | Cent-accurate Python/JS calculation & unit tests | **`PARITY`** |
| **Unconstrained Arbitrary Multi-File Backend Frameworks** | Scoped to browser/SQLite micro-apps and registered domain adapters | Can install arbitrary npm/PyPI packages and write multi-service backends | **Conventional Agent Wins on Arbitrary Stack Breadth** |
| **Non-Technical User Effort (iPhone / Zero-CLI)** | **1 prompt + 1-tap Accept/Reject/Export directly in mobile browser (`~313 ms`)** | Requires terminal, Git checkout, local runtime setup, and manual branch/stash commands | **OpenLine Genie Advantage on Accessibility & Zero-CLI UX** |
| **Rejected Proposal & Mid-Task Interruption Safety** | **Mechanically isolated `EXPLORATORY` / `REJECTED` tables + `ReceiverGuard` `SAVEPOINT`** | In-workspace agent edits overwrite working files unless user manually manages `git stash`/`git checkout` | **OpenLine Genie Advantage on Accepted-Work Preservation** |
| **Unknown External Outcome Recovery (`D-01b`)** | **Fences `UNKNOWN_RECONCILIATION_REQUIRED` rows (`0` silent retries) & reconciles via destination probe** | Standard retry-on-timeout re-sends webhook (`2` deliveries / duplicate external effect) | **OpenLine Genie Advantage on Consequential Recovery** |

## 3. Hard Safety, Financial & Execution Provenance Limitations (Never Overclaim)

1. **Demonstration A (Service Quoting & Invoicing) Honesty Boundary**:
   - Produces real, usable quotes, cent-accurate totals, numbered invoices, local persistence, and printable/portable exports at `$0` subscription cost.
   - **Does NOT** generate customer leads, process live credit-card/ACH payments, file taxes, or guarantee business revenue.
2. **Demonstration B (Kids Robot Academy) & Robotics Safety Boundary**:
   - Teaches movement, sensor logic, obstacle clearance, and workcell permit concepts in a free 2D browser simulator.
   - Application-level permit revocation (`STOP`) does **NOT** establish physical emergency stopping, safety-rated isolation (ISO 13849 / IEC 61508), or real robot hardware actuation.
3. **Model & Worker Execution Provenance**:
   - In this offline `$0`-spend sandbox, `OpenLineGenieEngine` and `GenieAppSynthesizer` execute deterministic local synthesis, AST/invariant self-tests, and OS subprocess receiver verification (`LOCAL_AUTONOMOUS_COMPILER_AND_VERIFIER`). No scripted or deterministic step is ever represented as a live paid cloud LLM call.
4. **Cold-Extraction Packaging Defect Found & Resolved in Inherited Shared-Receiver Bundle**:
   - During Milestone 1 verification of the inherited shared-receiver bundle, we found that a module expected a source path outside the ZIP root. In `openline-genie-001.zip`, all core modules in `core/` (`openline_guard.py`, `ipc_protocol.py`, `recall.py`, `tc_controller_v2.py`, `acs.py`) run 100% self-contained from a cold unzip with zero external path dependencies.
