# Install OpenLine Genie v0.7.1

Local-first visual project builder. No account. No cloud. No subscription.

## Prerequisites

- Python 3.10 or newer. Verified here on Python 3.12.3, Linux.
- `pip` and `venv` (standard with most Python installs).
- A modern desktop browser. Chrome and Firefox verified in automated tests.
- Linux is the verified OS. macOS and Windows are NOT TESTED.
- No paid API key is needed for default use.

## Install

1. Get the release archive. Open the OpenLine Genie repository on
   GitHub (`terryncew/openline-genie`), go to **Releases**, and download
   the source archive attached to the **v0.7.1** release. Extract it and
   work inside the extracted directory. The v0.7.1 release must exist
   before this step works; if there is no v0.7.1 entry under Releases,
   the release has not been published yet.
2. Enter the extracted directory.
3. Create a virtual environment and install the runtime dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

This installs `cryptography` (Ed25519 receipts) and `numpy` (local model
math). The first install downloads those packages, so it needs network
access. Nothing else is required to run the server. Playwright is optional
and only needed for browser tests; see `pyproject.toml` under
`[project.optional-dependencies]`.

4. Check the install:

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

## Verify your install

```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_rc6_projection.mjs
```

Expect 116 Python tests to run with no failures, and 11 Node tests passing. The 4 browser tests skip when the optional Playwright install is absent (112 passing, 4 skipped in that case); with Playwright installed, all 116 pass. The full suite takes about 20 seconds.

## Uninstall

1. Stop the server.
2. Delete the extracted directory.
3. Delete the state directory you passed with `--state-dir`, if you made
   one. That removes all projects, keys, and databases.
4. Delete the virtual environment (`.venv` inside the extracted
   directory goes with it in step 2).

No system files are changed. Nothing is installed outside the directory
you extracted and the state directory you chose.

## License

Apache License 2.0. See `LICENSE` in the release archive. OpenLine
branding and trademarks are governed separately and are not licensed
under Apache 2.0.
