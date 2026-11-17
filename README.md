# OpenLine Genie & Living Projects (`v1.2.0-rc3`)

**Local-First Seven-Application Suite, Custom App Builder & Receiver-Governed Runtime**

- **Canonical Public Repository**: [`https://github.com/terryncew/openline-genie`](https://github.com/terryncew/openline-genie)
- **Zero-Install Static Browser Preview (`v0.7.1`)**: [`https://terryncew.github.io/openline-genie/try/`](https://terryncew.github.io/openline-genie/try/)
- **Ecosystem Directory**: [`ECOSYSTEM.md`](https://github.com/terryncew/openline-genie/blob/main/ECOSYSTEM.md)
- **Frozen Five-Application Baseline**: Tag [`v1.0.0-rc1`](https://github.com/terryncew/openline-genie/tree/v1.0.0-rc1) (`7148fe4de9488d30280ccbc0c9dfdbd419592dab`)

## 1. Quick Start (Clean Virtual Environment Installation)

OpenLine Genie runs locally on `127.0.0.1` in **Free Local Mode (`$0.00` cost, no API keys, no cloud account required)**:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify all 7 applications & sample projects (exits 0):
python3 launch_genie.py --verify-only

# Start the local server on http://127.0.0.1:8795:
python3 launch_genie.py
```

## 2. Included Applications (`v1.2.0-rc3` Seven-Application Local Suite)

1. **Energy Commons (`/products`)**: Community solar, battery/PCM reserve, and tariff planning.
2. **Advocate + Case Packet (`/products`, `/api/advocate/case_packets`)**: Evidence organization, missing-document checks, and PII-redacted appeal packets.
3. **Capability Commons (`/products`)**: Reusable community project templates and portable bundles.
4. **Science (`/products`)**: Reproducible hypothesis testing, seed-offset checks, and model selection.
5. **Civic (`/products`)**: Public infrastructure comparison, resident challenges, and accountability dossiers.
6. **Neighborhood / ClearCovenant (`/neighborhood`)**: Role-separated homeowner, board, and community covenant governance.
7. **Robotics Studio (`/robotics`)**: Multi-body Lagrangian/contact physics simulator and hardware safety adapter for **Open Duck Mini v2 (14-DoF Biped)** and **LeRobot SO-101 (6-DoF Arm)** (`SIMULATED_VERIFIED_ONLY`; physical servo hardware remains `HOLD` until benchtop robot run).

## Semantic Authority Bridge

`core/semantic_authority_bridge.py` exchanges semantic models (NVIDIA
Auto-Ontology / Apache Ossie) as files only (YAML interchange, no live
integration with any external system). Certification badges shown by an
upstream model are kept separate from receiver-pinned Ed25519 certification
attestations, and consequential commits fail closed on stale or forged
certification.

## 3. Security, Authority & Honest Scope Boundaries

- **Loopback & CSRF Protection**: Binds strictly to `127.0.0.1` / `localhost` with `Host`, `Origin`, and `Content-Type: application/json` guards on all mutating `POST` routes.
- **Cryptographic Capsule Trust & No Arbitrary `exec()`**: `core/portable_verified_inheritance.py` requires trusted issuer verification and Ed25519 signature verification (`core.openline_guard.verify_envelope`) before import, and enforces an AST-checked static kernel allowlist (arbitrary Python `exec()` is disabled).
- **Mandatory Consequential-Effect Recall Enforcement**: `ReceiverGuard` STOP/epoch state, `RecallLedger` DNF standing, and supporting assumptions (`data_version`, `calibration_expiry_utc`, `reference_sensor_health`, `source_sha256`, `policy_pin_sha256`, `authority_epoch`) are checked automatically at every consequential effect boundary, even if a worker omits a manual recall check.
- **Browser & Viewport Scope**: Verified in headless Chromium at desktop (`1280x800`) and mobile width (`390x844`, `0px` horizontal overflow). Physical iOS Safari hardware is marked `UNTESTED_ON_PHYSICAL_IOS_DEVICE`.


## Release candidate notes (`v1.2.0-rc3`)

This is the `v1.2.0-rc3` public release candidate: the local-first,
single-operator suite described above. It is not production-safe
multi-user software; see the honest limitations below before relying on it
for anything consequential.

- HTTP listening is restricted to `127.0.0.1` or `localhost`. Host and Origin
  are validated for **GET and POST**; non-loopback bind requests are refused.
- Neighborhood uses one **server-configured local owner identity** per instance;
  request URL, POST body, and role tabs are never credentials. Default is the
  Unit 104 homeowner demo; board/community roles require a separately started
  owner-configured session. This is **not a multi-user authorization service**.
  All callers with local same-OS-user access can still access the local server.
- When the owner accepts a change to an application assumption, dependent
  standing becomes `REOPEN`. Consequential authorizations fail closed until
  the exact accepted snapshot has undergone an explicit **local assumption
  review**. That review does *not* establish independent physical/scientific truth
  or repair unrelated revoked upstream evidence.
- Portable import verifies the source receipt and state. Overwrite requires an
  expected destination version and SHA plus a newer incoming version; importing
  the same or older snapshot has an explicit refusal rather than a silent no-op.
- `/api/semantic/state` serves the existing local research receipt; if absent,
  the route returns `503` instead of launching expensive research on a GET.
- Legacy research runners use `OPENLINE_RESEARCH_WORKSPACE`,
  `OPENLINE_RESEARCH_DOWNLOADS`, and `OPENLINE_OUTPUT_DIR` rather than frozen
  private `/working_dir` paths. Their external research inputs are not bundled.

For detailed source-level tests, remaining browser-review and full-suite limits,
see `RELEASE_NOTES.md`.
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

## Chip-package research (computational only, hardware on HOLD)

**[Chip-package research: a proposed cooling and power-delivery design, independently challenged](https://github.com/terryncew/openline-genie/blob/main/research/chip-packaging/).** A one-person AI-assisted team generated and independently challenged a chip-package research hypothesis: consolidating power delivery, liquid cooling, signal wiring, and structural support into one metal package. The nearly twofold modeled advantage collapses to +0.332% parity when the assigned yield, cost, and power-delivery values are equalized with a matched conventional design. The proposed design cannot route high-bandwidth memory on a single 8 µm wiring layer (343 of 1,750 connections). The independent audit found the electrical test design would draw 614.4 W instead of the stated 50 W, the transistor packages do not fit the stated 45 mm face, and the STEP files are not manufacturable solids. No hardware has been built. The step-by-step manufacturing instructions are withheld; what is published is a read-only computational snapshot with a one-command reproduction. **The freshwater-production claim is not established.**

## For AI coding agents

The layout, entry points, interfaces, how to run the tests, the safety boundaries, and what is implemented versus what is only proposed are documented in the guides alongside the code; no separate agent guide ships in this release archive.

## License

Apache License 2.0. See `LICENSE`. OpenLine branding and trademarks are governed separately and are not licensed under Apache 2.0.