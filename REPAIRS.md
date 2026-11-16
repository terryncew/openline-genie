# REPAIRS.md — minor repairs applied by the independent acceptor (Muse)

Source: GPT-6 repaired private candidate, Drive file
`OPENLINE_GENIE_v1.2.0_RC2_GPT6_REPAIRED_PRIVATE.zip`, SHA-256
`4390e64f46e5c08cf20798192bd8b0b61142746bef4640cdf67c9e983cde8335`
(5,215,488 bytes), verified from the acceptor's own download.

Scope of THESE repairs: redaction of private identifiers and removal of a
retired brand label from user-facing surfaces and research docs. No code
logic, no Host/identity/STOP/import/recall/capsule/binding/auth behavior
was changed. Every file below was edited only as described; all other
files are byte-identical to the source candidate.

This tree is NOT publication-ready: two consequential defects in the
Energy decision / recall flow were found live and returned to GPT-6 for
re-acceptance (see `../evidence/GPT6_REACCEPTANCE_PACK_R5_RESTORE_AND_FORM_DEFAULTS.md`
and `../evidence/r5-restore-fix-proposal.patch` in the acceptance
workspace, not in this tree):
- R5-RESTORE: owner review cannot restore CURRENT after two sequential
  single-key accepted changes (review binds recall rows to the current
  SHA only; `authorize_procurement` stays 409 with no owner path out).
- FORM-DEFAULTS: Energy (and Advocate) form inputs show hardcoded seed
  defaults, never the accepted values; a later single-field edit silently
  reverts previously accepted values in untouched fields.
GPT-6 must repair those, re-hash, and the new exact SHA must be
independently re-accepted before any merge, tag, release, or publication.

## 1. Private Drive identifiers redacted
- `FOUNDER_REPORT_CIVILIZATION_APPLICATIONS_001.md` — 14 unique private
  Google Drive file/folder IDs (15 occurrences), each explicitly labeled
  "Drive File / Drive Folder / Drive Doc" in the report's source table,
  replaced with `[private Drive location redacted for public release]`.
  Artifact names, verified SHA-256 digests, and verification statuses in
  the table are unchanged.

## 2. Private local path redacted
- `FOUNDER_CLOSURE_REPORT_001.md` (line 22) — the author's private
  `<isolated_workspace>/src_009`
  workspace path replaced with "an isolated local workspace (private
  path redacted for public release)". Claim unchanged.

## 3. Retired "Be Neighborly" sub-brand removed
The brand was retired from user-facing surfaces in v1.2.0-rc2; the
delivered candidate still presented it in the files below. All
occurrences replaced with the live "ClearCovenant — powered by OpenLine"
identity, or with a neutral reference to the retired working name where
the text is the historical record of the naming decision. The
`/be_neighborly` URL alias is intentionally kept as a compatibility
route (genie_server.py), as is the changelog line in RELEASE_NOTES.md
and the repair record in GPT6_RELEASE_ACCEPTANCE.md, which describe the
removal itself. The boundary test
`tests/test_final_release_boundaries.py` (assertNotIn) is unchanged.
- `CLEARCOVENANT_BOARD_PORTABLE_RECORD.html`,
  `CLEARCOVENANT_COMMUNITY_PORTABLE_RECORD.html`,
  `CLEARCOVENANT_HOMEOWNER_PORTABLE_RECORD.html` — `<title>` and `<h1>`
  (user-facing exported records).
- `PLAIN_LANGUAGE_USER_AND_INSTALLATION_GUIDE.md` — title.
- `CONSUMER_RESEARCH_AND_COMPETITOR_ANALYSIS.md` — title, section
  heading, intro, and the decision paragraph (verdict preserved; the
  retired name is no longer presented as a live subtitle).
- `PRICING_AND_BUSINESS_MODEL_ANALYSIS.md` — title.
- `PUBLIC_LAUNCH_MATERIALS_HOLD_PENDING_AUTH.md` — title, launch
  headline title, launch post intro.
- `core/neighborhood.py` — `PRODUCT_BRAND_IDENTITY`: header comment,
  `working_name_preserved` and `full_display_title` now name the live
  product (the display title is served in generated portable dossiers
  via `export_neighborhood_standalone_dossier_html`), `working_name_tested`
  records the test as `RETIRED_WORKING_NAME_TESTED_2026-11-15`, the
  collision and consumer-tone findings refer to "the retired working
  name", verdict enum updated to
  `ADOPT_CLEARCOVENANT_RETIRED_WORKING_NAME_SUBTITLE`. No code reader
  depends on the old values (verified by grep; only the receipts JSONs
  embed the same dict).
- `run_neighborhood_001.py` — acceptance directive string.
- `openline_009_living_project.py` — one comment, one docstring.
- `NEIGHBORHOOD_001_ACCEPTANCE_RECEIPTS.json`,
  `NEIGHBORHOOD_PORTABLE_EXPORT_IMPORT_DEMOS.json` — the same brand
  identity fields as `core/neighborhood.py` (these files are generated
  from it), plus the directive string where present. The consumer-tone
  finding's rationale is preserved; only the retired brand string was
  removed.

## 4. First-use loading banner now clears once the examples are ready
- `openline_five_products.html` (`renderAll()`) — the loading banner
  ("Preparing the five project examples…") was never cleared after
  seeding completed: `renderAll()` only set the banner when no product
  was present, or on an action result, so a first-time user saw
  "Preparing…" forever even with all five products rendered and usable
  (verified live in the browser on the unrepaired candidate: banner
  still "Preparing…" minutes after `/api/five_products/state` returned
  200 with all five products). Added: once a product is present, if
  the banner still shows the loading text, replace it with "Five
  project examples ready." (class `ok`). Only the loading text is
  replaced, so export/import/review feedback is never clobbered.
  Verified live on the repaired tree: banner visible at 0.2 s,
  products usable at 48.5 s, banner "Five project examples ready."

## Verification after these repairs
- `SHA256SUMS.txt` regenerated LAST from this tree (227 original files
  + this REPAIRS.md = 228 entries); `sha256sum -c SHA256SUMS.txt`:
  all entries OK.
- `python3 launch_genie.py --verify-only` in a fresh venv from the
  pinned requirements only: exit 0, READY, v1.2.0-rc2, seven
  applications ready.
- `tests.test_final_release_boundaries` +
  `tests.test_genie_rc7_adversarial_gate`: 13/13 OK.
- `node --test tests/test_rc6_projection.mjs`: 11/11 PASS.
- ASTRA gate (unchanged script): 3 PASS, 2 REVIEW — both REVIEWs
  resolved by direct measurement as in the unrepaired candidate
  (clean-venv verify-only for the dependency probe; measured trial
  counters with timed elapsed + retired 6x claim for the
  evaluation-counts probe).
