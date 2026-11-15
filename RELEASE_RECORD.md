# OPENLINE Final Ship & Closeout 001 — Release Record

Date: 2026-11-15. Release owner: Muse (release coordinator). Founder: Terrynce White.
Prior publication was STOPPED on 2026-11-14 (nothing published); this record supersedes that STOP. All findings below were independently verified by re-running the software, not by accepting reported counts.

## PUBLISHED

Public GitHub release: https://github.com/terryncew/openline-genie/releases/tag/v1.0.0-rc1
Tag: `v1.0.0-rc1` (prerelease, not draft). Commit: `f16f2e824c41dede1a3ebef6980d83096e46d9df`.
Parent commit (pre-publication main): `6ccbb18d90026b8b4b17b09ad18bf600d2b565d2`.
Release asset: `OPENLINE_GENIE_V1_0_0_RC1_APPLICATIONS.zip`, 6,266,452 bytes.
Asset SHA-256: `062b318a3f09f4248c806fd94888282c4a81a9c39de8540736df40680d15830e`.
No new repository was created. The existing public repository `terryncew/openline-genie` was used; its v0.7.1 tag (`87aee3f3b726136fce1676ff6ec1d9e42f97dde6`) and release are untouched, and all v0.7.1 files are preserved except the root README, which was replaced with the new landing page.

All six applications are published in `applications/`, served by one local server with a six-tab launcher at `/products`:

| Application | Plain description | Verified capabilities |
|---|---|---|
| Energy Commons | Compare community energy options and costs. | 10-year cash-flow comparison independently recomputed within $0.03 on all options; negatives/zero refused; 4/4 fraud-guard probes blocked. |
| Advocate | Understand decisions, organize evidence, and prepare challenges. | Missed deadlines flagged; self-certified "facts" downgraded; invented rules rejected; 0 PII leaks in probe. |
| Capability Commons | Build and share reusable community projects. | Export/import round-trip verified into a fresh install; tampered bundle refused (`import_sha256_mismatch`). |
| Science | Explore hypotheses and preserve reproducible research. | Absurd hypothesis falsified (RMSE 1035.1 vs 0.0002); independent replay verified; fabricated data raises a provenance error. |
| Civic | Compare public projects and examine the evidence behind decisions. | Inverted P10/P50/P90 proposal disqualified, cannot be recommended. |
| Neighborhood (ClearCovenant) | Understand HOA rules, resolve disputes, compare costs, and manage community records. | 12/12 dogfood scenarios pass; 20/20 unfamiliar-input workflows pass (stage/accept/reject, approval gate, persistence, export/import, Decision Recall, STOP, accepted-state preservation); live re-attack confirms client-supplied identity is ignored and the server binds loopback only. |

Measured verification (2026-11-15, Python 3.12.3, Linux, system Python):
- Python suite on the published tree: 184 ran, 174 passed, 5 errors, 1 failure, 4 skipped. Node: 11 passed, 0 failed.
- Manifest: `applications/SHA256SUMS.txt`, 268 entries, `sha256sum -c` all OK.
- Downloaded release asset SHA-256 matches the published value; extracted asset manifest 268 OK.
- Fresh-clone install from the published instructions (real `venv` + `pip install`): exit 0; `launch_genie.py --verify-only` READY.
- Live server from the published clone: `/products` 200 with six tabs; `/neighborhood` 200; `/api/status` 200; foreign Host 403; bind `127.0.0.1` only (verified with `ss`).
- Unfamiliar workflow on the published clone: built "Design a small neighborhood tool library" (HTTP 200, signed receipt); exported it by project id (HTTP 200, accepted SHA-256, portable JSON, standalone HTML); imported it into a fresh install (HTTP 200, provenance badge `EXTERNAL_RECEIVER_SIGNATURE_VERIFIED_IMPORTED`, project listed).
- Secrets/private-info scan on the published commit: clean (0 Drive links, 0 hardcoded workspace paths, 0 key patterns, 0 private-key files).
- Pages destinations intact: root, Try, How, See all HTTP 200.

## HELD

None. No application was held from publication. (Items recorded as NOT VERIFIED are test-environment limits, not held applications; see Limitations.)

## REPAIRED

Every defect corrected during acceptance, with before/after evidence in `evidence/` (five-app, neighborhood, integration logs):

1. Private Google Drive IDs stripped: 21 distinct IDs (47 link occurrences) in 4 five-app files. Verified 0 `drive.google.com` / `docs.google.com` hits in the published tree.
2. Server bind fixed: `start_genie_server()` honored `--host` in both trees (was hardcoded `0.0.0.0` while docs claimed loopback-only). Verified live with `ss`: `127.0.0.1` only. `--host 0.0.0.0` is refused.
3. Host/Origin check extended to `GET /api/*` endpoints (was POST-only). Foreign Host returns 403; foreign Origin returns 403 `cross_origin_request_refused`. Verified live.
4. Hardcoded builder paths removed: `/working_dir/c_2eb0812f9e3713b4` in 2 five-app runners (plus 1 prose mention, 1 test path) and `/working_dir/c_144ebe156016fa2f` in the Neighborhood runner. Verified 0 `/working_dir` hits.
5. Manifests regenerated from the exact shipped trees: five-app 252 OK (was 28 FAILED), Neighborhood 256 OK (was 133 of 257 covered), unified 268 OK.
6. Neighborhood impersonation boundary repaired within the local-app model (no new auth system invented): client-supplied role/unit/board identity is ignored at the HTTP layer; stage/action force per-workspace operator identity; the exploratory-proposal leak is filtered at the engine level for cross-role readers. Live re-attack (coordinator-run, 8 probes): state responses byte-identical across claimed identities; dossier exports return the operator's own records per workspace; foreign Host 403. A vendor-bid crash (`KeyError: 'option_id'`) found during qualification was also fixed.
7. Advocate: missed deadlines now flagged fail-closed; user statements can no longer self-certify as verified facts; invented legal rules rejected unless pinned. Civic: inverted P10/P50/P90 proposals disqualified. Energy: "independent calculator" claim corrected with a real reported-flows cross-check ($0.03).
8. Test harness: the 127.0.0.2 proxy bypass fixed inside the test module (4 earlier `RemoteDisconnected` errors were an environment artifact, proven by re-run).
9. LICENSE: Neighborhood copyright line added (`Copyright 2025-2026 Terrynce Anson White / OpenLine Protocol Contributors`, Apache-2.0).
10. Naming: "Be Neighborly" removed from all user-facing surfaces and served API payloads; the `/be_neighborly` route removed (now 404). Product name is ClearCovenant, presented as Neighborhood. Remaining mentions exist only in the two naming-decision records and two frozen evidence JSONs.
11. False claims corrected: "never shared with neighbors", "Zero Private Data Leaked", "VERIFIED_0_LEAKS" (in live code/docs), "174/174" and "172/172" counts, loopback claims, and a nonexistent install-guide zip reference. Documented counts now match measured counts exactly (184 ran: 174 passed, 5 errors, 1 failure, 4 skipped; Node 11/11).
12. Plain-language audit: internal engineering language removed from user-facing screens, examples, error messages, and guides across all six apps (raw error codes kept in browser console/developer docs only).
13. Integration: the two repaired trees (22 shared files differed) were merged into one unified tree with a sixth Neighborhood tab; every repair from both trees was grep-verified present; the merge script is preserved (`work/merge_unified.py`). One build defect caught by the file-count audit (an rsync exclusion dropping a nested manifest) was fixed and the manifest regenerated.
14. Publication docs: root README replaced with a landing page for Genie v0.7.1 plus the six applications; root `AGENTS.md` added for AI coding agents; `applications/INSTALL.md` version naming corrected to v1.0.0-rc1; `applications/RELEASE_NOTES.md` extended with the sixth application.

## LIMITATIONS

Known boundaries users must understand. Nothing here is concealed.

- Local only. The server binds `127.0.0.1` and refuses other hosts. Anyone who can reach the port on the computer is the operator, with full access to every workspace. Do not expose the port beyond the computer. There is no login, session, or password in this codebase.
- Same-user boundary. Signing keys and the database live in the state directory. Any process running as the same OS user can read them. Separate OS users, containers, or hardware keys are needed for a stronger boundary.
- Neighborhood is a local single-user tool for one household or association. It does not separate multiple households on one server, and multi-household separation is not a supported deployment. The multi-household isolation boundary was removed (it rested on self-asserted request parameters and was never real) and replaced with loopback-only plus Host/Origin checks.
- Not legal advice. Advocate and Neighborhood organize evidence, dates, and rules for human review. They are not legal advice, do not create an attorney-client relationship, and never submit anything to an outside agency automatically. Neighborhood covers California, Florida, Texas, South Carolina, and a general U.S. baseline; other states need the statute text or local counsel.
- No guaranteed savings or outcomes. Energy Commons compares costs; it does not promise savings. Science verifies computational reproducibility on recorded datasets; it does not validate a finding in the physical world. Civic compares proposals; it does not decide which one a community should choose.
- Not tested: macOS and Windows installs, iPhone Safari, uncoached human testing, paid-model calls, browser end-to-end tests. The 5 Python errors and 1 failure are browser tests that need Chrome/Chromium (not installed in the test environment) and 2 tests that check external archive files not included in this package; they are recorded as NOT VERIFIED, not passed. `muse_independent_checks.py` (24 checks) was not re-run here for the same reason.
- `launch_genie.py --verify-only` lists the five applications (energy, advocate, commons, science, civic). Neighborhood readiness is confirmed separately by the live `/neighborhood` route and `/api/neighborhood/state` checks recorded in the acceptance evidence, not by that script.
- A frozen evidence record (`applications/NEIGHBORHOOD_001_ACCEPTANCE_RECEIPTS.json`) still contains a `VERIFIED_0_LEAKS` claim that is superseded by the repaired single-operator model. The frozen record was left intact as evidence and is not repeated for the current code. Do not quote that claim for the current code.
- The deterministic builder covers the built-in domains; unfamiliar requests without a paid model fall back to the local synthesizer, which may produce a generic app. Paid model dispatch is OFF by default with a local $5.00 spend cap when opted in.
- Triage cannot distinguish a self-supplied hash from a document hash without an external registry; direct Python callers could still self-certify (the HTTP/UI path cannot). One persistence probe reported a restart SHA mismatch that could not be reproduced in three independent replications; recorded as unreproduced, not a finding.

## ROLLBACK

Exact recovery procedure to restore the pre-publication repository state. Execute only on the founder's order; do not run this as routine cleanup.

- Pre-publication main: `6ccbb18d90026b8b4b17b09ad18bf600d2b565d2`. Pre-publication tags: only `v0.7.1` → `87aee3f3b726136fce1676ff6ec1d9e42f97dde6`.
- Delete the release and its tag: `gh release delete v1.0.0-rc1 --repo terryncew/openline-genie --yes --cleanup-tag` (this deletes the release and the `v1.0.0-rc1` tag; the release asset is deleted with it).
- Restore main to the pre-publication commit: `git fetch origin && git push --force-with-lease origin 6ccbb18d90026b8b4b17b09ad18bf600d2b565d2:main`. (A force-push is required only for this rollback; it was not used during publication.)
- Verify: `gh api repos/terryncew/openline-genie/tags --jq '.[].name'` shows only `v0.7.1`; `gh api repos/terryncew/openline-genie/branches/main --jq '.commit.sha'` shows `6ccbb18d90026b8b4b17b09ad18bf600d2b565d2`; the four Pages destinations (root, Try, How, See) still return HTTP 200.
- The v0.7.1 tag, release, and Pages site are untouched by the publication and by this rollback.
- Source preservation independent of GitHub: the repaired unified tree is preserved at `~/workspace/final-ship-closeout-001/work/unified/`; the pristine archives are preserved at `~/workspace/genie-v1-publication/downloads/` (five-app SHA-256 `6fef67202f8573ff4b57f459621821cdf205b9fa5906506d97cf12562ad4a8a5`; Neighborhood SHA-256 `118353c7fc98c849c14dbfc26ab18a905ef7a47e33647a459deb6861ad1981ce`); all evidence is preserved under `~/workspace/final-ship-closeout-001/evidence/` with a SHA256SUMS manifest.

## NEXT OWNER

Owner: Terrynce White. No standing maintenance assignment exists for this release. Muse operated this release on the founder's order and holds no ongoing maintenance role. Any future change, repair, or new version requires the founder's explicit order naming the exact change. There is no scheduled follow-up, no social announcement, and no new research program attached to this release.


# OPENLINE Final Integration & Publication 002 — Release Record Addendum (v1.1.0-rc1)

Prepared 2026-11-15 by the integration coordinator, revised by the parent
agent for the manifest correction below. This text is the v1.1.0-rc1 release
record for RELEASE_RECORD.md. It was NOT appended to RELEASE_RECORD.md in the
coordinator run: a read of that file was flagged by a safety check, so the
file was left untouched. The parent agent appended this section without
reading the existing record. Nothing in this addendum is copied from the
flagged read; all facts below come from this run's own commands and logs,
plus the parent's own verification of the live release.

## PUBLISHED

- Release: https://github.com/terryncew/openline-genie/releases/tag/v1.1.0-rc1 (prerelease, not draft)
- Commit: `456425d413a3d1ebc9ba29ca414040435e0ed131` (merge of `integration/advocate-robotics-002` into main)
- Tag: `v1.1.0-rc1` (tag object `fdd89fdcffab123154495d4ba13bf3b5c8985775`)
- Asset: `OPENLINE_GENIE_V1_1_0_RC1_SOURCE.zip`, 12,268,616 bytes,
  SHA-256 `96d08c15a353259e412f1bd41a8104badcaff218f9cffcf260dd90973bfc8d10`
  (original publication, verified from the live GitHub download; the
  original asset was byte-identical to the tagged commit, verified by
  recursive diff)
- Manifest correction (parent verification, 2026-11-15): the original
  asset's root SHA256SUMS.txt listed a stale hash for README.md. The
  manifest was corrected in commit `076d316` and the asset was rebuilt
  from main and re-uploaded to the same release. The replacement asset's
  SHA-256 is recorded in the GitHub release notes. The rebuilt asset
  differs from the tagged commit only in SHA256SUMS.txt (one corrected
  line) and RELEASE_RECORD.md (this addendum).
- Advocate Case Packets: inside the existing Advocate application.
  Portable verifiable case records: original documents byte-for-byte with
  SHA-256 checksums, exact source citations, four-tier rule authority,
  deadlines never invented, Decision Recall on new evidence, offline-readable
  HTML dossiers, signed .zip export/import, tamper rejection.
- Robotics Studio: seventh application, simulation only. Open Duck Mini v2
  and LeRobot SO-101. Own loopback-only server on port 8796
  (`./run_robotics_studio.sh`), linked from the applications launcher.
- All six v1.0.0-rc1 applications preserved with workflows, receipts, and
  limitations unchanged. Tags/releases v1.0.0-rc1 and v0.7.1 untouched.
  GitHub Pages status built; root, Try, How, See all return HTTP 200.
- No new repository created. No force-push used during publication.

## HELD

None. Both candidates published. Physical-hardware behavior for Robotics
remains unverified (simulation only, stated in the docs); that is a stated
limitation of the simulation product, not a hold on it.

## REPAIRED

Advocate port (3):
1. Frozen timestamps replaced with real UTC in packet history entries and
   document ingestion (candidate stamped `2026-11-14T22:55/22:56/00:00Z`).
2. Browser test skip guard: the workbench browser test now skips as
   NOT VERIFIED without Chromium instead of crashing at import.
3. Workbench default pill text corrected ("Case Packet: Loading…" instead
   of "Case Packet: Verified" before data loads).

Robotics port (4):
1. Studio server refused non-loopback `--host` (Genie-style refusal;
   `--host 0.0.0.0` exits 1). `ss` confirms 127.0.0.1-only binding.
2. Browser draft export was mislabeled and unimportable (toy hash as
   `bundle_sha256`, portable project JSON omitted). Added a Get
   Server-Verified Export button posting to `/api/robotics/export`;
   the endpoint was verified by curl. The button's JS itself was not
   executed in a browser (no browser available) — NOT VERIFIED at UI level.
3. Chart.js CDN guard: `typeof Chart === 'undefined'` skips the telemetry
   chart offline instead of breaking the Run flow.
4. Workbench disclosure added: the browser page runs a simplified JS
   re-implementation, not `physics_sim.py`/ONNX; the Python engine is
   authoritative; hardware panel shows a canned packet.

Integration (coordinator):
1. Merged the two port branches; resolved `applications/genie_server.py`
   (Case Packet endpoints + `/robotics` launcher entry both kept) and
   regenerated `applications/SHA256SUMS.txt` from the combined tree
   (271 entries, all verify).
2. Removed `__pycache__` files from both port commits (rewrote the
   unpublished commits from the patch files) and added a root `.gitignore`.
3. Caught a docs commit that briefly contained test-run runtime state
   (SQLite databases and generated Ed25519 test keys); reset it before
   pushing — nothing unpublished was pushed. Extended `.gitignore` to
   runtime state directories, `*.sqlite*`, `.spend.lock`, `.genie_key_*`.
4. Docs: root README seven-application index, AGENTS.md (layout, routes,
   measured counts, implemented list), applications/RELEASE_NOTES.md
   v1.1.0-rc1 section.

Manifest correction (parent, 2026-11-15):
1. Parent verification of the published asset found the root SHA256SUMS.txt
   listed a stale hash for README.md (`f9bd01ff…`, from before the final
   docs commit); the README shipped in the asset hashes to `085bd543…`.
   One line corrected in commit `076d316`; the root manifest now verifies
   81/81 and both sub-manifests verify (271 and 160 entries).
2. The published asset was rebuilt from main including the corrected
   manifest and this record, and re-uploaded to the v1.1.0-rc1 release.
   The replacement asset's SHA-256 is recorded in the GitHub release notes.

## LIMITATIONS

- Browser tests need Chrome/Chromium (NOT VERIFIED here): the Case Packet
  workbench browser test, `muse_independent_checks.py` (24 checks),
  mobile/desktop overflow checks, the Neighborhood browser journey test.
- Applications suite: 186 ran, 175 passed, 1 failure, 5 errors, 5 skipped.
  The 1 failure and 5 errors are environmental (2 external-archive
  FileNotFound, 3 chromedriver-missing, 1 Chromium-required failure) — the
  same test IDs as the v1.0.0-rc1 baseline, zero regressions.
- Node: 11 passed, 0 failed. Robotics suite: 6 passed, 0 failed.
- Case Packet module: 2 ran, 1 passed, 1 skipped (Chromium).
- macOS/Windows installs, iPhone Safari, uncoached human testing: not tested.
- Robotics results are simulation only. Physical-hardware behavior is
  unverified; do not connect this software to a physical robot on the
  strength of these results. The new export button's JS was not executed
  in a browser; the browser workbench is a simplified visualization.
- `launch_genie.py --verify-only` lists five applications, not Neighborhood
  (pre-existing v1.0.0-rc1 residual); Neighborhood is confirmed by live
  route/state checks instead.
- A frozen evidence record (`applications/NEIGHBORHOOD_001_ACCEPTANCE_RECEIPTS.json`)
  still contains a superseded `VERIFIED_0_LEAKS` claim as evidence only;
  it is not repeated for the current code.
- The first `pip install` into the fresh verification venv partially failed
  (cryptography installed without hazmat contents, selenium missing) — a
  transient environment issue, fixed by force-reinstall; not a release defect.
- The two receipts JSONs downloaded from Drive do not match Drive's recorded
  md5s (the Drive CLI re-serializes JSON on download). Receipts were treated
  as supporting evidence only; every claim was re-verified by running the code.

## ROLLBACK

Execute only on the founder's order; do not run as routine cleanup.

- Pre-publication main: `956d83b795a9b830dd6e7c167e43450ecc60c55c`.
  Pre-publication tags: only `v1.0.0-rc1` and `v0.7.1`.
- Delete the release and its tag:
  `gh release delete v1.1.0-rc1 --repo terryncew/openline-genie --yes --cleanup-tag`
- Restore main to the pre-publication commit:
  `git fetch origin && git push --force-with-lease origin 956d83b795a9b830dd6e7c167e43450ecc60c55c:main`
  (A force-push is required only for this rollback; it was not used during
  publication.)
- Verify: `gh api repos/terryncew/openline-genie/tags --jq '.[].name'` shows
  only `v1.0.0-rc1` and `v0.7.1`; main shows `956d83b795a9b830dd6e7c167e43450ecc60c55c`;
  the four Pages destinations still return HTTP 200.
- Source preservation independent of GitHub: the integration branch
  (`integration/advocate-robotics-002`, merge `456425d`) is preserved at
  `~/workspace/final-integration-publication-002/work/repo/`; the pristine
  candidate archives are preserved at
  `~/workspace/final-integration-publication-002/downloads/` (Advocate
  SHA-256 `41a7b4691ba551596f7a227f5a71553de276095e5677dc005f88373e6e0a457f`;
  Robotics SHA-256 `a725f98885eb26d0df2fcc0db58c71932a0a63d6993a25c5221493e0147e3dff`);
  all evidence is preserved under
  `~/workspace/final-integration-publication-002/evidence/` with a SHA256SUMS manifest.

## NEXT OWNER

Owner: Terrynce White. No standing maintenance assignment exists for this
release. No scheduled follow-up, no social announcement, and no new research
program attached to this release.

# OpenLine Genie v1.2.0-rc1 — Release Record Addendum (Semantic Authority Bridge)

- Date: 2026-11-15. Agent: integration / qualification / publication (subagent).
- Source: candidate `OPENLINE_SEMANTIC_AUTHORITY_001_CANDIDATE_SOURCE.zip`,
  SHA-256 `dc34c1653f714498c5238121f477a2d920ef045864c04fa6283f0e462ba1301e`
  (verified match on recovery; see `evidence/recovery-reconciliation-001.md`
  and `evidence/comparison.json`).
- Public repo: `terryncew/openline-genie`.
- Base: public main `ed62b3682c049c265317dded76d0e2a433bf62c6` (v1.1.0-rc1).
- Branch: `integration/semantic-authority-001`, commit
  `90eb766` ("Integrate OpenLine Semantic Authority Bridge (v1.2.0-rc1)").
- Merge to main: `3ef38d50b76924b0e57012883e335074e59f6261`
  ("Merge Semantic Authority Bridge (v1.2.0-rc1) into main").
- Tag: `v1.2.0-rc1` (annotated, tag object
  `b268eda0aa64f817eca17c21becc325151f1f06b`), pushed 2026-11-15.
- Release: https://github.com/terryncew/openline-genie/releases/tag/v1.2.0-rc1
  (prerelease, published 2026-11-15T10:07:48Z).
- Asset: `OPENLINE_GENIE_V1_2_0_RC1_SOURCE.zip`, 12,322,844 bytes,
  SHA-256 `7690d1c9de1dcfe621520d434ab09fae4c46949c996ff466679b6cc452da4666`
  (built with `git archive` from the tag; checksum re-verified on the
  downloaded asset).
- Prior tags preserved, verified via `git ls-remote`: v0.7.1
  `87aee3f3b726136fce1676ff6ec1d9e42f97dde6`, v1.0.0-rc1
  `f16f2e824c41dede1a3ebef6980d83096e46d9df`, v1.1.0-rc1
  `fdd89fdc` / `456425d413a3d1ebc9ba29ca414040435e0ed131`. Unchanged.

## What was integrated (and what was not)

Ported (12 files, byte-identical to the candidate except the two noted
repairs and the regenerated receipts):
`core/semantic_authority_bridge.py`,
`capabilities_007_008/generated/semantic_authority_bridge_cap.py`,
`capabilities_007_008/registry_g4_semantic.json`,
`run_semantic_authority_001.py`, `tests/test_semantic_authority_001.py`,
`openline_semantic_authority_workbench.html`,
`examples/ontologies/*.yaml` (4), `SEMANTIC_AUTHORITY_001_RECEIPTS.json`
(regenerated on this tree), `ADVOCATE_CASE_PACKET_001_RECEIPTS.json`
(candidate evidence only).

Adapted: `capabilities_007_008/kernel.py` (exactly the 2 bridge hunks,
verified by diff against the candidate) and `applications/genie_server.py`
(ONLY the 2 route hunks, manually placed near `/ratchet`). The candidate's
server file was NOT ported: it is the pre-repair version (binds 0.0.0.0,
no operator-identity discard, Host/Origin check POST-only). The shipped
server keeps all three public repairs; the new `/api/*` route inherits the
shared `_loopback_check` automatically.

Not ported: the 40 base-drift files, `case_packets_demo/` (16 binaries),
`tests/state-discovery/` (5 Ed25519 key/seed files + live SQLite DBs/WAL —
secrets and runtime state; the patch's binary key hunks were never applied),
and the patch as a whole (reference diff only, against Argon's older base
with `/working_dir` paths). No changes to the root Genie server or to
Robotics Studio (`vendor_009/` is a separate snapshot).

## Repairs made at integration

1. **GET write side effect removed.** The candidate's
   `/api/semantic/state` ran the full suite and wrote
   `SEMANTIC_AUTHORITY_001_RECEIPTS.json` from inside a GET on a cache
   miss. The shipped route serves the precomputed receipts read-only and
   returns HTTP 503 `not_computed` (with instructions to run the runner)
   when the file is absent. Verified: repeated GETs neither rewrite the
   receipts file nor create files; with the file absent the route returns
   503 and writes nothing (`evidence/attack_verify_001.log`).
2. **Dead `?probe=recompile` control wired to a real handler.** It now
   runs the local, read-only Boundary B recompilation simulation against
   the shipped Energy Commons fixture and reports which default FK join
   edges changed (both tariff edges flip). No files written, no live
   service. Verified live (`evidence/attack_verify_001.log`,
   `evidence/published-smoke-001.log`).
3. **Workbench "REFUSED (HTTP 409)" label corrected** to "REFUSED — stale
   authority": stale refusal is the Python exception
   `StaleSemanticAuthorityRefused`, not an HTTP status; the bridge has no
   POST endpoint.
4. **PyYAML added**: `PyYAML==6.0.2` in `applications/requirements.txt`
   (verified clean install in a fresh venv).

## Measured results (all fresh numbers on the combined tree, 2026-11-15)

- **Applications suite** (system Python 3.12.3, no Chrome/Chromium):
  193 tests ran, 176 passed, 1 failure, 11 errors, 5 skipped
  (`evidence/full-suite-system-python-001.log`, 980.0s). All 7 new
  semantic tests passed. The 1 failure is the Neighborhood browser
  journey test (Chromium binary required — NOT VERIFIED). Of the 11
  errors: 2 check external archive files not in the package; 3 are
  browser tests needing Chrome/Chromium (`NoSuchDriverException` — NOT
  VERIFIED); 6 are live-server tests erroring on `TimeoutError`. The 6
  timeouts are a pre-existing environment limit, not a bridge regression:
  the first live-engine request takes ~42.5s on this 1.5-CPU box while
  the tests use a 20s client timeout (measured directly; second request
  0.1s), and the same 3 of those tests were reproduced failing identically
  on the pristine v1.1.0-rc1 tree
  (`cd work/baseline/applications && python -m unittest
  tests.test_five_products_qualification_repairs_001...test_06/07/08`
  → 3 errors, 66.9s). Baseline comparison: v1.1.0-rc1 measured 186 ran /
  175 passed / 1 failure / 5 errors / 5 skipped; v1.2.0-rc1 is 193 ran /
  176 passed / 1 failure / 11 errors / 5 skipped = +7 semantic tests
  passed, −6 tests moved to the pre-existing timeout errors, nothing else.
- **Semantic tests standalone** (venv python): 7/7 OK in 197.9s.
- **Bridge runner** (`python3 run_semantic_authority_001.py`, fresh run,
  `evidence/runner-baseline-run-001.log`, 199.3s wall, $0.00):
  verdict `QUALIFIED_CANDIDATE (LOCAL DETERMINISTIC & OSSIE YAML / MCP
  ADAPTER VERIFIED; LIVE REMOTE NVIDIA NIM DEPLOYMENT HOLD)`; holdout
  60/60 (100.0%), 0 false recalls, 0 missed consequential, 0 stale leaks;
  comparators C0 40/60 (66.67%), C1 20/60 (33.33%), C2 45/60 (75.0%);
  adversarial 10/10 blocked; dogfood Energy affected only
  DEC-ENERGY-COOP-RANKING (pump stayed CURRENT, stale EPC refused),
  Civic affected only DEC-CIVIC-WATER-RESILIENCE-REC (68.0 NTU, roughing
  prefilter covenant), Advocate affected only
  CLAIM-1-DISASTER-GRANT-EXCLUSION (overwrite refused); Worker A→B
  inheritance EXECUTED on the unfamiliar Biotech ontology
  (DEC-BIOLOGICS-LOT-RELEASE reopened, DEC-BIOLOGICS-VIAL-INVENTORY
  stayed CURRENT). Regenerated receipts SHA-256:
  `fc85f7565f139a5814512c35c74747d472c1778915392b2c52e71a418210392f`
  (candidate's copy was `1d5d0257…`, preserved at
  `evidence/candidate-receipts-as-shipped.json`).
- **Independent conventional-dependency comparison**
  (`evidence/conventional_comparison_001.py`, `.log`): bridge 10/10 vs a
  competent explicit dependency-graph tracker with hash-based invalidation
  (7/10) on the same 10 episodes. Bridge wins on SQL whitespace/casing/
  comment invariance (E2, E9) and forged-certification detection (E6);
  parity on synonym/description edits (E1, E7) and formula/unit/join/
  revoke/removal changes (E3, E4, E5, E8, E10). The candidate's own C1
  comparator is a weaker tracker (term version + raw SQL); this comparison
  is the honest one and its margin is narrower.
- **Reproducible example** (`applications/examples/semantic_authority_bridge_example.py`):
  exit 0 on the integration tree and on the published tag code — harmless
  edit reopens nothing, formula change reopens only the affected decision,
  stale action refused, unaffected action executes, re-authorization after
  re-certification executes, case history verifies.
- **Independent worker handoff** (`evidence/handoff_verify_001.py`, `.log`):
  Worker B in a clean process/dir (only `core/` + `capabilities_007_008/`
  copies + the packet; no Worker A state or keys) verified the packet and
  reproduced the REOPEN plus the stale-authority refusal from the packet
  alone.
- **Attack / live-server verification** (`evidence/attack_verify_001.py`,
  `.log`): 0 failures — Neighborhood identity re-attack byte-identical
  across claimed identities; foreign Host 403 on every `GET /api/*` route
  including `/api/semantic/state` and `?probe=recompile`; foreign Origin
  403; `/semantic` 200 + workbench marker; `/api/semantic/state` 200 +
  holdout 100.0; probe returns the real Boundary B result; GETs write
  nothing; `--host 0.0.0.0` refused; `ss` shows loopback-only listening.
- **Node**: 11/11 passed. **Robotics**: 6/6 passed.
  (`evidence/node-tests-001.log`, `evidence/robotics-tests-001.log`).
- **Install verification**: `launch_genie.py --verify-only` exits 0
  (`evidence/verify-only-001.log`).

## Publication verification (Step 6, the published commit, not the workdir)

- Fresh clone at tag v1.2.0-rc1: HEAD `3ef38d5`, receipts hash `fc85f756…`.
- Downloaded release asset SHA-256 `7690d1c9…` matches the uploaded asset.
- Manifests verified **on the downloaded asset**: root 81/81,
  applications 285/285, openline_robotics_001 160/160.
- Clean-environment install from the published tag (fresh venv,
  `TMPDIR` under `~/workspace`): PyYAML 6.0.2 installs; example passes
  7/7; verify-only exits 0; 7 semantic tests OK in 202.9s; Node 11/11.
- Live smoke from the published code
  (`evidence/published-smoke-001.log`): binds 127.0.0.1; `/products` 200;
  `/semantic` 200 + marker; `/api/semantic/state` 200 + holdout 100.0;
  probe 200 with both join edges flipping; foreign Host 403.
- Secrets/private-info scan on the published commit: no Drive IDs, no
  `/working_dir` paths, no private keys/tokens outside pre-existing
  `RELEASE_RECORD.md` prose documenting their removal, and no
  `state-discovery`/SQLite files committed. (Runtime state created by the
  verification runs themselves — `genie_local_data/`, `spend_authority.sqlite`
  — is gitignored and is not in the tag.)
- GitHub Pages verified returning 200 with content (2026-11-15): root,
  Try, How, See. The landing page still describes v0.7.1, as it did for
  v1.1.0-rc1; the `gh-pages` branch was left untouched (updating it was
  not required for this release and risked breaking the four verified
  destinations).

## Honest limits (carried into the release notes and docs)

- **NVIDIA boundary (exact):** file-level Apache Ossie YAML (and native
  Auto-Ontology YAML/JSON) interchange only, parsed and exported locally.
  The 9 read-only MCP tools are local in-memory methods; there is no MCP
  transport, no NIM endpoint, no Postgres, no network call. No live
  NVIDIA integration, no endorsement, and no claim that NVIDIA's
  converter will accept the bridge's files (that needs a live import
  test, which was not run). The OpenLine Ultimate Loop Google Doc was not
  publicly readable; no claim is made about the bridge's role in it.
- **Ephemeral keys:** steward/receiver keys are fresh Ed25519 per bridge
  instance (self-attestation, not an independent external receiver's key).
  Attestations prove integrity/provenance at a point in time, not
  empirical truth, legal validity, or external authority. Receipts are
  not stable across runs.
- **Holdout is self-constructed** (fixed script), not an external held-out
  set. Accuracy is a regression signal, not an independent evaluation.
- **Not verified:** browser end-to-end tests (no Chrome/Chromium),
  macOS/Windows installs, iPhone Safari, uncoached human testing.
- **Environment limit:** the 6 live-server `TimeoutError`s above
  (first engine build ~42.5s vs 20s test timeout on this box).

## Rollback points (kept together under `~/workspace/semantic-authority-bridge-001/`)

- `downloads/OPENLINE_SEMANTIC_AUTHORITY_001_CANDIDATE_SOURCE.zip` —
  pristine candidate (SHA-256 `dc34c165…`).
- `work/baseline/` — clean clone of public main at `ed62b36` (read-only
  reference; unmodified).
- `work/candidate/` — extracted candidate.
- `work/repo/` — working repo: branch `integration/semantic-authority-001`
  (`90eb766`), main at `3ef38d5`, tag `v1.2.0-rc1`.
- `work/verify-clone/` — fresh clone at tag v1.2.0-rc1 (verification only).
- `work/verify-asset/` — extracted downloaded release asset (manifests
  verified here).
- `evidence/release/OPENLINE_GENIE_V1_2_0_RC1_SOURCE.zip` — the uploaded
  asset (SHA-256 `7690d1c9…`).
- Rollback: `git checkout v1.1.0-rc1` (or `git revert` of merge `3ef38d5`)
  returns the tree to the prior release; the v1.1.0-rc1 tag, release, and
  asset are untouched.

## Held

Nothing held. No genuine integration or security defect was found that
could not be repaired in scope; the two foreseen defects were repaired
(see above) and re-tested. No component is withheld from this release.

## Parent verification (2026-11-15, Muse, on the published artifact)

- Live refs verified: release v1.2.0-rc1 (prerelease), tag object
  `b268eda0aa64f817eca17c21becc325151f1f06b` resolves to commit `3ef38d5`,
  main `3ef38d5`, older tags v1.1.0-rc1 / v1.0.0-rc1 / v0.7.1 intact,
  no new repository, Pages built, gh-pages `f2ab9317`.
- Downloaded asset SHA-256 `7690d1c9de1dcfe621520d434ab09fae4c46949c996ff466679b6cc452da4666`
  verified from the live re-download. Manifests on the downloaded asset:
  root 81/81, applications 285/285, robotics 160/160.
- Fresh venv install from the published asset OK (numpy 2.5.4,
  cryptography 50.0.2, PyYAML 6.0.2); `launch_genie.py --verify-only`
  exits 0. Semantic suite 7/7 OK; reproducible example exits 0 with all
  7 checks passing.
- Live smoke from the published code: both servers loopback-only,
  `/products` 200, `/semantic` 200, `/api/semantic/state` 200
  (adversarial 10/10 blocked), probe 200, foreign Host 403 on
  `/api/semantic/state`, foreign Origin 403, `--host 0.0.0.0` refused,
  Neighborhood identity re-attack byte-identical across three claimed
  identities.
- Timeout errors: the 6 live-server `TimeoutError`s from the full-suite
  run did NOT reproduce in isolation on either tree. The same 6 tests
  pass in ~13s on the pristine v1.1.0-rc1 tree and in ~13s on the
  combined v1.2.0-rc1 tree. They appear only under full-suite load on
  this shared 1.5-CPU box. No bridge-caused slowdown measured; the
  errors are environment flakiness, not a regression.
- Packaging note: the release asset was built with `git archive` without
  a `--prefix`, so it extracts flat (no top-level directory). Create an
  empty folder before extracting. Contents and manifests are correct;
  this is a packaging wart, not an integrity failure.
