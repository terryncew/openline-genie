# OpenLine Genie — Sample Projects

Each `.json` file in this folder is a self-contained, checksum-verified OpenLine Genie project file that you can inspect, share, or restore using **Import / Restore Project** in `http://127.0.0.1:8795/products`:

1. `sample_1_energy_commons.json` — **Energy Commons**: 24-unit apartment cooperative comparing grid baseline, rooftop solar PV, LiFePO4 battery storage, and solar + phase-change thermal water storage across 6 sensitivity scenarios.
2. `sample_2_advocate.json` — **Advocate**: Synthetic utility medical-baseline and disaster-relief appeal packet separating verified facts, unverified claims, and missing documents with automatic privacy redaction.
3. `sample_3_capability_commons.json` — **Capability Commons**: Reusable community project library index coordinating clean water filtration, cooperative childcare/kitchens, and building weatherization retrofits.
4. `sample_4_science.json` — **Science**: Reproducible 80-episode thermal-hydraulic research workspace comparing four competing models with AIC/MDL complexity penalties and preserved negative findings.
5. `sample_5_civic.json` — **Civic**: Municipal water resilience comparison across four proposals with P10/P50/P90 storm-outage cost bands and resident parcel-map challenge records.

## Semantic Authority Bridge (v1.2.0-rc1)

- `ontologies/*.yaml` — Apache Ossie YAML ontology fixtures for the bridge: Energy Commons, Civic, Advocate, and Biotech Clinical Cold-Chain (the unfamiliar domain used by the Worker A→B inheritance check). Each one is a plain file you can open, edit, and re-import; no live service is involved.
- `semantic_authority_bridge_example.py` — Runnable end-to-end example. Run it from inside `applications/` (`python3 examples/semantic_authority_bridge_example.py`): it binds two decisions to the Energy Commons fixture, shows a harmless edit reopening nothing, a formula change reopening only the affected decision, a stale-action refusal, and re-authorization after re-certification. Exit code 0 means every check passed. Full interface, model, and receipt-format docs: `SEMANTIC_AUTHORITY_BRIDGE.md`.
