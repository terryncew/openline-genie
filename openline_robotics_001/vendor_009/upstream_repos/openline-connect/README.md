# OpenLine Connect

**Receiver-owned execution controls and verifiable outcomes for AI agents.** A local business controls which agent requests are allowed, saves exactly one fictional SQLite effect per permitted request, and signs decisions that another machine can audit. No real funds, provider credentials or external side effects.

> **Developer Preview — Local Fictional Effects.** This is a local evaluation build, not production payment infrastructure or an approved ChatGPT directory plugin. SQLite-local effects only; see `docs/SECURITY.md`.

## Four commands

Use Python 3.11+. After cloning the standalone public source into a directory with Python 3.11+ and package-index access:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install ".[mcp]"
openline-connect init --home .openline
openline-connect allow --home .openline --action record.update --target customer-1 --value approved --amount-cents 100 --ttl-seconds 300
openline-connect serve --home .openline
# After an MCP client invokes openline_execute_protected_action using the grant JSON:
openline-connect verify --home .openline --seller-public <PINNED_PUBLIC_KEY_FROM_INIT>
```

`init` grants nothing and prints a receiver public key; pin that key outside any returned receipt. `allow` writes a fictional agent's signed request into `.openline/grants/`. The official SDK server uses local stdio and waits for a client. Run `serve` under an MCP client configured for that command; it doesn't silently execute an operation. `verify` returns a nonzero exit code when no receipt exists, the signature is wrong or the expected history is missing. Initial README docs do **not** promise a one-click ChatGPT connection.

## One-command fictional smoke test

```bash
openline-connect demo
python -m unittest discover -s tests -v
```

The demo creates fresh receiver and fictional buyer keys and a temporary receiver-signed grant, commits one local record update, safely replays it and verifies the signed history offline. It does not contact a chain, facilitator, provider or outside organization.

## Test a source checkout before installing

Python 3.11+ and `cryptography` are required. From the repository root:

```bash
python -m pip install 'cryptography>=42,<51'
python scripts/run_tests.py
PYTHONPATH="$PWD/src" python -m openline_connect.cli demo
```

The test runner supplies an absolute source path to subprocesses, including
those started from a temporary directory. It also works when invoked by its
absolute filename from another directory. The public package remains rc2;
`unified-demo` and Accept conformance belong to a separate candidate and are
not commands in this release.

## Security and limits

All exposed MCP execute tools go through the default-deny SQLite engine. Authorized effects are **SQLite-local**, within one trusted host, and concurrent retry protection is bounded by that transaction. The package cannot protect against a privileged operator, direct database writes or effects in external systems. A signature proves that the receiver made a claim and that an observer's pinned key can validate it; it does not independently prove delivery, payment settlement or historical completeness without a pinned expected head.

An MCP SDK is required for `serve`. The `--fallback-stdio` option is a test-only JSON-RPC fixture and is **not** MCP conformance evidence. Public ChatGPT connector eligibility and permissions must be checked separately. See `docs/SECURITY.md`, `docs/COMPATIBILITY.md`, and `docs/CONFORMANCE.md`.

**Preview verification status:** the core tests and fictional local onboarding have passed; the exact public export still needs fresh dependency installation and an official MCP SDK handshake on an internet-connected runner. No real payment or hosted ChatGPT connector was tested. Existing correctness comparisons show parity with standard EdDSA/JWS + SQLite. The commercial value of lower developer friction and independent adoption remains unverified.
