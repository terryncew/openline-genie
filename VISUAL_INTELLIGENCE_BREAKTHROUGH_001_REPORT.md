# OPENLINE GENIE v1.2.0-rc3 — VISUAL INTELLIGENCE & FINAL RELEASE CLOSURE REPORT

- **Candidate Version**: `v1.2.0-rc3` (`pyproject.toml` `1.2.0rc3`)
- **Candidate Evaluation Authority**: `CANDIDATE_HAS_EVALUATION_AUTHORITY = False`
- **Candidate Status**: `FROZEN_CANDIDATE_AWAITING_GPT6_INDEPENDENT_ACCEPTANCE` (Argon does not self-certify independent acceptance or production promotion)
- **Primary Visual Harness Reference**: *Vision-as-a-Tool: Visual Harness for Multimodal Agentic Coding* ([arXiv:2611.17797](https://arxiv.org/abs/2611.17797), [HTML](https://arxiv.org/html/2611.17797v1), [GitHub](https://github.com/TidalHarley/Vision-as-a-Tool))
- **Complementary Literature**: *VISTA* ([arXiv:2610.02200](https://arxiv.org/abs/2610.02200)), *Mosaic* ([arXiv:2609.39363](https://arxiv.org/abs/2609.39363)), *VideoHarness-SRSI* ([arXiv:2610.19424](https://arxiv.org/abs/2610.19424)), *ScaleGuard* ([arXiv:2611.16744](https://arxiv.org/list/cs.AI/recent)), *DeepMind MKA* ([PDF](https://storage.googleapis.com/deepmind-media/papers/mka_tech_paper.pdf))

## 1. Closure of Release Blockers (2.A – 2.D)

### A. Holdout Decontamination & Independent Evaluation Boundary (`Blocker 2.A`)
1. **Removed Benchmark & Holdout Cases from Candidate Source (`core/`)**:
   - Removed `build_benchmark_task_suite`, `run_four_way_capability_tournament`, `run_100_yard_hypothesis_test`, and `run_independent_visual_falsification_suite` from `core/visual_intelligence_harness.py`.
   - Set `CANDIDATE_HAS_EVALUATION_AUTHORITY = False` and renamed the candidate-side invariant check to `check_candidate_visual_and_functional_invariants` (`independently_accepted = False`, `independent_acceptance_status = "PENDING_EXTERNAL_EVALUATOR"`).
2. **Reclassified the Original 16 Cases Strictly as Regression Tests**:
   - Moved `REG-01` .. `REG-16` (formerly `DEV-01..08` and `HOLD-01..08`) to `tests/visual_regression_16_cases.py` with `split = "regression_fixture"`, `REGRESSION_SUITE_ONLY = True`, `IS_SEALED_HOLDOUT = False`, and `CLAIMS_UNSEEN_GENERALIZATION = False`.
3. **Replaced Fixture-Specific Regexes with General Algorithmic Solvers**:
   - Replaced hardcoded `room-1..3` and `node-b` regex replacements in `core/visual_intelligence_harness.py` with `_general_svg_node_and_label_reflow()` (arbitrary $N$-node/label collision resolution and viewBox envelope expansion) and `_general_floorplan_partition_and_egress_solver()` (exact footprint-conserving $N$-room grid partition and spanning doorway graph generator).
4. **Established Independent Evaluation Boundary (`core/independent_evaluation_boundary.py`)**:
   - Added stateless entrypoint `submit_candidate_repair_for_external_evaluation(task_input)` and CLI `python3 -m core.independent_evaluation_boundary --task-json <path>`.
   - Enforces `FORBIDDEN_EVALUATOR_ORACLE_KEYS` (`expected_html`, `expected_defects`, `private_holdout_verdict`, `force_accept`, `bypass_receiver`, etc.) and `assert_not_inside_private_evaluator_vault()` blocking any access to `GENIE_PRIVATE_EVALUATOR_VAULT`.

### B. Real Browser Acceptance Suite (`Blocker 2.B`)
1. **Removed Mock Selenium Shims**:
   - Removed the `sys.modules['selenium'] = types.ModuleType(...)` shim from `functional_runner.py` so the runner executes real Headless Chromium via `/usr/bin/chromium` and `/usr/bin/chromedriver`.
2. **Complete Browser Suite Execution**:
   - `python3 functional_runner.py .`: `6/6` tests PASS (`test_openline_genie_001.py` `5/5` + `test_06_living_world_journey.py` `1/1` mobile `390x844` journey).
   - `python3 tests/verify_real_bakery.py`: PASS (`174 -> 240` throughput, offline export & reload persistence verified in real Chromium).
   - `python3 -m unittest -v tests/test_r5_form_defaults_regressions.py`: `14/14` tests PASS (`R5-RESTORE` sequential accept/restore and `FORM-DEFAULTS` input persistence in real Chromium).
   - `python3 muse_independent_checks.py`: `24/24` security & browser checks PASS.
   - `python3 -m unittest discover -s tests -p "test_*.py"`: `231/231` tests PASS in both normal and `python3 -O` optimized modes (`0` failures, `0` skipped).
   - `node --test tests/test_rc6_projection.mjs`: `11/11` tests PASS.

### C. Release Consistency (`Blocker 2.C`)
- Aligned `pyproject.toml` (`version = "1.2.0rc3"`, `Pillow>=10.0.0`, `selenium>=4.8.0`, `[project.scripts]` `openline-genie` and `openline-genie-server`), `requirements.txt`, `requirements-browser-test.txt`, `launch_genie.py`, `README.md`, `RELEASE_NOTES.md`, and `INSTALL.md` to `v1.2.0-rc3`.

### D. Authority & Security Hardening (`Blocker 2.D`)
- Removed silent `except Exception: pass` blocks in `observe_rendered_artifact` (`core/visual_intelligence_harness.py`) and `GenieWorker._test_app_fallback_dom` (`core/genie_worker.py`) so failed visual inspections set `obs.inspection_failed = True` and fail closed (`REJECTED_VISUAL_INSPECTION_FAILED`).
- Added `OpenLineGenieEngine.propose_visual_artifact_repair()` in `genie_engine.py` enforcing receiver-controlled exploratory staging (`genie_exploratory` only; `genie_accepted` untouched), `STOP` checks, `SpendLedger` integrity verification, forged-receipt refusal, and fail-closed rejection on any control/SVG/room deletion (`REJECTED_FUNCTIONAL_DEGRADATION`).
- Restored strict ISO `YYYY-MM-DD` `filing_date` and integer `1..365` `appeal_window_days` validation in `openline_009_living_project.py`.

## 2. Real Product Dogfooding & Second-Worker Capability Inheritance (Section 3)
- Executed `python3 run_rc3_dogfood_and_browser_acceptance.py` and `tests/test_rc3_dogfood_and_inheritance.py` (`1/1` PASS) in real Headless Chromium (`artifacts/dogfood_rc3/`):
  1. **`DOGFOOD-01-CLEARCOVENANT-RESPONSIVE`**: Repaired mobile header occlusion and toolbar overflow clipping on a real ClearCovenant Neighborhood HOA interface and verified in real Chromium across `390x844`, `320x640`, and `1280x800` viewports (`0` defects, interactive click verified).
  2. **`DOGFOOD-02-STATEFUL-DISPATCH`**: Repaired form-submit state-reset trap, stale assumption defaults (`solar_kw=145`, `battery_kwh=280`, `reserve_floor_pct=25`), and offline Chart.js CDN dependency on a real Community Solar & Cold-Room Dispatch app, verified two sequential stateful clicks (`Committed:2`) and Advocate input persistence (`filing_date="2026-11-15"`, `appeal_window_days=45`), and recorded a fail-closed rejection trace (`REJECTED_FUNCTIONAL_DEGRADATION`) when a corrupted repair attempted to delete controls.
  3. **`DOGFOOD-03-SDD-PCM-HUB-FLOORPLAN`**: Repaired a 4-bay Solar Direct-Drive Phase-Change Multi-Service Hub (`bay-solar`, `bay-ro`, `bay-pcm`, `bay-vestibule`) floor plan and SVG schematic in real Chromium (`0` room overlap, `0` area conservation error, `4/4` rooms connected via `3` doorways, `0` SVG clipped elements).
- Verified clean-room **Worker B Visual Capability Inheritance** (`WorkerBPortableInheritanceRuntime` loading `capsule_argon_vis_001.json` in an isolated directory with zero Worker A state, passing `3/3` unseen dogfood vectors and automatically transitioning to `REOPEN` on assumption drift).
