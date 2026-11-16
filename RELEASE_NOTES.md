# OpenLine Genie `v1.2.0-rc3` — Release Notes

## Summary

v1.2.0-rc3 is the single release candidate produced by merging two lines:

- **R7.2 (authority line, base):** the STOP/Resume epoch-binding repair and the
  household 1..5000 server-side validation, both independently qualified.
- **RC3 (additive line):** the visual-intelligence harness, independent
  evaluation boundary, real-browser functional runner, and offline hardening
  of the Robotics and Ratchet pages.

RC3 on its own regressed all three R7-line authority fixes, so it could not
ship as-is. The merge keeps R7.2's authority paths verbatim and adds RC3's
work around them. Full per-file record: `MERGE_LOG.md` (in the closure
package) and the acceptance report.

## Repairs in this candidate

- **STOP/Resume race (R7.2, GPT-6):** the page queues a Resume clicked while
  STOP is in flight until STOP returns its authoritative new epoch, then
  clears with that exact epoch. Engine and server bind the clear to the
  expected epoch and reject stale, malformed, or foreign-epoch attempts
  (`stale_owner_intent`, `invalid_expected_epoch`); a newer STOP cannot be
  cleared by stale intent, and there is no automatic retry against a newer
  STOP. ReceiverGuard keeps its transaction-level check. Accepting a proposal
  staged before a STOP is refused: STOP revokes pending proposals at once
  (`REVOKED_BY_STOP_EPOCH`), and the accept path additionally rejects any
  proposal whose epoch no longer matches (`proposal_epoch_expired`).
- **Household boundary (R7.1, GPT-6, preserved):** Energy household counts are
  limited to whole numbers from 1 to 5000, matching the published UI. Boolean,
  non-numeric, non-finite, and negative values are refused before staging and
  cannot enter accepted state through the API.
- **Form defaults (R7, preserved):** accepted values survive reloads and
  one-field edits across Energy, Advocate, Civic, and Science.
- **Visual artifact repair (RC3, additive):** `propose_visual_artifact_repair`
  stages a visual/geometric repair into exploratory state under strict
  ReceiverGuard, SpendLedger, and fail-closed visual inspection boundaries.
  It cannot disable STOP, bypass receiver acceptance, forge receipts, or reset
  spending limits; failed inspection never becomes approval; accepted state is
  asserted unchanged on failure and after staging.
- **Evaluation boundary (RC3, additive):** the visual harness carries no
  evaluation authority; the 16 visual cases are regression tests only, not a
  sealed holdout and not a claim of unseen generalization.
- **Real-browser functional runner (RC3, additive):** the mock selenium shim
  is removed; the runner executes real selenium + Headless Chromium suites
  and fails closed on skipped tests.
- **Offline hardening (RC3, additive):** the Robotics Studio and Ratchet
  Workbench pages no longer depend on tailwind/chart.js CDNs.
- **Robotics manifest (closure repair):** `openline_robotics_001/SHA256SUMS.txt`
  was regenerated over the 17 files actually present (17/17 verified). Three
  stale entries referencing files never shipped in this tree (two external
  download archives, one generated HTML) were removed, not fabricated.

## Qualification

Independent qualification of the exact frozen candidate ran on Linux with
headless Chromium. Per-gate results, logs, and browser evidence are in the
acceptance report accompanying this release (closure `REPORT.md`). Pre-merge
baseline (R7.2, for reference): Python suite 237 ran, 1 failure + 18 errors,
all environmental, 0 product failures, 4 skipped; Node 11/11; new race tests
15/15; prompt STOP→Resume 3/3 desktop, 3/3 mobile, 3/3 fresh-server seeding.

## Known limitations (stated, not smoothed)

- Robotics Studio is simulation only. No hardware validation is claimed.
- iOS Safari, macOS, and Windows installs NOT VERIFIED.
- OS-identity security NOT VERIFIED (same-OS-user processes with access to
  the state directory can bypass the process boundary).
- Browser tests NOT VERIFIED where a Chromium binary is absent.
- The static GitHub Pages v0.7.1 preview does not provide the full seven-app
  local runtime.
- First-use seeding can take tens of seconds; under load, the first resumed
  staging action has previously taken up to ~54 seconds. Do not treat a
  missing response as acceptance.
- At 390px the page scrolls after an accept, taking STOP out of the viewport
  until the user scrolls back.

## Status

Release candidate for independent acceptance (GPT-6) and the owner's
authorization. Do not treat this candidate as released until both land.
