# Verified compatibility and release claims

| Boundary | Executed | Result |
|---|---|---|
| Python 3.13 and inherited cryptography 46.0.4 | Yes | 46 local tests PASS; local wheel CLI/test-only stdio PASS |
| Deterministic wheel build | Yes | Two fixed-epoch wheels byte-identical |
| PEP 621 source distribution | Yes | sdist built locally; fresh installation unresolved |
| Python 3.11/3.12/3.14/3.15 | No | NOT EXECUTED (metadata range is not evidence) |
| Fresh `cryptography==50.0.2` resolution | Attempted | HOLD: public index not reachable |
| Official `mcp>=2,<3` SDK negotiate/list/call | Attempted dependency, unavailable | NOT EXECUTED; JSON-RPC fallback is not official conformance |
| ChatGPT custom MCP remote connection | No | NOT EXECUTED; requires remote server or Secure MCP Tunnel and eligible plan/permissions |
| Official x402 facilitator and live settlement | No | NOT EXECUTED; fictional signed assertion only |
| Independent coding-agent cold adoption | No | NOT EXECUTED |
| Source rights and patent grant | Audit only | HOLD pending qualified review and founder approval |

Authoritative sources: https://py.sdk.modelcontextprotocol.io/ (MCP v2); https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt; https://pypi.org/project/cryptography/50.0.2/.

This standalone export removes the historical unsafe compatibility flag. An unguarded grant-free option is deliberately unsupported.
