# OPENLINE 009 GENIE — INSTALLATION, COLD-START & HOST LAUNCH MANUAL

- **Release Candidate**: `OPENLINE_009_GENIE_FINAL_RELEASE_CANDIDATE.zip`
- **Upstream Baseline**: `OPENLINE_009_RATCHET_VERIFIED_SOURCE_PACKAGE.zip` (`SHA-256: 6b2028b84b9581b6f339b8bd38b7d269e1fad122f9241f857f4d5e6598bc206c`)
- **Cumulative Patch**: `OPENLINE_009_FINAL_CLOSURE_001_CUMULATIVE.patch` (Defects 1–9 + `BUCSW` Standing Witness)

---

## 1. SYSTEM REQUIREMENTS

- **OS**: macOS, Linux, or Windows (WSL2)
- **Python**: Python `3.10+` (verified on Python `3.11`)
- **Dependencies**: Standard library only (`sqlite3`, `http.server`, `hashlib`, `json`, `unittest`, `contextlib`) plus `cryptography` (for Ed25519 receipt signing). Optional: `selenium` + `chromium`/`chromedriver` for running headless browser UI verification tests.

---

## 2. QUICK COLD-START INSTALLATION (30 SECONDS)

```bash
# 1. Unpack the verified release candidate into a clean directory
mkdir -p ~/openline_009_genie_rc
unzip -q OPENLINE_009_GENIE_FINAL_RELEASE_CANDIDATE.zip -d ~/openline_009_genie_rc
cd ~/openline_009_genie_rc/src_009

# 2. Launch Genie in local deterministic mode (no API key or internet required)
python3 genie_server.py --host 127.0.0.1 --port 8799 --no-model
```

Open **`http://127.0.0.1:8799/`** in desktop Safari/Chrome or mobile Safari (`390x844` viewport verified with `0px` horizontal overflow).
- Main Genie Workspace: `http://127.0.0.1:8799/openline_genie.html`
- Ratchet & Receipt Inspector: `http://127.0.0.1:8799/ratchet`

---

## 3. MODEL MODES (LIVE MODEL vs. `--no-model` vs. UNAVAILABLE MODEL)

1. **Local Deterministic Mode (`--no-model`)**:
   ```bash
   python3 genie_server.py --port 8799 --no-model
   ```
   Uses deterministic domain classification (`solar_estimator`, `garden_planner`, `kid_game`, `general_business`) and deterministic physics/financial calculators (`solar`, `water`, `garden`, `hub_coupled`). Discloses `DETERMINISTIC_TEMPLATE_AND_PHYSICS_CALC_ONLY_NO_LLM` in the UI and API.
2. **Live Model Mode (`OPENAI_API_KEY`)**:
   ```bash
   export OPENAI_API_KEY="sk-..."
   python3 genie_server.py --port 8799
   ```
   Uses live model synthesis for open-ended proposals while keeping all receiver authority gates (`stage -> accept/reject`, `STOP`, `RecallLedger`, and Ed25519 receipts) strictly enforced by SQLite.
3. **Unavailable Model Fallback**:
   If launched without `--no-model` and `OPENAI_API_KEY` is unset or unreachable, Genie returns `MODEL_UNAVAILABLE` without fabricating AI output or mutating accepted project state.

---

## 4. RUNNING THE VERIFICATION SUITES

```bash
cd ~/openline_009_genie_rc/src_009

# 1. Run the Final Closure 001 verification harness (Genie E2E + Solar Falsification + BUCSW)
python3 run_final_closure_001.py

# 2. Run the full 159-test unit & integration suite
python3 -m unittest discover -s tests -p "test_*.py"

# 3. Run the 24 independent browser & security checks
python3 muse_independent_checks.py
```

---

## 5. PERSISTENT HOST-LOCAL DAEMON LAUNCH (OUTSIDE EPHEMERAL SANDBOX)

Because the evaluation container is ephemeral, persistent daemon survival across host reboots is marked **`HOLD (HOST-LAUNCH PACKAGE VERIFIED)`** until started on your persistent host machine:

```bash
# Launch persistently in background on macOS / Linux host
nohup python3 genie_server.py --host 127.0.0.1 --port 8799 --no-model \
  --state-dir ~/.openline_009_state > ~/.openline_009_state/genie_server.log 2>&1 &
```

---

## 6. CLEAN ROLLBACK TO FROZEN BASELINE (`6b2028b8...`)

To revert all cumulative Closure 001 additions and return bit-for-bit to the frozen 009 Internal Acceptance source (`OPENLINE_009_RATCHET_VERIFIED_SOURCE_PACKAGE.zip`):

```bash
cd ~/openline_009_genie_rc/src_009
patch -R -p1 < ../OPENLINE_009_FINAL_CLOSURE_001_CUMULATIVE.patch
sha256sum -c SHA256SUMS.txt
```
