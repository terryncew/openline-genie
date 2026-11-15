# Conformance truth table

`PYTHONPATH=src python -m unittest discover -s tests -v` exercises 35 methods:
- Mandate signature, subject, seller, operation, target, parameter digest, expiry, amount, revocation and key succession
- Atomic SQLite-local business effects, replay and changed-request conflict, 12-thread concurrency and restart
- Unknown simulated settlement, post-settlement checkpoint crash and explicit seller-asserted refund-due/compensation (mock only)
- Signed refusal without forged caller identity attribution, signed outcome binding, historical chain and anchored head checks
- FastAPI protected ingress and blocked old route; real HTTP TestClient but NOT remote/production deployment
- Six MCP tool descriptions and test-only JSON-RPC stdio subprocess, NOT official SDK negotiation
- x402 v2-shaped decimal/epoch/EVM/Solana string validators, NOT official x402 integration

This product is a narrow generalization of PR95/96 local architecture. The existing conventional comparator attains correctness parity and no independent DX/time experiment occurred. Signed records are seller attestations only.
