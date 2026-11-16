# Limitations and feasibility findings

This page states what is wrong, what is unknown, and what would have
to change before any hardware work. Nothing here is a measured result.
Every number is a model output or an arithmetic check of a drawing.

## Hardware status: HOLD

No hardware has been fabricated, energized, or measured. The
manufacturing and test instructions are withheld. The drawings in
`cad/` are unqualified research artifacts, not fabrication drawings.
The heater netlist in `evidence/defective_heater_netlist.sp` is a
defective artifact published as evidence of the error, not a circuit to
build. Do not energize any part of this design as drawn.

## The eight feasibility findings

An independent review of the physical experiment package found the
following. The full review is in
`evidence/independent_review_004.md`; the checks that reproduce each
finding are in `simulation/mif004/independent_challenge_004.py`.

### F1. The electrical test would draw 614.4 W, not 50 W

The heater netlist specifies sixteen 15-ohm resistors in parallel at
24 V. Each draws 24² / 15 = 38.4 W. Sixteen draw 614.4 W — 12.288
times the 50 W stated for the surrogate test stage. The same error
appears in the bill of materials: the 3 × 3 surrogate entry claims
50 W total at 24 V for nine 15-ohm resistors in parallel, which is
345.6 W. Any bench run built to the stated wiring would overheat the
fixture and the supply. A corrected design needs a current-limited,
physically checked wiring diagram with fusing and thermal cutoffs, and
it needs to be reviewed before any energized test.

### F2. Sixteen power-transistor packages do not fit the 45 mm face

The test fixture mounts sixteen TO-247 power-transistor packages
(Vishay LTO100) in a 4 × 4 grid on a 45 mm face. Each package is
15.76 mm wide. Four across need 63.04 mm. The layout is mechanically
impossible as drawn. The fixture must be redesigned around the actual
package dimensions, or a different heater must be chosen.

### F3. The STEP files are not manufacturable solids

Both STEP files are ISO 10303-21 AP214 text wrappers containing only
reference points — 139 in the cold plate, 30 in the kerf bridge — with
no solid body (`MANIFOLD_SOLID_BREP`), no closed shell
(`CLOSED_SHELL`), and no faces (`ADVANCED_FACE`). A machine shop
cannot make a part from them. A real solid model must be produced in
CAD and checked before any fabrication is quoted or attempted.

### F4. The coolant flow numbers are inconsistent

The thermal model counts 60 coolant passes per header; the physical
drawing has 30 channels per header. The model uses a channel length of
22.5 mm (half of 45 mm); the drawn channel run is about 42 mm. The
modeled velocity is 0.397 m/s; continuity at the stated flow rate
gives 0.794 m/s. The model and the drawing describe different hardware.
They must be reconciled — one channel count, one length, one velocity —
before any thermal claim can be tested.

### F5. The claimed 3D power-delivery solver is a 2D lumped network

The power-delivery solver is a 16 × 16 grid of lumped resistors with
no nodes in the third dimension. It is a two-dimensional model, not
the three-dimensional solver its name claims. The claimed 6.67 W loss
and 4.06 micro-ohm equivalent resistance are assigned values inside
that model, not results of a solved three-dimensional layout with vias,
contacts, ground return, and insulation. A real power-delivery claim
needs a three-dimensional extraction from a real layout.

### F6. The evidence signing key is derivable from public source

The screening package signs its evidence with an Ed25519 key derived
from a fixed literal seed embedded in the source code. Anyone who reads
the source can reconstruct the private key and sign altered evidence
that validates against the advertised public key — the independent
review demonstrated exactly that. The signatures in this research
prove only that a file was reproduced from the same source. They are
not independent attestation, and no signature in this section should be
read as one.

### F7. The desalination receipt conflicts with the numerical output

The facility receipt claims 2.753 liters per kilowatt-hour at 69 °C
and 6.809 at 85 °C. Re-running the solver returns 5.803 and 8.459.
Neither figure is a measured result, and the gain output ratio is
prescribed from an assumed number of effects rather than derived from
a heat-and-mass balance. No desalination has been demonstrated.
**The freshwater-production claim is not established and must not be
presented as a demonstrated benefit.** Any future claim needs a
conserving model (heat input, temperature grade, mass, plant energy,
feedwater, and the minimum motive heat) and a measured result.

### F8. "Approval-free 50 A" is not an acceptable safety classification

Energized testing at 1,000 W and 1,280 A was described as approval-free
at 50 A. That is not a safety classification. Any energized test needs
a licensed professional engineer and an environmental health and safety
review, a documented safety boundary, and a pressure-relief and
thermal-cutoff design before power is applied.

## What the models do not establish

- **Manufacturing yield.** The tournament model assigns yields: 0.945
  to the proposed design, 0.865 to the conventional design. No yield
  has been measured, and no yield model based on a defect distribution
  exists. The modeled advantage collapses to parity when the yields
  are equalized.
- **Electrical performance.** No three-dimensional power-delivery
  resistance has been solved from a real layout. The 6.67 W loss is an
  assigned value. The first-principles bound (1,282 A, under 10.95
  micro-ohms for under 18 W) is a necessary condition, not a result.
- **Reliability.** No corrosion, fatigue, sealing, or long-term test
  data exists. The model includes corrosion and thermal-expansion
  solvers, but they are constitutive checks on assumed parameters, not
  measurements.
- **Total production cost.** The bill of materials mixes sourced
  catalog prices with engineering estimates, and the two must not be
  confused (see below). No supplier has quoted the custom fabrication,
  and no prototype has been costed from a real build.
- **High-bandwidth signal routing.** The proposed design cannot route
  HBM3e on a single 8 µm layer (343 of 1,750 nets). That figure comes
  from a closed-form escape calculation, not from routing a real netlist
  on a real pin map. A routed netlist on a real pin map does not exist.
- **Novelty.** Prior work exists in the same space: TSMC's CoWoS-R
  (4 µm wiring) and CoWoS-L (sub-micron), Georgia Tech's
  through-silicon-via and microfluidic work, a 2026 direct-to-package
  cooling paper, and a 2026 glass interposer with embedded cooling.
  Whether any part of this proposal is new has not been established.

## Cost sensitivity

The itemized bill of materials (`simulation/mif004/bom/`) totals
$8,483.18: $1,820.78 in sourced catalog prices and $6,662.40 in
engineering estimates. The two categories are different kinds of
numbers. A catalog price is a price you can pay today. An engineering
estimate is a guess about what custom fabrication might cost. The
tournament model's cost advantage for the proposed design depends on
the estimates, not on the catalog prices.

Per-approach totals from the bill of materials:

| Approach | Total |
| --- | --- |
| M0 conventional cold plate | $644.19 |
| M0 control (matched geometry) | $855.68 |
| M1 direct-to-silicon | $1,522.90 |
| M2 hybrid (CNC + copper-molybdenum-copper bridge) | $1,422.60 |
| M3 full custom | $6,495.00 |
| S0 surrogate test stage | $689.10 |

The S0 surrogate total of $689.10 is the cost of the test fixture
whose electrical design is wrong by a factor of twelve (F1) and whose
heater layout does not fit (F2). The figure is preserved as part of the
record; it is not a costed build.

A realistic sensitivity: if the custom fabrication estimates are
doubled, the proposed design's modeled cost advantage largely
disappears; if they are halved, it grows. Neither change is supported
by a quotation. The honest statement is that the cost is unknown until
a shop quotes a real solid model — and no real solid model exists (F3).

## Negative results preserved

Two negative results from the original research are preserved because
they constrain the design space:

- **Scale mismatch.** Bolting a 1 kW cold plate onto a 0.14 W
  milliwatt-scale die (a 7,143× power mismatch) makes the combined
  design 63.89% worse per dollar than the small die alone. The
  cooling hardware does not transfer across that scale gap.
- **Thermal survival is a property of the cooling geometry, not the
  proposal.** Giving the conventional design the same 0.75 mm
  interleaved counter-flow geometry lets it survive 90% single-header
  blockage at 71.88 °C. The proposed design's incremental physical
  contribution is the power-delivery loss reduction (21.60 W in the
  hybrid variant and 7.21 W in the full-custom variant, against
  105.10 W for the matched conventional control) and the removal of
  the thermal interface material and lid — not thermal survival itself.
- **Cross-industry transfer denied.** The same approach was tested
  for transfer to an electrochemical desalination stack and rejected:
  an advantage ratio of 0.91, below 1.0, because thermal diffusion
  across copper is roughly 76,000 times faster than ionic diffusion in
  water. The design does not transfer to that domain.

## What would have to change before any hardware work

1. A corrected electrical design: current-limited wiring, fusing,
   thermal cutoffs, and a heater layout that fits the packages. The
   614.4 W error must be fixed in the netlist, the bill of materials,
   and the test protocol together.
2. A real solid model (STEP with a closed solid body) that a machine
   shop can quote and build from.
3. A reconciled thermal model: one channel count, one channel length,
   one velocity, matching the drawing.
4. A three-dimensional power-delivery extraction from a real layout.
5. A yield model derived from an inspectable defect distribution, or a
   measured yield from a real build.
6. A routed signal netlist on a real pin map, or an explicit statement
   that the design does not attempt fine-pitch signal routing.
7. A licensed professional engineer and an environmental health and
   safety review, with a documented safety boundary, before any
   energized test.
8. A fresh signature scheme with a randomly generated key held by an
   independent party, if signatures are to mean anything beyond
   reproduction.
9. A conserving water model and a measured result before any
   freshwater claim is made.

Until those exist, the research stays a computational snapshot, and the
hardware stays on HOLD.
