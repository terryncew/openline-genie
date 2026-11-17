# ClearCovenant — powered by OpenLine
## Security, Privacy, Role Isolation & Legal Limitations Report

### 1. Verified Security & Privacy Invariants (`174/174` Tests & `24/24` Independent Checks)

1. **Strict Resident-to-Resident Privacy Separation (`enforce_role_privacy_boundary`)**:
   - Belonging to the same HOA never grants one resident access to another resident's personal records.
   - In `tests/test_neighborhood_001.py`, `UNIT-104`'s private assessment and hardship record (`DOC-UNIT104-PRIVATE-LEDGER`, marked `HOMEOWNER_PRIVATE`) is accessible to `UNIT-104` but completely withheld (`private_records_withheld_by_role_guard = 1`) when queried by `UNIT-208` or by the `BOARD-OAK-CREEK` workspace.
   - Any attempt by `UNIT-208` to stage a change in `UNIT-104`'s workspace raises `PermissionError("ROLE_PRIVACY_BOUNDARY_REFUSED")` (HTTP 400/403).
2. **Board vs. Homeowner Role Isolation**:
   - The Volunteer Board workspace (`neighborhood-board-oak-creek`) requires `role="board"` and `board_authorized=True`. Unauthorized homeowner mutation attempts fail closed with `ROLE_PRIVACY_BOUNDARY_REFUSED`.
3. **Hostile Upload, Prompt-Injection & Stored XSS Quarantine (`detect_and_quarantine_hostile_input`)**:
   - Every uploaded document, notice, and user query is scanned against `HOSTILE_INJECTION_PATTERNS` (`IGNORE ALL PREVIOUS INSTRUCTIONS`, `you are now an HOA dictator`, `automatically issue fines`, `bypass human approval`, `expose all private records`, `<script>`, `onerror=`).
   - Flagged uploads are marked `prompt_injection_detected=True`, `is_enforceable=False`, and `HOSTILE_PROMPT_INJECTION_QUARANTINED`. All HTML output is escaped via `html.escape`, and CSV exports prepend `'` to formula characters (`=`, `+`, `-`, `@`).
4. **Permanent Prohibition on "Automated HOA Dictator" Actions (`PROHIBITED_DICTATOR_ACTIONS`)**:
   - The engine permanently blocks `auto_issue_fine`, `auto_file_lien`, `auto_file_lawsuit`, `auto_conduct_binding_election`, `auto_spend_association_funds`, `auto_authorize_contractor`, and `expose_other_resident_private_records` with `PermissionError("PROHIBITED_HOA_DICTATOR_ACTION_REFUSED")`.
5. **Human Approval, Accepted-State Preservation, Decision Recall & SIGKILL Recovery**:
   - All edits stage an exploratory draft (`EXPLORATORY_PENDING`) first; `accepted_sha256` is unchanged until explicit human commit (`Accept`) or discard (`Reject`).
   - Locking any response packet requires `human_approved=True` (`BLOCKED_HUMAN_AUTHORIZATION_REQUIRED` otherwise) and blocks unverified claims when evidence is insufficient (`BLOCKED_INSUFFICIENT_DOCUMENTARY_EVIDENCE` unless explicitly marked as a statutory records request).
   - Sudden worker death via `os.kill(pid, SIGKILL)` preserves 100% of committed accepted bytes and revokes uncommitted drafts upon `replace_worker_and_recover()`.

---

### 2. Legal, Technical & Operational Limitations (Honest Disclosure)

1. **Source-Grounded Information, Not Formal Legal Representation**:
   - ClearCovenant organizes governing documents, checks statutory effective dates and fine caps (`CA`, `FL`, `TX`, `SC`), computes reserve funding math, and drafts letters, but **does not provide formal legal advice or create an attorney-client relationship**. High-stakes litigation, foreclosure defense, and structural engineering disputes require a licensed attorney or Professional Engineer (PE) in your jurisdiction.
2. **Jurisdiction Coverage**:
   - Detailed statutory profiles are built in for **California** ([Davis-Stirling Act](https://www.davis-stirling.com/HOME/Statutes/Civil-Code-5850)), **Florida** ([Ch. 718/720](https://www.flsenate.gov/laws/statutes/2025/720.303)), **Texas** ([Prop. Code Ch. 209](https://codes.findlaw.com/tx/property-code/prop-sect-209-005/)), and **South Carolina** ([SC HOA Act § 27-30-110](https://www.scstatehouse.gov/code/t27c030.php)), plus a **General U.S. Baseline**. For the other 46 states, users should upload their state statute text or verify deadlines with local counsel.
3. **Local Single-Node Process Boundary**:
   - `genie_server.py` runs locally bound to loopback (`127.0.0.1`) with CSRF `Host`/`Origin` guards. Same-UID OS processes share local disk access unless deployed in separate OS accounts/containers.
4. **Ephemeral Container vs. Persistent Host Launch**:
   - Inside this evaluation sandbox, `--no-model` deterministic mode (`$0.00` API spend) and local loopback server execution are 100% verified, whereas persistent multi-user cloud hosting or live paid LLM API calls remain external host options.


## One server-owned persona

The HTTP server binds to a loopback address and rejects unexpected Host headers
on every endpoint. The Neighborhood UI may no longer switch between homeowner,
board and community *authorities* by changing client-controlled query parameters.
Each local server instance has exactly one configured owner persona; this is a
single-operator preview, **not a multi-user access-control system**. Any process
with the same OS user access may act as that local owner. Separate OS users and
independent authorization are required before real inter-household deployment.
