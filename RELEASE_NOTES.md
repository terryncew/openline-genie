# R7.2 private STOP/Resume concurrency repair — HOLD FOR MUSE REACCEPTANCE

- Receives the exact R7.1 candidate SHA-256 643c0bf012a676dc8e6449b825b76382b222dba2ac01d54cb2acf766cf5e06b8 unchanged as its parent. Muse independently identified a prompt STOP/Resume race on five-products UI.
- Browser now queues a prompt explicit Resume click until the preceding STOP receipt is acknowledged, and pins the Resume request to that stop epoch. A newer independent STOP remains authoritative; no blind retries.
- Engine and HTTP routes accept an optional integer expected_epoch and fail closed with conflict if stale. Existing legacy clients without expected_epoch continue to work.
- New API regression tests and optional Chromium inline-API race probe (tools/browser_stop_race_probe.py) cover normal, intervening STOP, and failed STOP cases. Mocked browser tests are NOT full live HTTP acceptance.
- Original R7.1 household bound remains unchanged. No launch, PR, merge, or publication is authorized by creating this private repair candidate.

# R7.1 independent validation hotfix — private candidate; NOT PUBLISHED

- Corrected a receiver-side domain mismatch identified by GPT-6 while verifying R7 exact SHA `cd2a5ce2…`: a local API caller could stage **and accept** `households=99999` although the browser declares `max=5000`. The Energy `household_units` route now requires a finite integer in `[1, 5000]`; booleans, NaN and infinity fail closed. A new test covers both rejection and the permitted upper bound.
- Replaced obsolete `INSTALL.md` instructions for v0.7.1 with the actual seven-app rc2 installation and the unresolved complete-suite, network/CDN, and platform limitations.
- This is a new candidate with a new archive SHA. It cannot inherit R7's exact-hash owner approval. Prior R7 had 214 Python tests run (0 failures, 16 errors, 4 skips) and eleven Node passes; independent R7.1 targeted tests must be recorded separately. No public merge, tag or release is authorized by creating this patch.

# OpenLine Genie `v1.2.0-rc2` — Release Notes

## Summary of Changes in `v1.2.0-rc2`

1. **Cryptographic Capsule Receipt Verification (`core/portable_verified_inheritance.py`)**:
   - Enforces trusted issuer membership (`TRUSTED_CAPSULE_ISSUERS`) and Ed25519 signature verification (`sign_envelope` / `verify_envelope`) over `capsule_digest_sha256`, `source_sha256`, and `test_suite_sha256` before any capsule import or execution. Forged issuers (`UNTRUSTED-ISSUER`) and tampered signatures fail closed (`PermissionError`).
2. **Elimination of Arbitrary Python `exec()` During Capsule Import**:
   - Removed dynamic `exec()` from `core/portable_verified_inheritance.py`. Capsules are checked via `ast.parse()` and resolved strictly against audited allowlisted kernels (`ALLOWLISTED_CAPSULE_KERNELS`). Tampered or unallowlisted source strings fail closed without ever executing.
3. **Mandatory Assumption & Revocation Enforcement at Consequential Effect Boundaries**:
   - `WorkerBPortableInheritanceRuntime.execute_on_unseen_task()` and `OpenLineRoboticsProductEngine.test_hardware_safety_dispatch()` automatically verify live `ReceiverGuard` STOP/epoch state, `RecallLedger` DNF standing, and supporting assumptions before executing any effect, even when the caller never invokes a manual recall checker.
4. **Clean-Install Dependencies & Launcher/Version Alignment**:
   - Added `onnxruntime>=1.16.0` to root `requirements.txt` and `pyproject.toml` (`version = "1.2.0rc2"`), plus a deterministic pure-NumPy fallback in `openline_robotics_001/robotics_studio_engine.py` so `python3 launch_genie.py --verify-only` succeeds even in minimal offline environments.
   - Updated `launch_genie.py` console banner and application listing to `OPENLINE GENIE — SEVEN-APPLICATION LOCAL SUITE (v1.2.0-rc2)` while preserving 5-application backward compatibility (`applications_ready` and `/api/five_products/state`).
5. **Measured Trial Counters & Honest Evidence Labeling**:
   - Replaced static comparison literals in `core/portable_verified_inheritance.py` with measured trial evaluation counters and retired the `6.0x` real-agent performance multiplier claim (explicitly labeled `CONSTRUCTED_DETERMINISTIC_PARAMETER_SEARCH_NOT_REAL_LLM_AGENT_BENCHMARK`).


## GPT-6 independent repair pass (private candidate; **NOT PUBLISHED**)

This review corrected live security regressions observed by Muse against the
actual SHA `5f3d95df…` Argon RC2 candidate. This is a new source snapshot with a
new archive hash, **not** that original RC2 archive.

- Loopback HTTP bind and Host validation now cover all GET and POST routes.
- Neighborhood browser role/board authorization cannot be self-declared; the
  local server selects one owner persona and hides other workspaces.
- Accepting changed assumptions produces signed Decision Recall and blocks
  stale downstream authorizations. Explicit local basis review can reopen local
  computations after evidence matches; external revocations cannot be erased.
- Import uses explicit destination version/SHA compare-and-swap, with clear
  refusal of stale files and verified cross-install import tested.
- First-run UI displays preparation state and keeps STOP/Resume accessible.
- Semantic research no longer recomputes on request cache miss; research-only
  runners now take configurable paths rather than private absolute directories.
- User-facing ClearCovenant removes the 'Be Neighborly' sub-brand.
- An additional security regression suite covers GET, role spoofing, evidence
  revalidation, STOP before seeding, and portability. See GPT6_RELEASE_ACCEPTANCE.

Review status: *back-end focused tests passed; real Chromium UI verification
blocked by the testing environment's administrator URL policy*. **HOLD PUBLIC
RELEASE** until exact-hash independent browser + first-user acceptance.
