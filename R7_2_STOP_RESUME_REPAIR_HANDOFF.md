# R7.2 STOP/Resume repair — technical handoff for Muse

## Parent and authority boundary

Parent: `OPENLINE_GENIE_v1.2.0_RC2_R7_1_INDEPENDENT_PRIVATE.zip` with verified SHA-256 `643c0bf012a676dc8e6449b825b76382b222dba2ac01d54cb2acf766cf5e06b8`.
The original archive is unmodified. R7.2 remains **private / unapproved / HOLD** until independent live browser reacceptance.

## Reproduction and repair

The original `openline_five_products.html` optimistically displayed Resume while the initial STOP POST was outstanding. In Chromium with intentionally delayed and simulated guarded STOP API responses, the original UI issued CLEAR before STOP and finished stopped (one early clear, zero accepted clears). This is a **mocked HTTP UI timing falsifier**, not a claim about full real-server browser performance.

The revised UI queues an explicit rapid Resume request until STOP returns its authoritative new_epoch, then calls `clear_stop(expected_epoch=that_epoch)`. Server/engine reject stale, malformed, or foreign-epoch attempts while retaining ReceiverGuard's transaction-level check. No automatic retry against a newer STOP.

## Executed local evidence

- SHA-256 and 228/228 SHA256SUMS verified on R7.1 source before repair.
- Three new HTTP/SQLite ReceiverGuard tests pass: own-epoch resumption; a second independent STOP refuses queued stale intent; malformed epoch types never clear STOP.
- Local Chromium executed the real five-product page JS with a guarded mocked API and deliberate STOP delay: normal, intervening STOP, and STOP failure all pass the new behavior. The original R7.1 page failed the normal scenario.
- Targeted original household validation and stop boundaries passed; three new tests passed again under Python `-O`; Node projection suite 11/11 passed.
- Existing SQLite ResourceWarnings were observed in targeted tests; no claim that the full legacy suite is green.
- Chromium localhost network was blocked by this environment. **Actual live-server 1280px and 390px browser integration is NOT independently passed here.** Muse must reproduce it on the frozen R7.2 bytes.

## Muse's required final gate

Hash-verify R7.2 and its source manifest. In a clean browser environment, perform rapid STOP then immediate Resume with no artificial wait (including during first-use seeding) for multiple consecutive runs. Confirm one click resumes, accepted SHA remains unchanged, and any second intervening STOP survives stale queued clears. Also retest R7.1 household bounds, seven apps, Replay, Recall, import/export, offline/CDNs, existing test errors, and load timing. Produce actual browser logs and either GO + PR on the exact accepted source or HOLD + reproducible blocker. No auto-merge/publication.
