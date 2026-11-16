# OpenLine MIF-PWS v2 — Physical Experiment 004: Independent Acceptance

**Date:** 2026-11-16  
**Source:** `OPENLINE_MIF_PWS_V2_PHYSICAL_EXPERIMENT_004_PACKAGE.zip` (original unmodified)  
**SHA-256:** `d0feb99bdbdc9d695de5acc6ec33e8f645eb2a2ca4854ed972eb15cd0a63ae4b`  
**Evidence SHA-256:** `7f84efe061072a534d1bd64df597f4332dae0945a020320c3e31a16de5cb8b76`  
**Disposition:** ADOPT AS COMPUTATIONAL STUDY / HOLD DRAWING-BASED FABRICATION AND PHYSICAL PERFORMANCE CLAIMS.

## Confirmed

- ZIP hashes: all supplied manifest entries verified, 27 contained files including manifest, valid ZIP.
- `python -m unittest discover -s tests -v`: 7/7 PASS, with Pillow deprecation warnings; `python -O ...`: 7/7 PASS.
- Real, runnable calculations, separate conceptual options, BOM labeled catalog vs estimated, DXF/STEP/STL/SPICE files, physical-stage kill criteria, and properly reported **zero actual hardware measurements**.
- **Material negative result:** same-source escape-count model rejects replacing HBM3e CoWoS routing using the proposed one-layer 8 µm RDL: 343/1750 nets routed, 1407 unrouted. Still a simplified analytical router, not production DRC, but a valuable falsification.
- **Matched-pitch incumbent** in the model also survives 90% single-header blockage; thus no demonstrated unique thermal resilience from the novel arrangement.
- MED threshold now outputs zero below 65°C; does not validate a real desalination plant.

## Additional release blockers found in independent code/geometry inspection

**F1 — The electrical fixture does NOT deliver the declared 50 W surrogate load as netlisted.** `cad_and_drawings/mif_pws_v2_kelvin_and_rdl_netlist.sp` connects 16 separate `R_HEATER` resistors of 15 Ω directly across the fixed 24 V `V_HEATER`. Arithmetic: `16×24²/15 = 614.4 W`, or 12.288× the claimed 50 W. Even installing only the nine 15 Ω heaters listed for S0 and wiring all nine in parallel at 24 V would yield 345.6 W. A current-limited supply might reduce voltage; that is not what the supplied netlist represents. The 1 Ω full-load BOM heaters are also distinct from the netlist's universal 15 Ω. **Do not energize this fixture from the published electrical schematic.** Provide distinct current-limited, physically checked stage-specific wiring diagrams with fuse/thermal cutoffs before any supervised bench run.

**F2 — Heater package geometric collision.** The manufacturer's LTO100 TO-247 datasheet (https://www.vishay.com/docs/50051/lto100.pdf; Rev 29 Apr 2026) specifies 15.76 mm package body width and about 20.7 mm body height. The design mounts 16 LTO100 onto a 4×4, 45 mm active face at 11.25 mm tile pitch. Just four package widths span 63.04 mm, exceeding 45 mm without clearance; a direct flat-mounted 4×4 array as described is mechanically impossible. A smaller foil/alumina heater or external thermal spreading fixture requires a new explicit mechanical design and BOM.

**F3 — Invalid claim of manufacturable solid STEP model.** `cad_and_drawings/mif_pws_v2_hybrid_coldplate.step` is an AP214 text wrapper containing 139 `CARTESIAN_POINT` entities and product metadata, but no `MANIFOLD_SOLID_BREP`, `CLOSED_SHELL`, or `ADVANCED_FACE` representations. The DXF and STL may be useful starting visuals but the STEP is *not* a solid model of machinable channels, sealed manifolds, and coaxial penetrations. CAD interference, wall thickness, leak-tightness and independently importable B-rep checks have **not** passed.

**F4 — Flow-count and length mismatch in hydraulic equations.** The code declares 60 total interleaved channels (= 30 per header), but the flow solver uses `n_passes_per_header = spec.channel_count_total` (= 60), underestimating healthy flow velocity: 0.397 m/s reported vs 0.794 m/s by basic continuity at 2.5 L/min and 0.35×2.50 mm section. Its hydraulic channel length uses `45/2 = 22.5 mm` when the issued CAD coordinates show an X-channel run of ~42 mm. Pressure drop and pump requirements must be recomputed with physically consistent network topology, split-half manifolds only if drawn and plumbed, and measured pump curves. This undermines even the small model pressure-drop numbers; its correct numerical energy conservation is insufficient to prove hydraulic correctness.

**F5 — The so-called 3D PDN Laplace solver is a 2D network with lumped resistance terms.** `solve_3d_pdn_resistance_and_joule_heating` builds a 16×16 nodal matrix indexed only by `ix,iy`, with no z-axis finite-volume nodes. It adds assumed topology-specific spreading and contact resistance factors. Useful as a lumped electrical screening model, but cannot establish 3D connection/return-current, contact, skin, heating, field strengths, electromigration or true 1,280 A performance.

**F6 — Digital signature has no independent signer authority.** `sign_evidence_payload_ed25519` derives its private signing key from a fixed literal seed embedded in distributed Python source. I changed the evidence's `mission` field, signed using only the public source, and verified the forged version with the claimed public key. Ed25519 is functioning; custody is not. Treat signatures as reproducibility decorations, not external independent attestation. Use a distinct externally held key if claiming third-party witness acceptance.

**F7 — The MED receipt description disagrees with the computed result.** Its falsifier `FALS-EXP04-07` hardcodes a PASS narrative claiming **2.753 L/kWh at 69°C and 6.809 at 85°C**. The exact supplied solver and stored numeric sweep return **5.803** and **8.459 L/kWh**, respectively. The boolean test only checks zero below threshold and monotonic above it; it does not assert those descriptive values. The plant model still assigns gained-output ratio `GOR = 0.84 * effect_count`, a prescribed `usable_heat_fraction`, and no empirical or equipment qualification. Thus the formerly invented fixed −2.82 L/kWh was replaced by *temperature-dependent assumptions*, not demonstrated desalination.

**F8 — “Approval-free 50 A” is not an acceptable universal safety classification.** The Stage-1 description calls 50 A DC injection approval-free. Low voltage does not remove burn, short-circuit, and conductor-heating hazards; require competent local electrical risk review, appropriate current limits and hardware protection even for the 50 A test. No purchased or energized equipment was part of this audit.

## Strongest surviving proposition

Develop a **small independently instrumented copper cooling-path and Kelvin electrical-resistance coupon**, preserving the matched-pitch conventional control. The decisive measurements are electrical voltage-drop/resistance under safe controlled conditions, steady-state and blocked-header temperature maps, accurate pressure drop/flow under a physically drawn network, and coating leakage after wet thermal cycling. A successful *small coupon* would support the mechanism, not prove high-volume GPU packaging, HBM replacement, or water-positive data centers.

## Scientific disposition / acceptance gates

- **ADOPT:** Code and test concept for research; real falsifiable acceptance criteria; honest HBM routing failure; corrected physical boundaries compared with 003.
- **HOLD:** Custom fabrication from these STEP drawings; stage 1 heater connection and 50 A safety procedure; claimed thermal/hydraulic and PDN advantages; all TCO, high-current, desalination and wider societal outcomes.
- **NO NEXT SYNTHETIC TOURNAMENT**: First fix F1–F4 and externally review the revised coupon/fixture; all simulations remain modeling only. No orders, energization or publication were made.

## Reproduce this audit

Unzip the original Argon package, verify with `sha256sum -c SHA256SUMS.txt`, place `independent_challenge_004.py` in the extracted root, run `python independent_challenge_004.py`. The audit is non-mutating and produces exact calculations in `independent_challenge_results.json`. Datasheet dimensions are separately cited from Vishay's first-party publication above. The 7 bundled unit tests are independent replays of Argon's code, not third-party measurement.
