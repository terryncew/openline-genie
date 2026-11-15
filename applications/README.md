# OpenLine Genie

**Local-first software for planning community projects, organizing evidence, running reproducible research, and keeping important decisions under human control.**

OpenLine Genie runs on your own computer in your web browser. It lets individuals, neighborhood cooperatives, legal-aid advocates, researchers, and civic groups work through consequential decisions step by step—without losing track of assumptions, rejected options, or supporting evidence.

---

## Six Applications Included in OpenLine Genie

1. **Energy Commons — Plan affordable community energy**
   Compare rooftop solar, battery storage, thermal hot-water storage, and efficiency upgrades for a household, apartment building, or housing cooperative. Includes 10-year discounted cash-flow comparisons, maintenance and battery replacement costs, and sensitivity checks across interest rates, roof shading, and utility rate changes.
2. **Advocate — Organize evidence and prepare challenges to institutional decisions**
   Ingest a decision notice, track earliest conservative appeal deadlines, separate **verified facts** (backed by attached documents) from **unverified allegations** and **missing information**, check rule effective dates, and scrub personal identifiers (account numbers, phones, emails) before sharing.
3. **Capability Commons — Build and share reusable community projects**
   Start from three working templates—a **Clean Water Filtration Hub**, a **Cooperative Childcare & Community Kitchen**, and a **Building Weatherization & Shared Workshop**—or create your own project in plain words, apply verified capacity/budget planning tools, and export the entire project for another community group to continue.
4. **Science — Run reproducible research and preserve what was learned**
   Evaluate competing hypotheses against a standard baseline using complexity-penalized scoring (AIC and MDL), keep an permanent record of ruled-out hypotheses so failed ideas are not repeated, flag sensor calibration drift when datasets change, and verify independent zero-trust replay.
5. **Civic — Compare public projects and make decisions accountable**
   Evaluate competing public infrastructure proposals across best-case (P10), typical (P50), and storm-stress (P90) costs, attach checksum-verified resident challenges, and export a standalone HTML decision dossier that anyone can read in a standard browser without installing OpenLine.
6. **Neighborhood (ClearCovenant) — Understand HOA rules, resolve disputes, compare costs, and manage community records**
   Understand your HOA or condo rules, check whether a fine or assessment follows the rules, compare contractor bids, prepare responses to disputes, and keep a permanent, portable copy of your community records on your own computer. This is a local single-user tool for one household or association at a time: anyone who can reach the port on your computer is the operator, so never expose the port beyond your own computer. Multi-household separation is not a supported deployment.

---

## Quick Start (Free Local Mode — $0 Cost, No API Keys Required)

### Requirements
- **Operating Systems**: Linux is the verified OS. macOS and Windows are not tested.
- **Python**: Python 3.11 or newer (with standard `sqlite3` and `cryptography` package)
- **Node.js**: Node.js 18 or newer (used for project graph verification)

### 1. Verify Your Installation
```bash
python3 launch_genie.py --verify-only
```

### 2. Launch OpenLine Genie
On macOS / Linux:
```bash
./run_openline_genie.sh
```
Or on any platform with Python 3:
```bash
python3 launch_genie.py --port 8795
```
Then open **[http://127.0.0.1:8795/products](http://127.0.0.1:8795/products)** in your desktop or mobile browser.

### Robotics Studio (separate server, simulation only)

The Robotics Studio is a seventh, separate tool that lives at the repository root (`openline_robotics_001/`) and runs on its own loopback-only server on port 8796. It lets you design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls, for two robots: Open Duck Mini v2 (a small walking robot) and LeRobot SO-101 (a small robot arm).

```bash
# from the repository root
.venv/bin/pip install onnxruntime
./run_robotics_studio.sh
```

Then open `http://127.0.0.1:8796/robotics`, or follow the **Robotics Studio** entry on the launcher page (route `/robotics`). **Simulation only:** results are verified in simulation and never establish physical hardware safety; the hardware adapter is verified in dry-run only. Full details: `../openline_robotics_001/README.md`.

---

## What It Costs
- **$0.00 in default Free Local Mode**: OpenLine Genie runs 100% locally using deterministic calculators and templates. No cloud account, subscription, or paid AI API key is required.

## What Remains Under Your Control
- **Preview Before Saving (`Waiting for your review`)**: Every calculation or edit is staged as a draft first. Nothing changes your saved project record until you click **Accept changes** (or **Reject changes** to discard).
- **Pause All Changes (`STOP`)**: Clicking **Pause All Changes (STOP)** immediately freezes all edits and approvals until you explicitly click **Resume Editing**.
- **Automatic Review Flags (`Needs another review`)**: When an underlying assumption changes—such as a utility rate hike, a corrected case document, or sensor drift—OpenLine Genie flags dependent decisions as **Needs another review** while keeping your saved record intact.
- **Human Sign-Off for Commitments**: Preparing a cooperative procurement packet, locking an appeal packet, or recording a public infrastructure selection requires explicit human confirmation.

## Plain-Language Limitations (What OpenLine Genie Cannot Do)
- **Not Legal Representation**: OpenLine Advocate organizes evidence, dates, and rules for human review. It is **not legal advice**, does not create an attorney-client relationship, and never submits appeals to external agencies automatically.
- **Not a Licensed Engineering Stamp**: OpenLine Energy Commons and OpenLine Civic verify financial and physical conservation math, but site-specific roof structural capacity, electrical panel ratings, and environmental permits require licensed engineers and local inspectors.
- **Neighborhood Is a Local Single-User Tool**: Neighborhood (ClearCovenant) runs on your own computer for one household or association. It does not separate multiple households on one server, and it is not legal advice and creates no attorney-client relationship. It covers California, Florida, Texas, South Carolina, and a general U.S. baseline; other states need the statute text or local counsel.
- **Not a Substitute for Wet-Lab Hardware Testing**: OpenLine Science verifies computational reproducibility and model selection on recorded datasets, not physical material longevity in a hardware chamber.
- **Local Single-Computer Server**: By default, `genie_server.py` binds strictly to `127.0.0.1` (`localhost`) for your personal or local workstation use. Do not expose the local server directly to the public internet without an authenticated reverse proxy.
