# ClearCovenant — powered by OpenLine
## Security, Privacy, Role Isolation & Legal Limitations Report

### 1. Verified Security & Privacy Invariants

1. **Engine-Level Resident-to-Resident Privacy Filtering (`enforce_role_privacy_boundary`)**:
   - When the engine is called in-process with a stated role, belonging to the same HOA never grants one resident access to another resident's personal records.
   - In `tests/test_neighborhood_001.py`, `UNIT-104`'s private assessment and hardship record (`DOC-UNIT104-PRIVATE-LEDGER`, marked `HOMEOWNER_PRIVATE`) is accessible to `UNIT-104` but completely withheld (`private_records_withheld_by_role_guard = 1`) when queried by `UNIT-208` or by the `BOARD-OAK-CREEK` workspace.
   - Any attempt by `UNIT-208` to stage a change in `UNIT-104`'s workspace raises `PermissionError("ROLE_PRIVACY_BOUNDARY_REFUSED")` (HTTP 400/403).
   - The same filter applies inside uncommitted exploratory proposals: a staged draft's candidate documents are filtered by the requester's stated role before being returned. Answer text built from a withheld private record is also withheld: its cited provisions are stripped, its quoted answer and draft are replaced with a withheld notice, and the proposal summary (which quotes the verdict) is replaced the same way.
   - **Limit of this boundary (read carefully):** it filters by the role the caller *states*. Over HTTP the server takes no identity from the client at all (see item 1b): every caller that reaches the loopback port is the local operator, with full access to every workspace. This filtering is therefore a record-keeping aid for the single operator, not a login system and not proof against another person who can reach the port.
2. **Local Single-Operator Model — No Login, No Multi-Household Separation (1b)**:
   - `genie_server.py` takes no role, unit, or board-authorization value from any HTTP request. `GET /api/neighborhood/state` ignores those query values; `POST /api/neighborhood/stage` and `/api/neighborhood/action` discard them and act as the local operator for the requested workspace.
   - There is no password, session, token, or login flow, by design. Anyone who can reach the port on this computer IS the operator.
   - Protection therefore rests on: the server binding only to loopback (`127.0.0.1`, verified by `ss`), `Host`/`Origin` checks on `POST` endpoints and on `GET /api/*` read/export endpoints, and the operator never exposing the port beyond this computer.
   - **Multi-household separation is NOT a supported deployment.** Do not run one ClearCovenant server for several households, and do not share the port or the state directory with another household. A portable export bundle (JSON) contains the full unredacted records of its workspace: only share it with people who should see those records. The standalone HTML dossier lists document titles and digests, not private content.
3. **Board vs. Homeowner Role Isolation (in-process)**:
   - The Volunteer Board workspace (`neighborhood-board-oak-creek`) requires `role="board"` and `board_authorized=True` when called in-process. Unauthorized homeowner mutation attempts fail closed with `ROLE_PRIVACY_BOUNDARY_REFUSED`. Over HTTP, board actions are operator actions (see 1b): there is no second party to authorize, and no board action is taken without the operator's own explicit step in the interface plus, for response packets, the human-approval checkbox.
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
   - `genie_server.py` binds only to loopback (`127.0.0.1`, honored from `--host`; any non-loopback host is refused at startup) with `Host`/`Origin` guards on mutating `POST` endpoints and on `GET /api/*` read/export endpoints. Same-UID OS processes share local disk access unless deployed in separate OS accounts/containers. There is no login: anyone who can reach the port on this computer is the operator (see §1 item 1b).
4. **Ephemeral Container vs. Persistent Host Launch**:
   - Inside this evaluation sandbox, `--no-model` deterministic mode (`$0.00` API spend) and local loopback server execution are 100% verified, whereas persistent multi-user cloud hosting or live paid LLM API calls remain external host options.
5. **Semantic Authority Bridge (v1.2.0-rc1) — local files only, self-attested keys**:
   - The bridge reads and writes Apache Ossie YAML (and native Auto-Ontology YAML/JSON) files on this computer. There is no live NVIDIA service, no NIM endpoint, no network call, and no MCP transport; the 9 read-only MCP tools are local in-memory methods. Compatibility is claimed at the file level only — not a live NVIDIA integration, not NVIDIA endorsement, and not a promise that NVIDIA's converter will accept the bridge's files (that needs a live import test, which has not been run).
   - Each bridge instance generates fresh ephemeral Ed25519 steward and receiver keys. Certification attestations are self-attestations by that instance, not signatures from an independent external receiver or a long-lived steward. A signature proves the record was not altered after signing; it does not prove the underlying claim is true, legally valid, or externally authorized. Receipts are not stable across runs.
   - Stale-authority refusal surfaces as the Python exception `StaleSemanticAuthorityRefused` from `attempt_consequential_action`. There is no bridge POST endpoint and no HTTP status for it.
   - `GET /api/semantic/state` is read-only and covered by the same Host/Origin check as every other `GET /api/*` route; it serves the precomputed receipts file and never runs the suite or writes files. `?probe=recompile` runs a local, read-only simulation and writes nothing.
