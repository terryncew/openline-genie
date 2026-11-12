# OpenLine Genie — Owner Guide (RC6)

Plain-language guide to using Genie. Genie builds a working app from a
sentence, shows you the plan as a living picture, and only keeps the
changes you accept. Nothing it proposes changes your accepted work
until you say so.

## What Genie is

You describe what you want. Genie builds a working single-file app,
tests it, and shows it to you. You can explore changes (a second oven,
a different shift pattern), see what each change would do, and accept
or reject each one. Accepted work is kept, signed, and survives the
worker being replaced. Rejected work disappears without touching what
you accepted.

Genie is not the Living Projects Studio. The Studio's workers are
scripted demonstrations. Genie's workers are real: they call a model
(Claude Haiku) to build and revise the app. Do not confuse the two.

## Start the server

From the source tree:

```bash
python3 genie_server.py --port 8795 --state-dir /tmp/genie-state
```

Then open `http://127.0.0.1:8795/` in a browser. The server only
listens on your own machine (loopback). That is not a security
boundary in the operating-system sense: anything already running on
your machine can reach it. Do not expose the port to a network.

The first run needs no model call for the built-in bakery: click
"Design a neighborhood bakery" on the wish screen and the demo bakery
loads from the engine's own numbers.

## Ask for a project

Type one sentence, for example "Help me build a neighborhood bakery."
Click Build. A real model build takes about half a minute and costs a
few tenths of a cent. The spend line at the top of the page shows the
running total against the $5.00 cap. If the build fails, nothing is
kept and you can try again.

You can also build without the model (deterministic bakery only) by
posting to `/api/build` with `"use_model": false`. That costs nothing.

## Explore changes

The picture shows your project as connected parts. Each part shows its
number: how much it can do per day. The part that limits your output
is marked LIMIT.

- Tap a part to see it in detail.
- The "Try one change" card offers one change at a time. It shows the
  numbers before and after, and what the next limit would be.
- The discovery card appears on its own when it finds something
  surprising. For the bakery it says the shift change looks useless
  alone but is worth +40 loaves a day with another oven. That is real
  arithmetic from your accepted project, not a guess. Exploring it
  creates a preview only.
- "Explore" makes a preview. A preview changes nothing you accepted.
  The picture marks previews clearly, and the banner tells you the
  original numbers are kept.

## Accept or reject

- **Accept** keeps the change. The accepted version moves forward and
  a signed receipt records it.
- **Reject** throws the preview away. Your accepted work stays exactly
  as it was. You can reject at three places, and they do different
  things: "Discard preview" (top) throws away every unaccepted
  preview; "Reject this change" (in the detail panel) rejects only the
  change you are looking at; "Keep what I have" (on a choice card)
  throws away previews and keeps your accepted baseline.
- Nothing is accepted unless you accept it. Dismissing the discovery
  card changes nothing.

## STOP

The STOP / Freeze button freezes all changes. While STOP is on, no new
change can be proposed or accepted, and no build can run. Rejecting
still works. Your accepted work stays exactly as it was. Click "Clear
STOP" to resume. STOP stays directly tappable by mouse, touch, and
keyboard at every screen width even while the discovery card is open:
when the page footer is in view the card lifts above it instead of
covering STOP.

Use STOP when something looks wrong and you want everything to hold
still while you look.

## Replace the worker, close, reopen

- **Replace worker** (in Details) retires the current worker and starts
  a new one. The old worker cannot do anything afterwards. Your
  accepted work is unchanged, and the new worker can carry on.
- **Close** shuts the project. Nothing can change while it is closed.
  **Reopen** brings it back with the accepted work intact.

## Export

The "Export app" button at the top downloads your accepted work as one
HTML file. It runs on its own in a browser with no server and no
internet. It contains only accepted work: previews and simulated
numbers are never exported. Keep the file; it is your project.

## What the words mean

- **Accepted — saved**: this is your kept work, recorded with a signed
  receipt.
- **Preview**: a change you are looking at but have not accepted.
- **RECEIVER VERIFIED**: the receiver checked the signed receipt
  against the key it pinned when the project loaded. It means the
  record is genuine, not that the business numbers are guaranteed.
- **±7%**: a stated planning margin around the numbers, not a measured
  error.
- **Sim**: a simulated preview. It shows what would happen; it changes
  nothing until it goes through propose and accept.
- The Details panel ("What the labels mean") defines every label
  in the app.

## What Genie can and cannot do

Can:
- Build a working single-file app from a short description.
- Show the plan, test changes as previews, and keep only what you accept.
- Prove what was accepted, rejected, stopped, and replaced, with
  signed receipts you can check.
- Replace the worker without losing accepted work.
- Export accepted work as a standalone file.

Cannot:
- Guarantee the business numbers. Demand (320 loaves a day), shop
  capacity (300), and prices are assumptions you or the engine stated.
  Throughput and profit are computed from those assumptions only.
  Genie does not measure a real bakery.
- Build any unfamiliar domain on demand. It has been shown working for
  a bakery, a barber booking tool, and a community fridge tracker. A
  new domain may fail; a failed build costs a little money and keeps
  nothing.
- Undo something that already happened outside Genie. A receipt proves
  what the receiver recorded. It cannot cover actions that never
  crossed a recording boundary.
- Revoke instantly. In-flight permissions live to their 60-second
  lifetime. STOP freezes new changes; it does not rewind the world.
- Run in a real browser on Safari (unverified), or as a shared service.
  The server is loopback-only by design.

## Honest limits of this release

- **Discovery-first is NOT YET VERIFIED.** The discovery card works and
  its numbers are real, but no first-time user who had never seen Genie
  has yet used it and found a useful consequence they did not ask about.
  Until that happens, "discovery-first" is a design claim, not a proven
  experience.
- **The Steve Jobs gate is NOT YET VERIFIED** for the same reason: no
  naive human participant has been available. The usability walkthrough
  so far is an AI simulation, not a human test.
- **The demo video shows the UI before the last 12 fixes.** The engine
  states it shows (accepted work, rejections, STOP, replacement) are
  unchanged, but two labels you will see in the video are old: a button
  that read "(+174)" now reads "(output +66/day)", and Export has moved
  from the page footer to a button at the top. The current UI is the one
  in the app, not the video.
- **One browser test is flaky, not stale.** The old `test_06` customer-journey
  test looked for buttons the current UI no longer has; that requirement was
  retired by recorded decision and the journey was rewritten as the new
  `test_06_living_world_journey.py` regression (1/1). The rewritten test has
  a known test-side race in its Reject leg (the UI diagnostic can still read
  the old number when the test reads it, while the engine state is already
  correct); it fails occasionally under load and passes on retry. It is a
  test problem, not a product problem.
- **The empty-text anomaly is unexplained.** A bike-repair build once
  failed twice with empty model responses and the cause could not be
  seen through the adapter. The adapter now logs the response
  structure before failing, so a repeat can be diagnosed, but the
  original failure has no explanation. If a build fails this way,
  report it with the time and the prompt; do not retry blindly.

## If something goes wrong

- A build fails: check the spend line and try once more. If it fails
  the same way twice, stop and report the prompt and the time.
- The page shows an error: reload. Your accepted work lives on the
  server, not in the page.
- STOP is on and you cannot change anything: that is STOP working.
  Clear it from the button at the top.
- You accepted something by mistake: propose the reverse change and
  accept that. There is no undo button; acceptance is the record.

## Cost

Every model call is logged in `SPEND_LEDGER.md` and `spend.json` in
the project folder, with message id, tokens, and cost. The cap is
$5.00 total. Haiku only. Model spend is tracked against the cap as
calls are made; deterministic builds and all tests cost $0.

The cap is enforced by reservation: before a model call the adapter
reserves the call's worst-case cost against the cap and writes that
reservation to the ledger before dispatching. If the provider's reply
carries usage numbers, the reservation is reconciled to the actual
cost; if usage is missing, the worst-case amount stands as the
recorded cost rather than $0. A call the provider explicitly refuses
costs $0. So the running total can overstate true provider spend
when usage goes missing, but it can never understate it.

## Final Product Pass (RC7 r4) — Reusable Living World & Interactive Controls

- **First-5-Seconds Orientation Strip (`#fiveSecStrip`)**: Directly below the project title, four quiet badges state (1) what you are building, (2) what Genie created (`Runnable App + Living Model` vs `Verified State + Quarantined Snapshot`), (3) the active bottleneck and how to inspect or edit it, and (4) who controls the result (`You decide · Receiver Verified · STOP ready`).
- **Reusable Multi-Domain Living World**:
  - **Hearth & Crumb Bakery (`bakery`)**: Projects steam-injected hearth deck ovens (`174 loaves/day` baseline), shaping bench & baker shift (`240 loaves/day`), cold retarder proofing rack (`280 loaves/day`), storefront counter (`300 loaves/day`), and neighborhood demand (`320 loaves/day`).
  - **Sunnyvale Community Garden (`garden`)**: Projects the rainwater cistern & drip header (`105 lbs/week` baseline), volunteer crew (`135 lbs/week`), 4-family raised crop beds (`150 lbs/week`), cold-rinse wash shed (`180 lbs/week`), and neighborhood share demand (`200 lbs/week`), surfacing the `drip_mulch + weekend_workday` super-additive synergy (`+15 lbs/week` bonus).
  - **ResidualMLP Checkpoint Optimizer (`neural_model`)**: Projects locally executable neural checkpoints (`gen0_baseline.npz` `40.4%` -> `gen3_calibrated_int8.npz` `64.2%`, `7,444B -> 1,623B`) across `Spectral SVD & GELU` (`52 -> 92 frontier_pts`), `Curriculum Filter` (`64 -> 90 frontier_pts`), `INT8 & Temp Calib` (`74 -> 94 frontier_pts`), and `Evaluator Holdout` (`95 frontier_pts`), surfacing the `spectral_repair + curriculum_finetune` synergy (`+10 frontier_pts` bonus).
  - **Generic Unfamiliar Projects (`generic`)**: Projects an honest operational-flow diagram (`Typed Inputs`, `Formula & Rules`, `Active Records`, `Portable App & Export`) from your synthesized app without pretending Genie built a bespoke 3D machine.
- **Interactive Assumption Editor (`⚙ Assumptions`)**: Tap any station (such as the Oven, Staff, Ingredients, Cistern, Volunteer Crew, or Neural Stage) and click `⚙ Assumptions` in the Inspector to view and edit the underlying operating numbers. Clicking `Preview assumption change →` sends a real `POST /api/propose` to the engine, previews the updated capacities and bottleneck on the canvas while keeping your accepted baseline untouched, and lets you **Accept** or **Reject** the change. Invalid numbers (zero or negative capacities/cycle times) fail closed.
- **Non-Canvas Accessible Station View (`☰ Stations`)**: Click `☰ Stations` in the toolbar (or navigate via keyboard/screen reader) to open the synchronized station list (`#worldFallbackPanel`). Every station, assumption editor, preview, Accept, Reject, and STOP control works 100% without relying on 2D canvas rendering.
- **Portable Bundle Import & Worker Model Switcher (`Details`)**: Open `Details` to import a portable bundle JSON (`Import portable bundle`), view runnable-artifact trust (`TRUSTED_LOCAL_RECEIVER` vs `UNTRUSTED_IMPORTED_HTML_QUARANTINED`), or switch the AI worker model (`Switch model`) while preserving accepted state byte-identically.
