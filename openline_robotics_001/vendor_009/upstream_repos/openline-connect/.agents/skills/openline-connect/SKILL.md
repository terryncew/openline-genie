---
name: openline-connect
description: Protect AI-invoked local business actions with explicit receiver grants, durable replay protection, and signed outcomes. Use for MCP tool authorization, default-deny operations, or offline receipt verification.
---

# Connect a fictional local business operation

Read `README.md` first. This developer preview is not production payment infrastructure or an approved ChatGPT connector.

- Install from this standalone project with `python -m pip install ".[mcp]"` in an environment with package-index access.
- `openline-connect init --home .openline` creates owner keys and **no grants**.
- `openline-connect allow --home .openline --action record.update --target customer-1 --value approved --amount-cents 100 --ttl-seconds 300` explicitly grants the exact local operation.
- `openline-connect serve --home .openline` starts an official MCP stdio server **only if** the SDK is installed. Do not assume public ChatGPT connection.
- `openline-connect verify --home .openline --seller-public HEX` checks signed local results against an externally pinned key.

Never auto-approve, expose raw seller/SQLite handlers, or treat an MCP host's confirmation as receiver authorization. Only the intentionally unsafe test-only `--fallback-stdio` flag uses a non-SDK JSON-RPC subprocess.
