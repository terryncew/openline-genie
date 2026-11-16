# OpenLine Genie — GPT-6 independent repair and acceptance

**Private software release candidate. Public publication: HOLD.**

The starting source was the *real* Argon `OPENLINE_GENIE_RELEASE_CANDIDATE_v1.2.0_RC2.zip` (SHA-256 `5f3d95df0b4fca3e7c66b1e6fd59cf595ff5746b098cad1d1f1b38951096c75c`), not the older convergence bundle. This dossier describes a materially changed, newly hashed private candidate. Never represent the old hash as the repaired release.

## Boundary-first conclusions

The live failures reported by Muse revealed real authorization and first-use defects. Independent source repairs covered:

1. Server binds only to `127.0.0.1` or `localhost` instead of `0.0.0.0`, with strict Host/Origin checks on GET and POST. Foreign Host requests to HTML and API routes now return 403.
2. Neighborhood identity is server-owned, not client-controlled. Homeowner is the default single-operator demo; non-owner roles are denied on state reads, staging, authorization, dossier export, project reads and imports. Browser role tabs for other personas are hidden. This is not multi-tenant authentication or physical verification of board membership.
3. Accepting changed product assumptions revokes each dependent assumption source in the signed RecallLedger, visibly shows `REOPEN`, and blocks consequential authorizations. An explicit, hash-bound owner review may restore only *local* parameter standing; unrelated or newer external revocations remain blocked. The owner review does not validate the physical world.
4. UI import now sends the exact destination base-version/SHA for compare-and-swap, refuses an equal/stale source with an explicit message, and reports completion only after accepted state is returned. A second-install import of a newer signed project was reproduced.
5. First-use UI presents a loading explanation and fetches a lightweight STOP status independent of slow example seeding; `/api/status` now returns `stopped` and epoch. Early STOP/Resume was verified through the HTTP endpoints.
6. Semantic GET no longer runs an expensive research computation when its stored receipt is missing; responds HTTP 503 with an offline command instead.
7. Five inherited research-only runners no longer require their author’s private `/working_dir` paths; environment-configurable input/output locations are used. External research inputs remain excluded.
8. User-facing ClearCovenant header/title no longer contains the retired “Be Neighborly” label; its historical `/be_neighborly` route remains as a compatibility alias.
9. Independent application engines are bound to their respective HTTP server instances, rather than a mutable class singleton. A subclass-based legacy test compatibility issue was caught and repaired.

## Tests executed on the repaired tree

- Original archive SHA verified before editing.
- **74/74 selected Python tests PASS** (backend, adversarial, independent falsifiers, semantic, rc6 integration, SQLite atomicity, living-world domain, bounded RGPO and inheritance, and six independent release-boundary tests). Command: `python3 -m unittest -q tests.test_genie_rc3_backend tests.test_genie_rc7_adversarial_gate tests.test_rc7_r1_independent_falsifiers tests.test_semantic_authority_001 tests.test_genie_rc6_integration tests.test_rc7_r3_atomicity tests.test_rc7_r4_living_world_product tests.test_final_release_boundaries tests.test_loop_b_rgpo_011_qualification tests.test_loop_c_portable_inheritance`.
- **11/11 Node projection tests PASS**: `node --test tests/test_rc6_projection.mjs`.
- `python3 launch_genie.py --verify-only` returns READY with **all seven apps** in a fresh state directory.
- Live HTTP adversarial smoke PASS: hostile Host on five routes; unauthorized board request, dossier, import and export; semantic cache miss; STOP/Resume before seeding; changed-assumption REOPEN and effect denial; local review; independent evidence revocation cannot be cleared by local review.
- Signed Energy Commons project transfer PASS: source version 3 exported; destination version 2 refuses overwrite without CAS; newer source imported after correct version/SHA provided, retaining source provenance and modified assumptions.
- Inline JavaScript syntax PASS with `node --check` for five major HTML interfaces.

## Explicit remaining HOLD gates

- **Full headless browser walkthrough not independently accepted here.** Chromium is installed, but its administrator-managed URL blocklist (`URLBlocklist: ["*"]`) blocked Playwright navigation to the locally served app. The test was attempted and failed with `ERR_BLOCKED_BY_ADMINISTRATOR`, *not* a passing UX test. Do not bypass the administrator policy. Re-run the real desktop/mobile app workflow in a permitted browser test environment.
- **Full legacy Python suite not accepted.** The packaged Playwright compatibility shim requires Selenium, which is not installed in this environment; the omnibus run also exceeded its time cap. The bundle has an optional browser-test requirements file, but the complete suite was not green here. Some historical tests deliberately assume that anonymous requests can select all three Neighborhood roles, which is no longer an acceptable authority contract; reconcile those tests with the new server-owned identity without relaxing the security checks.
- No live iPhone Safari device test; only mobile-layout source and static checks.
- No independent multi-UID, network-exposed, multi-tenant, hardware-control or paid-model production qualification.
- Actual public GitHub `main` is an earlier release branch. No push, public PR, tag, release, payment, external contact or social post was performed by this repair.

## Next discriminating gate

In a permitted clean browser/host environment, install **this exact ZIP hash** in a fresh directory. Run all seven apps with real 390 px and desktop layouts. Demonstrate one-prompt project creation, evidence inspection, ACCEPT, REJECT, STOP during initial seeding and after readiness, Resume, assumption-change REOPEN, explicit local review, signed export/import into a second installation, role-spoof refusal and no console errors. Re-run the complete suite with documented browser dependencies, and report failures rather than editing the acceptance checks to manufacture a pass.

If those pass, present the exact archive SHA to the owner for a final public-release decision. Until then, **HOLD publication; preserve the already-public older preview**. Physical Witness, Qwen model-efficiency and robotics hardware experiments are separate and do not change this software verdict.
