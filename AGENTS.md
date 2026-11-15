# AGENTS.md — OpenLine Genie repository

This file is for AI coding agents working in this repository. It tells you what is here, where the entry points are, how to run things, what the safety boundaries are, and what is implemented versus what is only proposed. Read it before changing anything.

## What this repository is

OpenLine Genie is local-first software. It runs on the user's own computer, in their web browser, with no account, no cloud, and no paid AI key required in default mode. The user proposes work; a receiver gate decides whether each exact action is allowed; accepted work is recorded with a signed receipt. The user decides what stays.

## Layout

- **Repo root** — OpenLine Genie v0.7.1 (the original product). `genie_server.py`, `genie_engine.py`, `core/`, `tests/`, `try/`. The v0.7.1 release (tag `v0.7.1`) is immutable; do not rewrite its history or move its tag. The product site (Try/Get/How/See) lives on the `gh-pages` branch; do not touch that branch for code changes.
- **`applications/`** — Six community applications, releases v1.0.0-rc1, v1.1.0-rc1, and v1.2.0-rc1 (prereleases). This is where most application work happens. It is a self-contained tree: its own `genie_server.py` launcher, `genie_engine.py`, `core/`, `openline_009_living_project.py`, `tests/`, `examples/`, `INSTALL.md`, `README.md`, `RELEASE_NOTES.md`, `LICENSE`, and `SHA256SUMS.txt` (285 entries; verify with `sha256sum -c SHA256SUMS.txt` from inside `applications/`).
- **`openline_robotics_001/`** — Robotics Studio (v1.1.0-rc1), a seventh application. Self-contained package with its own loopback-only server (`robotics_studio_server.py`, port 8796), engine, physics simulator, and tests. Launched with root `run_robotics_studio.sh`. Simulation only; physical hardware is unverified.
- **`applications/openline_five_products.html`** — the six-tab launcher page served at `/products`. Tabs: `energy`, `advocate`, `commons`, `science`, `civic`, `neighborhood`. It also links to the Robotics Studio (route `/robotics`, which only links to the studio server; it does not proxy API calls or share Genie state).
- **`applications/openline_neighborhood.html`** — the Neighborhood (ClearCovenant) page, served at `/neighborhood` and `/clearcovenant`.

## The seven applications

| Application | Plain description | Tab / route | Example |
|---|---|---|---|
| Energy Commons | Compare community energy options and costs. | `energy` | `applications/examples/sample_1_energy_commons.json` |
| Advocate | Understand decisions, organize evidence, and prepare challenges. Case Packets preserve institutional decisions, organize evidence, and transfer verifiable case records between people or AI assistants. | `advocate` | `applications/examples/sample_2_advocate.json` |
| Capability Commons | Build and share reusable community projects. | `commons` | `applications/examples/sample_3_capability_commons.json` |
| Science | Explore hypotheses and preserve reproducible research. | `science` | `applications/examples/sample_4_science.json` |
| Civic | Compare public projects and examine the evidence behind decisions. | `civic` | `applications/examples/sample_5_civic.json` |
| Neighborhood (ClearCovenant) | Understand HOA rules, resolve disputes, compare costs, and manage community records. | `neighborhood` / `/neighborhood` | `applications/SAMPLE_HOA_CONFLICT_SCENARIOS_12_CASES.md` |
| Robotics Studio | Design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls. Simulation only. | `/robotics` (links to `http://127.0.0.1:8796/robotics`) | `openline_robotics_001/examples/` |

## Entry points

- **Launch the applications server** (from inside `applications/`):
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/python genie_server.py --host 127.0.0.1 --port 8795 --state-dir ./genie-state
  ```
  Then open `http://127.0.0.1:8795/products`. Flags: `--host 127.0.0.1` (loopback only; any other host is refused), `--port 8795`, `--state-dir ./genie-state` (where keys and the SQLite database live; without it, state does not persist across restarts), `--no-model` (forces deterministic mode), `--enable-paid-model` (OFF by default; only with an explicit opt-in and the local $5.00 spend cap).
- **Verify the install:** `python3 launch_genie.py --verify-only` (inside `applications/`).
- **Key HTTP routes:** `GET /products` (six-tab launcher), `GET /neighborhood`, `GET /robotics` (launcher link to the studio), `GET /semantic` (Semantic Authority Bridge workbench), `GET /api/semantic/state` (read-only precomputed bridge receipts; `?probe=recompile` runs the local read-only Boundary B simulation), `GET /api/status`, `GET /api/neighborhood/state`, `GET /api/neighborhood/dossier?workspace={homeowner|board}&format=json`, `POST /api/neighborhood/stage`, `POST /api/neighborhood/action`, `GET /api/advocate/case_packets`, `GET /api/advocate/case_packet/export`, `POST /api/advocate/case_packet/stage`, `POST /api/advocate/case_packet/import`, `POST /api/build`. The Robotics Studio runs its own server on port 8796: `GET /robotics`, `POST /api/robotics/simulate`, `POST /api/robotics/export` (see `openline_robotics_001/README.md`).

## How to run the tests

From inside `applications/`, with the system Python (the full suite needs `selenium`, which is not in `requirements.txt`; the venv install covers only the runtime deps):

```bash
python3 -m unittest discover -s tests -p "test_*.py"
node --test tests/test_rc6_projection.mjs
```

Measured 2026-11-15 (Python 3.12.3, Linux, no Chrome/Chromium installed) on the v1.2.0-rc1 tree: 193 Python tests ran, 176 passed, 1 failure, 11 errors, 5 skipped; Node 11 passed, 0 failed; Robotics 6 passed, 0 failed (`python3 -m unittest openline_robotics_001.tests.test_robotics_breakthrough_001` from the repo root, needs `onnxruntime`). All 7 new Semantic Authority Bridge tests passed. The 1 failure is the Neighborhood browser journey test, which needs a Chromium binary. Of the 11 errors: 2 check external archive files not included in this package, 3 are browser tests that cannot run without Chrome, and 6 are live-server tests that error on `TimeoutError` because the first engine build takes ~42.5s on this 1.5-CPU box while the tests use a 20s client timeout — the same 6 errors were reproduced on the pristine v1.1.0-rc1 tree. Those are NOT VERIFIED here, never passed. The 5 skips are browser tests that skip when Chromium is absent (including the Case Packet workbench browser test). Set `NO_PROXY=localhost,127.0.0.1,127.0.0.2,::1` when running the suite (one test module binds `127.0.0.2`, and the sandbox egress proxy otherwise intercepts it). The applications suite takes about 16 minutes on this box (the 7 bridge tests alone take ~3.5 minutes); the robotics suite about 60 seconds.

## Safety boundaries (do not weaken these)

- **Loopback only.** `genie_server.py` binds `127.0.0.1` and refuses any other `--host`. The Host/Origin check applies to `GET /api/*` as well as `POST`. Never add a flag or code path that binds `0.0.0.0` or disables the Host check.
- **Single user / single operator.** Anyone who can reach the port on the machine is the operator, with full access to every workspace. There is no login, session, or password anywhere in this codebase, and none should be invented as a casual fix. Neighborhood is a local single-user tool: it does not separate multiple households on one server, and multi-household separation is NOT a supported deployment. The Neighborhood HTTP layer intentionally ignores client-supplied role/unit/board identity parameters; the local operator is the only actor.
- **Human control is the product.** Every consequential step goes through the local receiver: proposing, accepting, rejecting, STOP, worker replacement, export, import. There is no way to accept a change without the receiver, and the browser UI alone cannot write accepted state. Do not add an auto-accept, auto-submit, auto-fine, or auto-send path.
- **No paid model without opt-in.** Paid model dispatch is OFF by default. Never enable it silently, never add a payment method, never exceed the local spend cap.
- **No network in default mode.** The deterministic local synthesizer needs no network. Do not add telemetry, analytics, or outbound calls.
- **Secrets.** There are no API keys, tokens, passwords, or private keys in this repository. Test fixtures use fictional `555` numbers and `.example` addresses only. Never commit a real credential, a private Drive ID, or a real personal record.

## Implemented versus proposed

**Implemented:** all seven applications with working primary workflows; Advocate Case Packets (export/import, Decision Recall, tamper rejection, offline-readable dossiers); the Semantic Authority Bridge (local-only Ossie YAML / Auto-Ontology interchange, semantic-change detection that reopens only affected decisions, selective Decision Recall, stale-authority refusal, verifiable case histories; see `applications/SEMANTIC_AUTHORITY_BRIDGE.md` — file-level Ossie compatibility only, no live NVIDIA integration, self-attested ephemeral keys); Robotics Studio simulation for two robots with capability transfer, STOP, authorization refusal, and corrupted-import rejection; human approval, rejection, STOP, Decision Recall, and accepted-state preservation; signed receipts for accepted/refused actions; export/import round-trips (portable JSON bundle + standalone HTML); the loopback-only servers with Host/Origin checks; the deterministic local synthesizer ($0 default).

**Proposed or not implemented:** paid-model dispatch (opt-in only, $5 cap, not tested here); multi-household separation in Neighborhood (explicitly NOT supported); a hosted consumer service (this is a local Python application, not a hosted service); browser end-to-end tests (need Chrome/Chromium, not verified here); macOS/Windows installs and iPhone Safari (not tested).

## Changing things

- Keep `applications/SHA256SUMS.txt` in sync: after any change inside `applications/`, regenerate it from the exact tree (`find . -type f ! -path "./SHA256SUMS.txt" | sort | xargs sha256sum > SHA256SUMS.txt`) and verify with `sha256sum -c SHA256SUMS.txt`. Note the exclusion is top-level only; the nested `upstream_repos/openline-idea-layer/SHA256SUMS.txt` must stay listed.
- Do not edit frozen evidence records (e.g. `applications/NEIGHBORHOOD_001_ACCEPTANCE_RECEIPTS.json`) to make their claims match current code. If a frozen record's claim is superseded, say so in the release record and the limitations docs, and leave the record itself intact.
- Do not remove the plain-language limitations from user-facing docs. Do not reintroduce internal engineering language (project codenames, internal experiment IDs, research codes) into user-facing screens, examples, or error messages; technical detail belongs in developer docs, test evidence, and audit records.
- The product name is **Neighborhood** (consumer-facing name **ClearCovenant**). The name "Be Neighborly" is not used: it collides with an active commercial platform (beneighborly.com) and a registered trademark. Do not reintroduce it into any user-facing surface.
- The `VERIFIED_0_LEAKS` claim in the frozen `NEIGHBORHOOD_001_ACCEPTANCE_RECEIPTS.json` is superseded: it described the pre-repair multi-household isolation claim, which was false at the HTTP layer and was replaced by the single-operator model. Do not repeat that claim for the current code.

## License

Apache License 2.0 (`LICENSE` at the repo root and in `applications/`).
