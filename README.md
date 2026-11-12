# OpenLine Genie v0.7.1 (public release)

OpenLine Genie Living World (`genie_living_world.html` + `genie_server.py` + `genie_engine.py`) is a local-first visual project builder and constraint-reasoning environment governed by `ReceiverGuard` (`core/openline_guard.py`).

## What Works Today (v0.7.1 Capabilities)

1. **Living World Visual Projection & Constraint Discovery (`genie_living_world.html`)**:
   - Served at `http://127.0.0.1:8795/` by `genie_server.py`.
   - Projects live accepted state, exploratory proposals, rejected quarantine records, STOP epochs, and cryptographic Ed25519 receipts signed by the local `ReceiverGuard`.
   - Identifies the active **binding constraint** (e.g., `oven` at `174 loaves/day` in **Hearth & Crumb Bakery**, or `water` at `105 lbs/week` in **Community Garden Crop Rotation, Drip Cistern & Volunteer Planner**), highlights clamped traps (`+0` output when expanding non-binding resources), compares OpenLine synergy paths against competent conventional comparators, and records `100-Yard Jump` receipts (`genie_jump_decisions`) when an accepted change shifts the bottleneck to the next ceiling.
2. **Hardened Receiver Authority & Promotion Invariants (`P0-A` through `P0-E` Closed)**:
   - **P0-A (Atomic Base Compare-and-Swap)**: Every exploratory proposal records `base_version` and `base_state_sha256`. Promoting a proposal verifies inside the SQLite transaction that `genie_accepted` is still at `(base_version, base_state_sha256)`; competing proposals from an older base are marked `STALE_REOPEN_REQUIRED` and refused with `PermissionError` (HTTP `409`).
   - **P0-B (STOP Epoch & Worker Revocation Binding)**: Every proposal binds `proposer_epoch`, `proposer_worker`, and `proposer_basis_json`. Triggering `STOP` advances the epoch and atomically marks all pending pre-STOP proposals `REVOKED_BY_STOP_EPOCH`; `clear_stop` never resurrects them. Replacing a worker (`replace_worker_and_recover`) revokes pending proposals from the revoked worker (`REVOKED_BY_WORKER_SWAP`).
   - **P0-C (Immutable Project Identity & Schema)**: Canonical `project_id` and `schema` are enforced across `propose_exploratory_change`, `verify_project_artifact`, `accept_exploratory_change`, and `_commit_accepted_state`.
   - **P0-D (Fail-Closed `TRUSTED_PROJECT_FAMILIES` Registry)**: Only registered families (`service_quoting_invoicing`, `robot_academy_kids`, `bakery`, `synthesized_micro_app`, `model_built_app`) and explicitly permitted transitions are accepted; unknown families or cross-family validator downgrades fail closed.
   - **P0-E (Durable Cross-Process & Cross-Thread Spend Authority)**: `SpendLedger` (`core/model_adapter.py`) combines per-directory `RLock`, OS `fcntl.flock`, unique atomic temp writes (`spend.json.<pid>.<uuid>.tmp`), and a SQLite high-water authority table (`spend_authority.sqlite`) to prevent concurrent reservation races, detect ledger deletion/reset/tampering, refuse unknown model pricing, and reconcile stale open reservations (`reconcile_stale_reservations`).
3. **Portable Export & Fresh-Install Import/Recovery (`/api/export` & `/api/import`)**:
   - Exports standalone HTML, CSV (with formula-injection neutralization), and canonical JSON bundles carrying the accepted SHA-256 and Ed25519 receipt.
   - Imports portable bundles into a fresh installation (`import_portable_bundle` / `POST /api/import`), verifying SHA-256 integrity and upstream receipt signatures while labeling external receiver keys honestly (`EXTERNAL_RECEIVER_SIGNATURE_VERIFIED_IMPORTED` vs `LOCAL_RECEIVER_REIMPORTED`).

## v0.7.1 receiver atomicity repair (public release)

RC7 r2 had a reproducible interrupted-import failure: accepted state could commit before a staged app was promoted, then the failure handler deleted that app. v0.7.1 moves staged-app promotion, accepted state, and the signed receipt into **one receiver-guarded SQLite transaction**, and requires every accepted `app_version` pointer to reference an accepted artifact with matching SHA-256. The same commit rule covers imports, ordinary exploratory acceptance, and model-worker-created apps. Failure-injection tests explicitly check failed promotion, failed receipt insertion, and a caller crash *after* durable commit.

**Receipt effect digest convention:** for `genie_accepted`, the signed receiver `effect_sha256` is computed from the persisted row *before* the receipt is injected (the `receipt_json` column is `{}` at digest time). The receipt is then inserted in that same transaction. To independently reproduce the effect SHA, fetch the row by primary key and hash the canonical row dictionary with `receipt_json` set to the literal string `{}`. Hashing the final row including the receipt itself will produce a different hash due to self-reference. The separate signed request payload hash binds exact accepted `project_id`, `version`, and `state_sha256`; neither a bare receipt signature nor an effect hash substitutes for content/target/basis checks. This is a protocol-specific projection, not a claimed general proof of external effects.

The `tests/test_rc7_r3_atomicity.py` suite must pass before review. This release has not been tested on physical iPhone Safari or by unscripted external users. Source archives intentionally exclude `.genie_key_*`, generated SQLite databases, WAL/SHM, and `__pycache__`.

## Honest Runtime Scope & Limitations

- **Default Execution Mode (`$0` Local Deterministic Synthesizer)**: By default, `genie_server.py` starts with paid model dispatch **OFF** (`use_model=False`). Unfamiliar prompts are compiled deterministically by `GenieAppSynthesizer` and domain models (`core/bakery.py`, `core/community_garden.py`) with zero external API calls and `$0.00` spend. Paid model synthesis (`GenieWorker` + `AnthropicAdapter`) is only enabled when explicitly opted in via `--enable-paid-model` or `GENIE_ENABLE_PAID_MODEL=1`.
- **Local Trust Boundary (Same-UID Process Scope)**: `genie_server.py` binds strictly to loopback (`127.0.0.1` / `localhost`) and enforces `Host` and `Origin` CSRF checks on mutating `POST` requests. Signing seeds (`.genie_key_*`, mode `0600`) and SQLite databases (`genie_state.sqlite`, `spend_authority.sqlite`) reside in the local state directory; processes running under the same OS user (`UID`) share filesystem access unless isolated by separate OS accounts, containers, or hardware keys.
- **Soft/Local Spend Cap Scope**: `SpendLedger` enforces atomic pre-dispatch reservations for local `AnthropicAdapter` calls, but cannot prevent external API usage outside this adapter or provider-side billing discrepancies.
- **Verification Scope**: Automated Python (`unittest`, `python3 -O`) and Node (`node --test`) suites verify backend cryptographic invariants, concurrent race refusal, projection accuracy, and DOM/CSS layout rules. Native iOS Safari hardware testing and external unscripted human comprehension studies remain **NOT TESTED** in this release.

## Quickstart & Clean-Room Verification

```bash
# 1. Install runtime dependency (cryptography for Ed25519 signatures)
pip install -r requirements.txt

# 2. Run the local server (paid model dispatch OFF by default)
python3 genie_server.py --host 127.0.0.1 --port 8795

# 3. Run the 7 P0 release falsifiers and adversarial gate (normal + python3 -O)
python3 -m unittest -v tests/test_genie_rc7_release_falsifiers.py tests/test_genie_rc7_adversarial_gate.py
python3 -O -m unittest -v tests/test_genie_rc7_release_falsifiers.py tests/test_genie_rc7_adversarial_gate.py

# 4. Run full Python & Node verification suites
python3 -m unittest discover -s tests -p "test_*.py" -v
node --test tests/test_rc6_projection.mjs
```

## License

Copyright (c) 2026 OpenLine Project.

Licensed under the Apache License, Version 2.0 (the "License"). See LICENSE for the full text. You may obtain a copy of the License at https://www.apache.org/licenses/LICENSE-2.0

OpenLine branding and trademarks are governed separately and are not licensed under the Apache License 2.0.
