# OpenLine Genie v1.2.0-rc2 — local seven-app installation

**Research/beta release candidate.** The seven-app local suite is distinct from the static v0.7.1 GitHub Pages preview. No account or paid model/API key is required for default local operation.

## Requirements and actual support

- Python 3.10+ and pip/venv; Node.js only for the projection test suite.
- Tested engineering environment: Linux. macOS, Windows, iPhone Safari and physical robot hardware have not been independently qualified for this archive.
- The full interface runs on the same computer as its Python server. It binds to **127.0.0.1 only**, so an iPhone cannot browse another computer's server without a separate, security-reviewed deployment. Do not set `--host 0.0.0.0`.
- Initial `pip install` uses the internet for packages (`cryptography`, `numpy`, `onnxruntime`); default running uses no paid APIs. Robotics dashboards may require public CDN assets for some charts; inaccessible CDNs can produce chart errors, although the simulator backend still runs.

## Install and start

Extract the **R7.2 frozen acceptance ZIP** into a new directory. Open a terminal in its `openline-genie/` directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launch_genie.py --verify-only --state-dir ./genie-local-state
.venv/bin/python launch_genie.py --state-dir ./genie-local-state
```

Open `http://127.0.0.1:8795/products` for Energy, Advocate, Commons, Science and Civic; `/neighborhood` for ClearCovenant and `/robotics` for Robotics Studio. `http://127.0.0.1:8795/` is the project map. Accepted work persists under the specified state directory. Stop the terminal with Ctrl+C; do not delete the state directory if you want your records.

On first use, five example products may require tens of seconds of initialization. A loading banner is displayed; STOP is usable before completion. Under load, the first resumed staging action has previously taken up to approximately 54 seconds. Be patient, but do not treat a missing response as acceptance. The local server is one-operator software, not a network service for multiple users.

## Verify from extracted source

```sh
sha256sum -c SHA256SUMS.txt
node --test tests/test_rc6_projection.mjs
python3 -m unittest -v tests.test_r5_form_defaults_regressions.TestR5FormDefaults.test_14_api_household_domain_matches_browser_and_cannot_be_accepted
```

The entire research/legacy Python suite may take many minutes and is **not expected to be completely green in an isolated release installation**: the preceding R7 candidate ran 214 tests with 0 failures, 16 errors and 4 skips, including missing Selenium, unavailable pinned Idea Layer/freeze archive inputs, and resource-dependent live-server timeouts. Those are recorded as unverified, not as passes. R7.1 adds one independent regression test; do not infer an independently replayed full-suite result from its presence. Browser testing requires separate test dependencies and an allowed local Chromium environment.

## Boundaries and corrections

- The local receiver enforces STOP, owner-controlled effects, signed receipts and Decision Recall within its supported local model. Same-OS-user processes with access to the state directory can bypass this process boundary; hardware protection and multiuser security are not established.
- New R7.1 server-side input check: Energy household counts are limited to whole numbers from **1 to 5000**, matching the published UI. Invalid requests fail before staging and cannot enter accepted state through this path.
- Robotics is a simulation, not hardware qualification. Static preview is not the seven-app local runtime. No paid model is used unless explicitly enabled and configured.
- Before using public-data or community applications to make legal, medical, civic, safety, financial or physical engineering decisions, get qualified review. Demonstration results and quoted benefits are modeled, not real-world guarantees.

## Uninstall

Stop the server, delete the extracted program and `.venv`; remove the named state directory **only if you intentionally want to erase all local projects and keys**. Preserve a signed export first if you need future access.
