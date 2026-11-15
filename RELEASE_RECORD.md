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
