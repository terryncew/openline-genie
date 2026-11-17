# OPENLINE CIVILIZATION APPLICATIONS 001 — REPRODUCIBLE LAUNCH & REPLAY INSTRUCTIONS

## 1. Unpack & Verify Cryptographic Hashes
```bash
sha256sum -c SHA256SUMS_CIVILIZATION_APPLICATIONS_001.txt
mkdir -p /tmp/openline_civ_apps_replay
unzip -q OPENLINE_009_CIVILIZATION_APPLICATIONS_001_SOURCE.zip -d /tmp/openline_civ_apps_replay
cd /tmp/openline_civ_apps_replay/src_009
```

## 2. Run All Five Civilization Applications, Central Experiment, Sixth Finding & 8 Falsifiers
```bash
python3 run_civilization_applications_001.py
```
This deterministically executes:
- **Application A (Franklin)**: Community Energy and Essential-Cost Cooperative (`genie-synth-community-energy-cooperative-and-essentialcost`) + `conventional_energy_coop_calculator` parity check + 6-scenario sensitivity matrix + 4 fraud-trap refusals.
- **Application B (Baldwin)**: Public-Benefits and Institutional Appeal Assistant (`genie-synth-privacyconscious-publicbenefits-and-institutiona`) + 3-bucket epistemic triage + statutory effective-date check + fail-closed deadline bound + PII redaction.
- **Application C (Morrison)**: Reusable Community Project Library across 3 distinct projects (Water, Food/Childcare, Building/Community-Space) + real `SIGKILL` worker recovery + cross-installation export/import + **Defect 10 (`D3-CA-010`)** post-import Decision Recall.
- **Application D (Einstein)**: Self-Correcting Scientific Research Workspace (`genie-synth-selfcorrecting-scientific-research-workspace-for`) + competing hypotheses (`B0, H1, H2, H3`) + immutable negative findings + `independent_research_replayer`.
- **Application E (Arendt)**: Public Infrastructure Decision Accountability (`genie-synth-public-infrastructure-decision-accountability-re`) + evidence-backed public challenges (`CHALLENGE-001`, `CHALLENGE-002`, `CHALLENGE-003`) + standalone `PUBLIC_INFRASTRUCTURE_ACCOUNTABILITY_DOSSIER.html`.
- **Central Experiment & Sixth Finding**: 20-project capability compounding curve (`N_BE = 4`) + `evidence-triaged-counterfactual-auditor-v1` (`ET-COSA`) on Unfamiliar Task 6 (`genie-synth-municipal-pharmacy-coldchain-and-insulin`).

## 3. Run the Full Automated Test & Security Suites
```bash
# Run the dedicated Civilization Applications 001 test suite (8 tests including live HTTP server E2E)
python3 -m unittest tests/test_civilization_applications_001.py -v

# Run the complete 167-test unit, regression, and browser E2E suite
python3 -m unittest discover -s tests -p "test_*.py"


# Run the 24 OpenLine 007/008 capability flywheel unit tests
python3 -m unittest discover -s capabilities_007_008/tests -v
```

## 4. Launch the Interactive Genie / Living World Server Locally
```bash
python3 genie_server.py --host 127.0.0.1 --port 8799 --no-model
```
Then open:
- Primary Living World UI: `http://127.0.0.1:8799/`
- Classic Genie Workbench: `http://127.0.0.1:8799/openline_genie.html`
- Ratchet & Receipt Diagnostic Workbench: `http://127.0.0.1:8799/ratchet`

## 5. Clean Rollback to Frozen Release Candidate (`4460757f...`)
```bash
patch -R -p1 < ../OPENLINE_009_CIVILIZATION_APPLICATIONS_001.patch
```
