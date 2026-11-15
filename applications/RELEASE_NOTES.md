# OpenLine Genie v1.0.0-RC1 — Public Release Notes

## Highlights
- **Five Complete Applications in One Local Suite (`/products`)**:
  1. **Energy Commons**: 10-year cooperative energy & hot-water cash-flow comparison with a calculation cross-check (each 10-year cost recomputed from the reported figures; agreement within $0.05), 6-scenario sensitivity matrix, and 4 built-in guards against unrealistic vendor assumptions.
  2. **Advocate**: Institutional appeal packet organizer with conservative deadline calculation, three-bucket evidence separation (`Verified fact`, `Unverified claim`, `Missing information`), rule effective-date verification, and automatic PII redaction.
  3. **Capability Commons**: Portable library of executable community projects (Water Filtration Hub, Cooperative Childcare & Kitchen, Building Weatherization & Workshop) plus one-prompt custom project creation and cross-machine export/restore.
  4. **Science**: Reproducible research environment with AIC/MDL complexity penalties, permanent negative-result preservation (`0` erased findings), dataset drift flagging, and independent zero-trust replay.
  5. **Civic**: Public infrastructure comparison under P10/P50/P90 uncertainty, evidence-linked citizen challenges, and one-click standalone HTML decision dossier export.
  6. **Neighborhood (ClearCovenant)**: Understand HOA rules, resolve disputes, compare costs, and manage community records — as a local single-user tool. The server binds loopback only, client-supplied identity is ignored (the local operator is the only actor), and multi-household separation is not a supported deployment. Includes 12 HOA conflict scenarios, draft responses, vendor/reserve comparison, and portable export.
- **Plain User-Facing Language**: Replaced internal engineering codes with clear status indicators (`Waiting for your review`, `Accept changes`, `Needs another review`, `Some supporting information is missing`, `Approval required`) while keeping full cryptographic receipts and SHA-256 checksums accessible in the expandable **Technical & Audit Details** drawer.
- **One-Command Local Launch**: Added `launch_genie.py` and `run_openline_genie.sh` for zero-cost (`$0`) local operation without API keys, plus 5 ready-to-import sample projects in `examples/`.
