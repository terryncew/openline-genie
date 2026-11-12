# Genie Receiver Adapter Boundary (design only, RC6)

A third-party AI agent can drive the same Genie receiver/project interface
the built-in worker uses. This is a documented design. It is NOT a
compatibility claim: no Claude, ChatGPT, or MCP integration has been built
or tested against it. Do not claim one until an actual integration passes
end-to-end tests (criteria at the bottom).

## Transport

- HTTP, loopback only: the server binds `127.0.0.1:8795` by default.
  The loopback server is not an OS permission boundary (inherited RC3 limit).
- Same-origin browser UI only. There is no remote endpoint, no bearer
  scheme, and no owner-issued capability grant implemented in RC6.
  Any future remote adapter must add owner-issued grants and is out of
  scope for this release.

## Endpoints (all JSON; POSTs need `Content-Type: application/json`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Liveness + spend ledger summary |
| GET | `/api/projects` | List projects |
| GET | `/api/project?project_id=` | Full bundle (see state shape) |
| GET | `/api/bakery/paths?project_id=` | Next-step assumption patches for a bakery project |
| POST | `/api/build` | Create a project. Body: `{prompt, use_model}`. `use_model:false` is the deterministic fallback; `use_model:true` runs the Haiku worker through `src/core/model_adapter.py` (spend-capped, $5.00 cumulative — reservation-based: the adapter reserves the worst-case cost before dispatch and holds the reservation as recorded spend when usage metadata is missing; see "Spend cap" below). |
| POST | `/api/propose` | Create an exploratory proposal. Body: `{project_id, summary, patch}`. The patch is a partial state (e.g. `{bakery:{assumptions:{...}}}`); the engine recomputes derived values and validates. Never mutates accepted state. |
| POST | `/api/accept` | Accept a proposal. Body: `{project_id, proposal_id}`. Accepted state changes; a signed receipt is issued. |
| POST | `/api/reject` | Reject a proposal. Body: `{project_id, proposal_id, reason}`. Accepted state is byte-identical afterward. |
| POST | `/api/stop` | Freeze the project. Propose/accept then return 409; reject still allowed. |
| POST | `/api/replace_worker` | Replace the active worker (new Haiku worker). Accepted state and its SHA are preserved. |
| POST | `/api/close`, `/api/reopen` | Close / reopen a project. |
| GET | `/api/export?project_id=` | The real runnable accepted app (single HTML file). |

## State shape (GET /api/project)

```json
{
  "project_id": "...",
  "project_family": "bakery",
  "accepted": {
    "version": 2,
    "state_sha256": "...",
    "state": { "...": "canonical accepted state" },
    "state_canonical_json": "{... exact bytes the receipt binds ...}",
    "receipt": { "receipt": { "payload": { "receipt_id": "..." } } }
  },
  "exploratory": [
    { "proposal_id": "...", "summary": "...",
      "candidate_state": { "...": "..." },
      "candidate_sha256": "...", "status": "EXPLORATORY_PENDING" }
  ],
  "rejected": [ { "proposal_id": "...", "summary": "..." } ],
  "stopped": false,
  "status": "open",
  "active_worker_id": "worker-a",
  "receiver_public_key": "...",
  "owner_public_key": "..."
}
```

Notes:

- `exploratory` lists every proposal row, including rejected ones; filter
  by `status === "EXPLORATORY_PENDING"` for open proposals.
- Receipts are Ed25519 signatures over the canonical accepted state.
  Verify `accepted.state_sha256` against `accepted.state_canonical_json`
  (the exact bytes) and the receipt against the pinned
  `receiver_public_key`. The living-world UI pins the key on first load
  and marks any later mismatch UNVERIFIED_IMPORT.
- The project graph, constraints, and signed evidence are
  model-independent: they are functions of accepted state, not of which
  model built the project. Discovery (counterfactuals, synergy combos,
  opportunities) is computed from that state by the frozen
  `graph_core.mjs` and needs no model call.

## Rules an adapter must follow

1. Read state only through `/api/project`; never invent a parallel store.
2. Change state only through `/api/propose` + owner accept/reject.
   Discovery NEVER auto-applies: every improvement is a reversible
   exploratory proposal until the owner accepts it.
3. Respect STOP (409 on propose/accept while stopped) and the 60-second
   in-flight token TTL: revocation bounds, never instant.
4. Keep prompts under 100K and all model calls spend-capped through
   `src/core/model_adapter.py`. The $5.00 cumulative cap binds in full.

## Spend cap (reservation-based, r5)

Before any model call the adapter atomically checks the cap against
committed spend (settled total + open reservations) and persists an
open reservation for the call's worst-case cost in `spend.json`
before dispatch; a call whose worst case would exceed the remaining
cap is refused before dispatch and recorded as a `refused`
reservation entry. After the call the reservation is reconciled to
actual usage when the provider returns usage metadata. When usage is
missing — or the call fails after dispatch (timeout, unparseable
output, unexpected shape) — the reservation is held at worst case as
recorded spend (flagged `reservation_held` / `usage_missing`), never
$0. A call the provider explicitly refuses (429/529/…) releases its
reservation at $0. The running total is therefore an upper bound on
true provider spend, never a lower bound. `spend.json` gains only a
top-level `"reservations"` list; `total_usd()` keeps its
settled-only meaning, while `committed_usd()` (settled + open
reservations) is what the cap is enforced against. Residual gaps:
ledger disk failure, input-token estimate approximation,
cross-process race, direct helper calls bypassing the adapter
(see `REPAIRS_R5_B2.md` §6).

## What an end-to-end test of a third-party adapter must show

A second agent implementation, built independently of the RC3 worker,
driving the endpoints above against a fresh project: fetch bundle, verify
the receipt against the pinned key, propose a real change, have the owner
accept it in the UI, and confirm the accepted state, receipt, and
re-projected graph all change consistently — with reject restoring the
exact accepted state. Until that run exists, there is no compatibility
claim.
