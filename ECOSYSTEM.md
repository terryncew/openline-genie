# Find OpenLine's public work

OpenLine is a family of **free, local-first research and developer tools**. This page points to repositories that are already public. The main user-facing entrypoint is [OpenLine Genie](https://github.com/terryncew/openline-genie); the projects below have different levels of readiness. A green software test does not prove a physical instrument or real-world service is qualified.

## Start with Genie

**[OpenLine Genie](https://github.com/terryncew/openline-genie)** — [try the browser experience](https://terryncew.github.io/openline-genie/try/). The main repository documents an original Genie v0.7.1 release and **seven local applications**: Energy Commons, Advocate, Capability Commons, Science, Civic, Neighborhood, and Robotics Studio. The six non-robotics applications share a local server; Robotics Studio has its own server. See [the application installation instructions](applications/INSTALL.md) and the [agent/reproduction guide](AGENTS.md). These are local tools, **not** a hosted multi-user service. Independent browser, system and hardware validations vary; see each release's declared limitations.

## Research with a concrete physical target

**[Physical Witness](https://github.com/terryncew/openline-physical-witness)** — open research into early fouling of water-treatment membranes. Its [frozen computational research release](https://github.com/terryncew/openline-physical-witness/releases/tag/v0.4.0-rc4) includes simulations, design concepts, baselines and documented failures. Later public experimental supplements explore low-cost benchtop instrumentation, reference contamination and a modular flow-cell fixture. **No working physical sensor or demonstrated water/energy savings.** Native hardware signoff and laboratory measurements remain pending; see [current research status](https://github.com/terryncew/openline-physical-witness/blob/main/RESEARCH_STATUS.md). Private and unaccepted research is not represented as a public release.

## Core agent authority and interoperable components

- **[OpenLine](https://github.com/terryncew/openline)** — receiver-owned authority, signed receipts and STOP in a local developer preview. SQLite-local effects only; not production payment or security infrastructure.
- **[Living Projects](https://github.com/terryncew/openline-living-projects)** — a standalone local developer preview demonstrating receiver acceptance, recovery and portable receipts. Some related functionality is now included in Genie; this remains a separate reference implementation, not a second required platform.
- **[Connect](https://github.com/terryncew/openline-connect)** — developer-preview receiver controls for externally proposed agent actions, with fictional/local effects.
- **[World](https://github.com/terryncew/openline-world)** — experimental receiver-authorized activity projection; check its own README before use.

## Other public applications and experiments

- **[OpenLine Energy](https://github.com/terryncew/openline-energy)** — advisory solar/energy scenario explorer, not equipment control.
- **[OpenLine Idea Layer](https://github.com/terryncew/openline-idea-layer)** — structured ideas and coding-agent briefs; hypotheses, not verified demand.
- **[Robot Academy](https://github.com/terryncew/openline-robot-academy)** — offline robotics learning, no physical robot required.

## Evidence and participation

Follow the **README, installation/replay instructions, release tags, known failures, and test limits in each repository**. A claimed independent benchmark win, autonomous invention, commercial performance improvement or physical validation must be reproduced in the corresponding source before it is treated as established.

Researchers and engineers can inspect the public Physical Witness code and propose issues, corrections, conventional comparisons, or a blinded experiment with actual water and a known fouling ground truth. **No laboratory endorsement or physical validation is claimed.** Open contributions should not contain confidential research archives, private data, credentials or access keys.
