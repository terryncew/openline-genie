# Dependencies, Licensing & Security Disclosures

## 1. Runtime Dependencies
- **Python 3.11+ Standard Library**: `sqlite3`, `http.server`, `hashlib`, `hmac`, `json`, ` math`, `datetime`, `unittest`, `urllib`.
- **`cryptography` (Python package, Apache-2.0 / BSD-3-Clause)**: Used for Ed25519 cryptographic signing and verification of project state receipts and portable bundles.
- **Node.js 18+ Standard Runtime**: Used by `living_world/graph_core.mjs` and `idea_layer/export_brief.mjs` (zero external npm packages required at runtime).
- **Optional Paid Model Adapter (`OFF` by default)**: `core/model_adapter.py` is disabled by default (`use_model=False`). No API keys or network calls are required or performed in Free Local Mode.

## 2. Security & Privacy Architecture
- **Loopback-Only Binding**: The local HTTP server binds strictly to `127.0.0.1` (the `--host` flag accepts only `127.0.0.1` or `localhost`; any other host is refused, and the server code itself refuses non-loopback binds). It enforces `Host` checks on all `/api/*` read endpoints and `Host`, `Origin`, and `Content-Type: application/json` checks on all state-changing `POST` requests, so a web page on another site cannot read or change your projects through the browser.
- **What loopback does NOT protect**: anyone (or any program) already running on your computer as the same user can reach the server and read or change projects, keys, and the database — there is no login. The server has no TLS. Static pages (the app's own files) are served to any `Host` value because they contain no personal data; only the `/api/*` data endpoints check `Host`. Do not expose the port to a network.
- **No Included Private Keys or Personal Data**: Ephemeral local signing keys (`.genie_key_owner`, `receiver_ed25519.seed`) are generated fresh on first run inside your local `--state-dir` with owner-only (`0600`) file permissions and are never bundled in the source release.
