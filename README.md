# OpenLine Genie

**Local-first software that helps people plan community projects, organize evidence, run reproducible research, and keep consequential decisions under human control.**

OpenLine Genie runs on your own computer, in your web browser. Nothing is uploaded anywhere. You see the work take shape, change things, and explore different directions. The AI does the exploring. You decide what stays.

This repository holds two things:

1. **OpenLine Genie v0.7.1** — the original product: build an idea in your browser, discover what breaks, explore what works, keep what you approve, with a receiver gate and a signed receipt, so swapping the model mid-task does not lose the work. Free and open source.
2. **Seven applications (v1.1.0-rc1)** — six in the `applications/` directory (Energy Commons, Advocate, Capability Commons, Science, Civic, and Neighborhood) plus Robotics Studio at the repository root. Each one is a working local tool for a real job. See below.

## Try Genie v0.7.1

- **Try it in your browser:** https://terryncew.github.io/openline-genie/try/
- **Get the source:** https://github.com/terryncew/openline-genie/releases/tag/v0.7.1
- **How it works:** https://terryncew.github.io/openline-genie/how/
- **See a real session:** https://terryncew.github.io/openline-genie/see/

## Seven applications (v1.1.0-rc1)

All seven run on your own computer. No account, no cloud, no subscription, no paid AI key required. The six in `applications/` run from one local server; open `http://127.0.0.1:8795/products` after launching, and pick a tab. Robotics Studio runs as its own loopback-only server on port 8796 (see below).

| Application | What it does | Entry point | Example |
|---|---|---|---|
| **Energy Commons** | Compare community energy options and costs. | `applications/` tab `energy` | `applications/examples/sample_1_energy_commons.json` |
| **Advocate** | Understand decisions, organize evidence, and prepare challenges. Case Packets preserve institutional decisions, organize evidence, and transfer verifiable case records between people or AI assistants. | `applications/` tab `advocate` | `applications/examples/sample_2_advocate.json` |
| **Capability Commons** | Build and share reusable community projects. | `applications/` tab `commons` | `applications/examples/sample_3_capability_commons.json` |
| **Science** | Explore hypotheses and preserve reproducible research. | `applications/` tab `science` | `applications/examples/sample_4_science.json` |
| **Civic** | Compare public projects and examine the evidence behind decisions. | `applications/` tab `civic` | `applications/examples/sample_5_civic.json` |
| **Neighborhood (ClearCovenant)** | Understand HOA rules, resolve disputes, compare costs, and manage community records. | `applications/` tab `neighborhood`, or `http://127.0.0.1:8795/neighborhood` | `applications/SAMPLE_HOA_CONFLICT_SCENARIOS_12_CASES.md` |
| **Robotics Studio** | Design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls. Simulation only. | `./run_robotics_studio.sh`, then `http://127.0.0.1:8796/robotics` | `openline_robotics_001/examples/` |

Full details, installation, and per-application limitations: `applications/README.md` and `applications/INSTALL.md`. Release notes: `applications/RELEASE_NOTES.md`. Checksums: `applications/SHA256SUMS.txt` (verify with `sha256sum -c applications/SHA256SUMS.txt`).

## Install the applications

Requires Python 3.11 or newer and Linux (macOS and Windows are not tested). From the release archive, or from a clone of this repository working inside `applications/`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python genie_server.py --host 127.0.0.1 --port 8795 --state-dir ./genie-state
```

Then open `http://127.0.0.1:8795/products`. Full instructions: `applications/INSTALL.md`.

To check the install: `python3 launch_genie.py --verify-only` (inside `applications/`). To run the tests: `python3 -m unittest discover -s tests -p "test_*.py"` and `node --test tests/test_rc6_projection.mjs` (inside `applications/`), plus `python3 -m unittest openline_robotics_001.tests.test_robotics_breakthrough_001` (from the repository root, with `onnxruntime` installed). Measured 2026-11-15 on the v1.1.0-rc1 tree: 186 Python tests ran, 175 passed, 1 failure, 5 errors, 5 skipped; Node 11 passed, 0 failed; Robotics 6 passed, 0 failed. The 1 failure and 5 errors are browser tests that need Chrome (not installed in the test environment) and two tests that check external archive files not included in this package. They are recorded as NOT VERIFIED here, not passed.

## Robotics Studio (simulation only)

Design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls. It runs as its own loopback-only server on port 8796, next to the six applications above — not inside them.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt onnxruntime
./run_robotics_studio.sh
```

Then open `http://127.0.0.1:8796/robotics`. It is also linked from the applications launcher (`http://127.0.0.1:8795/products`, route `/robotics`). Two robots are supported: Open Duck Mini v2 (a small walking robot) and LeRobot SO-101 (a small robot arm). Full details: `openline_robotics_001/README.md`.

**Simulation only.** Every result is verified in simulation and never establishes physical hardware safety. The hardware adapter is verified in dry-run only; nothing here drives a physical robot.

## How decisions stay under your control

- **Preview before saving:** every calculation or edit is staged as a draft first. Nothing changes your saved record until you accept it. Rejecting leaves the accepted work untouched.
- **STOP:** pausing all changes freezes edits and approvals until you explicitly resume. Accepted work is never lost by STOP.
- **Decision Recall:** accepted work can be recalled and verified later, with a signed receipt for what was accepted or refused.
- **Export and import:** export gives a standalone file and a portable bundle with the accepted checksum and the receiver receipt. Import it on a fresh install to recover the project.

## Honest limitations

- **Local only.** The server binds `127.0.0.1` (loopback) and refuses other hosts. It is not reachable from another machine. Do not expose the port beyond your own computer. Anyone who can reach the port on your computer is the operator, with full access to every workspace.
- **Same-user boundary.** Signing keys and the database live in the state directory. Any process running as the same OS user can read them. Separate OS users, containers, or hardware keys are needed for a stronger boundary.
- **Neighborhood is a local single-user tool.** It runs for one household or association. It does not separate multiple households on one server, and multi-household separation is not a supported deployment.
- **Not legal advice.** Advocate and Neighborhood organize evidence, dates, and rules for human review. They are not legal advice, do not create an attorney-client relationship, and never submit anything to an outside agency automatically. Neighborhood covers California, Florida, Texas, South Carolina, and a general U.S. baseline; other states need the statute text or local counsel.
- **No guaranteed savings or outcomes.** Energy Commons compares costs; it does not promise savings. Science verifies computational reproducibility on recorded datasets; it does not validate a finding in the physical world. Civic compares proposals; it does not decide which one a community should choose.
- **Not tested:** macOS and Windows installs, iPhone Safari, uncoached human testing, paid-model calls. Browser tests need Chrome or Chromium.

## For AI coding agents

See `AGENTS.md` in this repository. It documents the layout, entry points, interfaces, how to run the tests, the safety boundaries, and what is implemented versus what is only proposed.

## License

Apache License 2.0. See `LICENSE`. OpenLine branding and trademarks are governed separately and are not licensed under Apache 2.0.
