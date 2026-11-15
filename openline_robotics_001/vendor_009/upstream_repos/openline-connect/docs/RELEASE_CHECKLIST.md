# Publisher checklist — developer preview

1. Founder and qualified rights reviewer clear chain of title for every exported source file, AI-assisted contributions, employer/contractor/invention assignments, and patent license consequences; approve the **exact** public tree.
2. Independently verify Python 3.11 and 3.13 clean install using `cryptography==50.0.2` and `mcp>=2,<3` with complete logs; execute `scripts/official_mcp_smoke.py` (real SDK, no fallback).
3. Inspect the public export for signing secrets, private URLs, internal history, unsafe old authorization paths and artifacts. Review wheel/sdist contents and verify their SHA-256 against release manifest.
4. Apache-2.0 and the NOTICE are staged in this public-candidate tree. Confirm the rights authorization covers these exact bytes before public distribution.
5. Obtain founder approval for the final repository name, commit/tag, license, exact artifacts and publication wording. Only then create a separate public repository / push verified tag / publish draft release notes. Do not modify visibility of existing research repository.
6. Do not publish to PyPI, turn on actions runners, deploy a server, use a real payment facilitator or contact external companies under the existing release commission.

Production use is not approved: TLS, external settlement reconciliation, key custody, completeness witness, operator permissions, supply-chain and independent penetration testing are outside this preview.
