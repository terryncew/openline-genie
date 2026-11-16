# OpenLine Genie & Living Projects (`v1.2.0-rc2`)

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

## 2. Included Applications (`v1.2.0-rc2` Seven-Application Local Suite)

1. **Energy Commons (`/products`)**: Community solar, battery/PCM reserve, and tariff planning.
2. **Advocate + Case Packet (`/products`, `/api/advocate/case_packets`)**: Evidence organization, missing-document checks, and PII-redacted appeal packets.
3. **Capability Commons (`/products`)**: Reusable community project templates and portable bundles.
4. **Science (`/products`)**: Reproducible hypothesis testing, seed-offset checks, and model selection.
5. **Civic (`/products`)**: Public infrastructure comparison, resident challenges, and accountability dossiers.
6. **Neighborhood / ClearCovenant (`/neighborhood`)**: Role-separated homeowner, board, and community covenant governance.
7. **Robotics Studio (`/robotics`)**: Multi-body Lagrangian/contact physics simulator and hardware safety adapter for **Open Duck Mini v2 (14-DoF Biped)** and **LeRobot SO-101 (6-DoF Arm)** (`SIMULATED_VERIFIED_ONLY`; physical servo hardware remains `HOLD` until benchtop robot run).

## 3. Security, Authority & Honest Scope Boundaries

- **Loopback & CSRF Protection**: Binds strictly to `127.0.0.1` / `localhost` with `Host`, `Origin`, and `Content-Type: application/json` guards on all mutating `POST` routes.
- **Cryptographic Capsule Trust & No Arbitrary `exec()`**: `core/portable_verified_inheritance.py` requires trusted issuer verification and Ed25519 signature verification (`core.openline_guard.verify_envelope`) before import, and enforces an AST-checked static kernel allowlist (arbitrary Python `exec()` is disabled).
- **Mandatory Consequential-Effect Recall Enforcement**: `ReceiverGuard` STOP/epoch state, `RecallLedger` DNF standing, and supporting assumptions (`data_version`, `calibration_expiry_utc`, `reference_sensor_health`, `source_sha256`, `policy_pin_sha256`, `authority_epoch`) are checked automatically at every consequential effect boundary, even if a worker omits a manual recall check.
- **Browser & Viewport Scope**: Verified in headless Chromium at desktop (`1280x800`) and mobile width (`390x844`, `0px` horizontal overflow). Physical iOS Safari hardware is marked `UNTESTED_ON_PHYSICAL_IOS_DEVICE`.


## Private RC2 release-repair candidate — independent reviewer notes

The source in this archive is a **private post-Argon repair candidate**, not the
published GitHub main branch. Public release remains **HOLD** until a separate
browser/installation reviewer accepts the exact new ZIP hash and the owner approves.

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
see `GPT6_RELEASE_ACCEPTANCE.md`. Do not market this private candidate as
production-safe multi-user software.
