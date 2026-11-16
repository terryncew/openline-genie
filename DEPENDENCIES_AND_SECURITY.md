# Dependencies & Security Boundary (`v1.2.0-rc2`)

## Runtime Dependencies (`requirements.txt`)

- `cryptography>=41.0.0` — Ed25519 signing and verification (`ReceiverGuard`, `RecallLedger`, portable capability capsules).
- `numpy>=1.26.0` — Deterministic operational, thermodynamic, and multi-body robotics simulation arrays.
- `onnxruntime>=1.16.0` — CPU execution provider for 2-layer MLP robot policies in Robotics Studio (with automatic pure-NumPy fallback if the C++ wheel is absent).

## Security & Containment Boundary

- **Local Loopback Only**: `genie_server.py` and `launch_genie.py` bind to `127.0.0.1` / `localhost` by default and reject cross-origin `POST` requests (`403`).
- **No Untrusted Python Execution**: Portable capability capsules (`core/portable_verified_inheritance.py`) do not execute arbitrary Python strings via `exec()`. Only Ed25519-authenticated capsules matching allowlisted kernel hashes (`ALLOWLISTED_CAPSULE_KERNELS`) are admitted.
- **No Paid API Keys Required**: Paid model dispatch is OFF by default (`use_model=False`, `$0.00` cost).
