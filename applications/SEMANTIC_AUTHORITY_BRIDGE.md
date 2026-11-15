# Semantic Authority Bridge — Developer Documentation

**Status:** shipped in v1.2.0-rc1 (prerelease). Local-only, deterministic,
no network, no paid service.

## What it is, in plain language

Decisions in OpenLine (an energy choice, a civic recommendation, an
advocate's claim) rest on *definitions*: what a term means, how it is
calculated, which tables join to which, whether the definition is still
certified, and which evidence documents support it. When a definition
changes, some decisions stop meaning what they meant — but only some.
The Semantic Authority Bridge watches the definitions a decision was
bound to, and when one changes it reopens **only the affected
decisions**. Everything else stays as it was. While a decision is
reopened, consequential actions under it are refused until a human
re-evaluates it under the new meaning. There is no global STOP involved:
unaffected decisions keep working.

## What it is not

- **Not a live NVIDIA integration.** The bridge reads and writes
  Apache Ossie YAML (the documented interchange format for NVIDIA
  Auto-Ontology) and native Auto-Ontology YAML/JSON as *files*, on this
  computer. It implements the 9 read-only MCP tools from NVIDIA's
  `docs/mcp.md` as **local in-memory methods** — there is no MCP
  server, no MCP client transport, no JSON-RPC, and no live tool call.
  There is no NIM endpoint, no Postgres connection, and no network call
  anywhere in the bridge. The receipts' own verdict is
  `QUALIFIED_CANDIDATE (LOCAL DETERMINISTIC & OSSIE YAML / MCP ADAPTER
  VERIFIED; LIVE REMOTE NVIDIA NIM DEPLOYMENT HOLD)`. Do not claim a
  live NVIDIA deployment, NVIDIA endorsement, or that NVIDIA's
  converter will accept the bridge's files: that needs a live import
  test, which has not been run.
- **Not an external receiver's signature.** Each bridge instance
  generates a fresh ephemeral Ed25519 steward key and receiver key
  (unless the caller supplies keys). The "certification attestation"
  is therefore a self-attestation by the bridge instance, not a
  signature from an independent external receiver or a long-lived
  steward. It proves the record was not altered after signing, not
  that an outside authority endorsed it, and not that the underlying
  claim is true. Attestations do not survive a process restart unless
  the caller supplies persistent keys.
- **Not an HTTP 409.** Stale-authority refusal surfaces as the Python
  exception `StaleSemanticAuthorityRefused` from
  `attempt_consequential_action`. The bridge has no POST endpoint, so
  there is no HTTP status for it. The workbench previously labelled a
  refusal "HTTP 409"; that label was wrong and has been removed.

## Files

| Path (under `applications/`) | What it is |
|---|---|
| `core/semantic_authority_bridge.py` | The bridge (1,787 lines). Import, signing, binding, change detection, refusal, re-authorization, case-history export/verify, the 9 local MCP-tool methods, the local recompilation simulation, and the C0/C1/C2 comparators. |
| `capabilities_007_008/generated/semantic_authority_bridge_cap.py` | 007/008 capability wrapper: `run_semantic_authority_bridge(facts)`. Registered in `capabilities_007_008/registry_g4_semantic.json` and dispatched by `capabilities_007_008/kernel.py` (schema-witness validation of `project_id`, `initial_ontology`, `decisions`). |
| `run_semantic_authority_001.py` | The full runner: 11-stage loop, 60-episode holdout, 3-application dogfood (Energy Commons, Civic, Advocate), 10-vector adversarial suite, Worker A→B inheritance. Writes `SEMANTIC_AUTHORITY_001_RECEIPTS.json` beside itself. |
| `tests/test_semantic_authority_001.py` | 7 tests (test_01–test_07). |
| `openline_semantic_authority_workbench.html` | Workbench served at `GET /semantic`. Shows the three dogfood applications and the receipts JSON from `GET /api/semantic/state`. |
| `examples/ontologies/*.yaml` | 4 Ossie fixtures: Energy Commons, Civic, Advocate, Biotech Clinical Cold-Chain (the unfamiliar domain used by Worker B). |
| `examples/semantic_authority_bridge_example.py` | Runnable end-to-end example (see below). |
| `SEMANTIC_AUTHORITY_001_RECEIPTS.json` | Precomputed receipts from the full runner on this release tree (regenerated during integration). Served read-only by `GET /api/semantic/state`. |
| `ADVOCATE_CASE_PACKET_001_RECEIPTS.json` | Advocate 4-case handoff receipts from the candidate (supporting evidence only; produced on the older base). |

## Interface (for another coding agent)

```python
from core.semantic_authority_bridge import (
    SemanticAuthorityBridge,
    SemanticOntologyModel,
    StaleSemanticAuthorityRefused,
    simulate_nvidia_semantic_recompilation,
)

bridge = SemanticAuthorityBridge()  # fresh ephemeral keys, temp state dir
model = bridge.import_ontology(
    open("examples/ontologies/energy_commons_ossie.yaml").read(),
    auto_sign_certified_with_pinned_steward=True,
)
bridge.register_evidence_document("DOC-1", "Tariff schedule text.")
bridge.bind_decision(
    project_id="PROJ-1",
    decision_id="DEC-1",
    conclusion_summary="Option 3 is cheapest.",
    proposed_action="Sign the EPC contract.",
    bound_term_ids=["TERM_NET_AVOIDED_ELECTRICITY_COST"],
    bound_sql_attr_ids=["SQL_ATTR_AVOIDED_TOU_COST"],
    bound_join_edge_ids=["REL_METER_TO_SERVICE_TARIFF"],
    bound_evidence_doc_ids=["DOC-1"],
)

report = bridge.detect_and_apply_semantic_changes(new_model, project_id="PROJ-1")
# report["affected_decisions"] -> reopened; report["unaffected_decisions"] -> kept

bridge.attempt_consequential_action(
    project_id="PROJ-1", decision_id="DEC-1",
    task_id="TASK-1", action_note="Sign the contract.",
)  # raises StaleSemanticAuthorityRefused while DEC-1 is REOPEN; else executes

bridge.reevaluate_and_authorize(
    project_id="PROJ-1", decision_id="DEC-1",
    disposition="AUTHORIZE_CONTINUATION",  # or "REFUSE_AND_HOLD"
    updated_conclusion_summary="...",
    authorization_note="...",
)
packet = bridge.export_verifiable_case_history(project_id="PROJ-1")
verdict = SemanticAuthorityBridge.verify_imported_case_history(packet)
```

Notes:

- `import_ontology` accepts an Ossie YAML string, an Auto-Ontology
  YAML/JSON string, or a dict. YAML text needs PyYAML
  (`requirements.txt`: `PyYAML==6.0.2`); dict input works without it.
- `detect_and_apply_semantic_changes` takes a `SemanticOntologyModel`
  (build one from a dict, or from
  `simulate_nvidia_semantic_recompilation(model)` for the local Boundary
  B simulation). It reopens only affected decisions; unaffected
  decisions stay CURRENT and keep executing.
- Re-authorizing a decision whose meaning changed requires the steward
  to re-certify the revised definition first (re-import with
  `auto_sign_certified_with_pinned_steward=True`, or
  `sign_all_certified_terms_in_ontology`). A changed meaning cannot be
  re-authorized on the old attestation: `reevaluate_and_authorize`
  raises `SemanticValidationError` while the attestation is stale.
- `register_evidence_document` refuses in-place rewrites of a
  registered document ID (`HistoricalEvidenceRewriteRefused`); a new
  version is a new document, the old bytes stay intact.
- `SemanticOntologyModel` also exposes the 9 local MCP-tool methods:
  `mcp_check_readiness`, `mcp_search_terms`, `mcp_get_term`,
  `mcp_get_term_columns`, `mcp_get_term_sql_attributes`,
  `mcp_get_sql_attribute`, `mcp_describe_table`,
  `mcp_check_answerable`, `mcp_ask_question`. Local in-memory only.
- The capability wrapper runs the same flow through the 007/008
  kernel: `kernel.execute("semantic-authority-bridge", facts)` with
  `facts = {"project_id": ..., "initial_ontology": {...},
  "decisions": [...]}`. The kernel validates the schema first.

## Dependency-tracking model (SSB-CDIG)

Each bound decision pins a `CanonicalSemanticSlice` of four digests:

1. **Expression-and-column digest** — the SQL expression, normalized
   through a token-level AST signature (invariant to whitespace,
   casing, and comments), plus verified `table.column` existence,
   types, unit, grain, and denominator.
2. **Join-subgraph digest** — the transitive closure of default
   semantic-FK join paths the decision relies on.
3. **Certification-witness digest** — the receiver-pinned Ed25519
   steward attestation over the term ID, the certified flag, and the
   two digests above. (Self-attestation per instance; see above.)
4. **Evidence-basis digest** — SHA-256 plus character spans of the
   supporting records in `originals/`.

A change reopens a decision only if one of its four digests changes.
Synonym, description, and version-number edits do not change any
digest, so they never reopen anything. A formula change, a unit or
grain change, a join-default flip (Boundary B: recompilation reselects
the default FK edge, alphabetically first when neither column is the
unqualified `<target>_id`), a certification revocation without a
version bump (Boundary A), a missing column, or an evidence rewrite
does change a digest, and reopens exactly the decisions bound to it.

Guards: destructive SQL/DDL (`DROP`, `DELETE`, `TRUNCATE`, `UPDATE`,
`INSERT`, `ALTER`, `GRANT`, `COPY TO PROGRAM`, `pg_read_file`,
`xp_cmdshell`, `;--`) and prompt-injection patterns
(ignore-previous-instructions, bypass-receiver-authority,
auto-approve-all-commits) are rejected at import.

## Receipt format

- Bridge receipts: schema `openline.semantic_authority.receipt.v1`
  (per action, appended to `bridge.receipts`).
- Case history: schema `openline.semantic_authority.case_history.v1`
  (`export_verifiable_case_history` /
  `verify_imported_case_history`).
- Full runner receipts: schema
  `openline.semantic_authority_breakthrough_001.master_receipt.v1`
  (`SEMANTIC_AUTHORITY_001_RECEIPTS.json`).

Signatures in receipts establish record integrity, provenance, and
authorization at a point in time. They do not establish empirical
truth, legal validity, or external authority.

## HTTP surface

Served by `applications/genie_server.py` (loopback-only, Host/Origin
check applies to all `GET /api/*`, same as every other API route):

- `GET /semantic` — the workbench page (static HTML).
- `GET /api/semantic/state` — **read-only**. Serves the precomputed
  `SEMANTIC_AUTHORITY_001_RECEIPTS.json` shipped with the release. If
  that file is absent, it returns a `not_computed` status (HTTP 503)
  telling the operator to run the runner; it never runs the suite or
  writes files from a GET.
- `GET /api/semantic/state?probe=recompile` — runs the local, read-only
  Boundary B recompilation simulation against the shipped Energy
  Commons fixture and reports which default FK join edges changed.
  No files are written, no live service is used.

Recompute the receipts with:

```bash
python3 run_semantic_authority_001.py   # inside applications/
```

## Plug-in points

- **Living Projects / Decision Recall**: the bridge records bindings
  in `core/recall.py`'s `RecallLedger` and refuses through
  `core/openline_guard.py`'s receiver path. Neither file needed
  changes.
- **Dogfood**: Energy Commons, Civic, and Advocate (Case Packets) —
  the three applications whose decisions the runner binds.
- **Not plugged in**: the root Genie server (thin v0.7.1 server, no
  workbench-route precedent) and Robotics Studio
  (`openline_robotics_001/vendor_009/` is a separate vendored
  snapshot).

## Reproducible example

```bash
python3 examples/semantic_authority_bridge_example.py   # inside applications/
```

It loads the Energy Commons fixture, binds two decisions, shows a
harmless edit reopening nothing, a formula change reopening only the
affected decision, a stale-action refusal, a successful action under
the unaffected decision, re-authorization after re-certification, and
a verified case-history export. Exit code 0 means every check passed.

## Security and privacy limitations

- Local-only. No network, no telemetry, no outbound calls. The
  bridge never executes SQL against a real database; SQL attributes
  are validated, never run.
- Ephemeral keys (see above). Receipts are not stable across runs:
  the receiver public key changes on every fresh bridge instance.
- Ossie file-level compatibility only (see above). No live NVIDIA
  integration, no endorsement claim.
- Single-operator boundary, same as the rest of the applications
  server: anyone who can reach the loopback port is the operator.
  State (the recall ledger SQLite file) lives in the bridge's state
  directory; same-OS-user processes can read it.
- The 60-episode holdout in the runner is self-constructed (a fixed
  script), not an external held-out set. Treat its accuracy as a
  regression signal, not an independent evaluation.
