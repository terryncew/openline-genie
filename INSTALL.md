# Install OpenLine Genie v1.2.0-rc3 (`1.2.0rc3`)

Local-first visual project builder. No account. No cloud. No subscription.

**Research/beta release candidate.** The seven-app local suite is distinct from the static v0.7.1 GitHub Pages preview. No account or paid model/API key is required for default local operation.

## Prerequisites

- Python 3.10 or newer. Verified here on Python 3.12.3, Linux.
- `pip` and `venv` (standard with most Python installs).
- A modern desktop browser. Headless Chromium (via Playwright) verified in automated tests. Firefox is NOT verified.
- Linux is the verified OS. macOS and Windows are NOT TESTED.
- No paid API key is needed for default use.

## Install

1. Get the release archive: extract the frozen `OPENLINE_GENIE_v1.2.0_RC3_FINAL.zip`
   (or, once published, the source archive attached to the **v1.2.0-rc3** release on
   GitHub at `terryncew/openline-genie`). Work inside the extracted
   `openline-genie/` directory.
2. Create a virtual environment and install the runtime dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

This installs `cryptography` (Ed25519 receipts), `numpy`, `onnxruntime`, `Pillow`, and `selenium` (for Headless Chromium verification). The first install downloads those packages, so it needs network
access. Nothing else is required to run the server. Playwright is optional
and only needed for browser tests; see `pyproject.toml` under
`[project.optional-dependencies]`.

3. Check the install:

```bash
.venv/bin/python -c "import numpy, cryptography; print(numpy.__version__, cryptography.__version__)"
```

## Run

```bash
.venv/bin/python genie_server.py --host 127.0.0.1 --port 8795 --state-dir ./genie-state
```

Then open `http://127.0.0.1:8795/` in your browser.

Flags:

- `--host 127.0.0.1`: loopback only. The server refuses any other host.
- `--port 8795`: local port. Pick another free port if 8795 is taken.
- `--state-dir ./genie-state`: where keys and the SQLite database live.
  Use a real directory if you want your projects to survive a restart.
  Without this flag the server uses a fresh temporary directory each
  start, and your projects do not persist.
- `--enable-paid-model`: OFF by default. Only pass it to opt in to paid
  model dispatch, with the `$5.00` local spend cap. Without it the server
  runs the deterministic local synthesizer at `$0`.
- `--no-model`: forces deterministic mode even if paid model use is
  enabled in the environment.

Stop the server with Ctrl-C.

## Requirements and actual support

- The full interface runs on the same computer as its Python server. It binds to **127.0.0.1 only**, so an iPhone cannot browse another computer's server without a separate, security-reviewed deployment. Do not set `--host 0.0.0.0`.
- Initial `pip install` uses the internet for packages (`cryptography`, `numpy`, `onnxruntime`); default running uses no paid APIs. Robotics dashboards may require public CDN assets for some charts; inaccessible CDNs can produce chart errors, although the simulator backend still runs. (The Robotics Studio and Ratchet Workbench pages served by `genie_server` no longer depend on tailwind/chart.js CDNs; the standalone copy served by the robotics server still loads Tailwind, Chart.js, and Google Fonts from CDNs and needs network access for full styling and charts.)
- On first use, five example products may require tens of seconds of initialization. A loading banner is displayed; STOP is usable before completion. Under load, the first resumed staging action has previously taken up to approximately 54 seconds. Be patient, but do not treat a missing response as acceptance. The local server is one-operator software, not a network service for multiple users.
- New server-side input check: Energy household counts are limited to whole numbers from **1 to 5000**, matching the published UI. Invalid requests fail before staging and cannot enter accepted state through this path.
- STOP/Resume repair: a Resume clicked while STOP is in flight is queued until STOP returns its authoritative epoch, then clears with that exact epoch. A newer STOP cannot be cleared by stale intent. Accepting a proposal staged before a STOP is refused.

## First use

1. Open `http://127.0.0.1:8795/`. Three demo projects are already there.
2. Build a bakery. Type: `Design a small neighborhood bakery`. The
   builder works out the binding constraint (the oven, at 174 loaves/day)
   and shows the paths that raise output.
3. Explore a change. Pick the second-oven path. The preview shows 240
   loaves/day with staff as the new bottleneck. Accepting it records the
   change with a signed receipt. Rejecting it leaves the accepted work
   untouched.
4. Try STOP. STOP freezes new proposals and accepts. Clear STOP resumes.
   Accepted work is never lost by STOP.
5. Export. Export gives a standalone HTML file, a CSV, and a portable
   JSON bundle with the accepted SHA-256 and the receiver receipt. Import
   the bundle on a fresh install to recover the project. Import stamps
   provenance into the copy, so its SHA differs from the source by design;
   the provenance record keeps the source SHA and the verification badge.

## What requires the local receiver

Every consequential step goes through the local receiver (`ReceiverGuard`):
proposing, accepting, rejecting, STOP, worker replacement, export, import.
The receiver checks authority, epoch, and base state before anything
commits, and signs a receipt for what it accepted or refused. There is no
way to accept a change without the receiver. The browser UI alone cannot
write accepted state.

## Honest limitations

- Loopback only. The server binds `127.0.0.1` and refuses other hosts.
  It is not reachable from another machine.
- Same-user boundary. Signing keys (`.genie_key_*`, mode `0600`) and the
  SQLite database live in the state directory. Any process running as the
  same OS user can read them. Separate OS users, containers, or hardware
  keys are needed for a stronger boundary.
- `$0` default. Paid model dispatch is OFF unless you opt in. The local
  `$5.00` spend cap is enforced only for the local adapter, not for API
  use outside it.
- iPhone Safari is NOT TESTED. Uncoached human testing is NOT TESTED.
- macOS and Windows installs are NOT TESTED.
- The deterministic builder covers the built-in domains (bakery,
  community garden, quoting, robot academy, small synthesized apps).
  Unfamiliar requests without a paid model fall back to the local
  synthesizer, which may produce a generic app.
- Robotics is a simulation, not hardware qualification. Static preview is not the seven-app local runtime. No paid model is used unless explicitly enabled and configured.
- Before using public-data or community applications to make legal, medical, civic, safety, financial or physical engineering decisions, get qualified review. Demonstration results and quoted benefits are modeled, not real-world guarantees.

## Verify your install

```bash
sha256sum -c SHA256SUMS.txt
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_rc6_projection.mjs
```

Measured on the qualification host (Linux, Python 3.12.3, 1.5-CPU shared cell):
252 tests collected, 247 ran. Normal mode: 226 pass, 4 failures, 17 errors,
0 skipped, ~166s. The failures/errors are environmental or documented
mismatches, not product failures — see the acceptance report for the
per-error reconciliation (missing pinned Idea Layer script, missing external
freeze archive, no system Chromium binary, one known fail-closed 409
mismatch, one flaky timing race in test_12 now fixed by accepting both legal
outcomes of an in-flight read). Node: 11/11 pass. The full suite takes
minutes, not seconds, on this host; with a browser driver present it takes
~305s. Browser tests need a Chromium binary; the qualification host has none
at `/usr/bin/chromium`, but the Playwright-cache Chromium 131 + ChromeDriver
131 pair works via the `GENIE_CHROME_PATH` / `CHROMEDRIVER_PATH` overrides
(`functional_runner.py` 6/6 with them).

## Uninstall

1. Stop the server.
2. Delete the extracted directory.
3. Delete the state directory you passed with `--state-dir`, if you made
   one. That removes all projects, keys, and databases.
4. Delete the virtual environment (`.venv` inside the extracted
   directory goes with it in step 2). Remove the named state directory
   **only if you intentionally want to erase all local projects and keys**.
   Preserve a signed export first if you need future access.

No system files are changed. Nothing is installed outside the directory
you extracted and the state directory you chose.

## License

Apache License 2.0. See `LICENSE` in the release archive. OpenLine
branding and trademarks are governed separately and are not licensed
under Apache 2.0.


### Security and import boundary

Run `python3 launch_genie.py --host 127.0.0.1` on a computer you control.
Never expose port 8795 to your LAN, Internet, reverse proxy, or shared account.
There is no per-user login. Neighborhood demo identity is configured **at server
startup**, not through browser query parameters. Board mode requires a separately
controlled local session and appropriate data authority, for example:

```sh
GENIE_NEIGHBORHOOD_OWNER_ROLE=board python3 launch_genie.py --host 127.0.0.1
```

The example above selects a *local simulation persona*; it does **not** verify
real board membership. Do not use it to process another resident's private
records. For normal use, leave this environment variable unset.

A new accepted assumption changes decision standing to `Needs another review`.
The explicit Review action verifies only local calculation and owner acceptance.
If supporting external evidence has been revoked, the system refuses to clear it.

To restore a signed project into an existing local installation, the imported
project must be newer than the currently accepted version. Genie requires the
exact current version/SHA to authorize overwrite. Otherwise it refuses and
retains all accepted work. Install on a fresh state directory for older snapshot
inspection rather than using overwrite to roll authority backward.
