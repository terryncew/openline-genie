# How to reproduce every number

You need a computer with Python 3.10 or later and nothing else. No
account, no network access, no paid service, and no contact with the
author is required. The whole reproduction takes about two minutes on a
modest machine.

## One command

From the `simulation/` directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run_reproduction.py
```

The script runs four stages and compares every number to the expected
values in `simulation/expected/`. It prints PASS or FAIL for each check
and exits non-zero on any mismatch. When it passes, the last line reads:

```
REPRODUCTION PASSED: every numerical result matches the expected values.
```

The script writes its fresh outputs next to itself
(`ablation_results.json`, `RATCHET_003_ROUND_004_*.json`, and inside
`mif004/` the regenerated evidence, figures, and manifest). Those files
are generated outputs, not part of the tree; they are listed in
`simulation/.gitignore`.

## What each stage does

### Stage 1 — Tournament ablation

`tournament_ablation.py` runs the tournament model on seven controlled
variants and one severe operating case, then computes the parity check.

The model scores each design in teraflops of compute per dollar of
five-year lifecycle cost at a modeled scale of 2,500 units. The model is
a coupled electro-thermal simulation: it solves heat flow and power
loss for a compute module, applies a holdout survival test, and divides
the surviving compute by the lifecycle cost. The inputs that matter
most are assigned, not measured: manufacturing yield (0.945 for the
proposed design, 0.865 for the conventional design), the
power-delivery resistance, and the die and packaging costs. That is why
the ablation exists — to show how far the score moves when those
assigned values change.

Expected results (`expected/ablation_results.json`):

| Variant | Score | Cost | Peak temp. | Power-delivery loss |
| --- | --- | --- | --- | --- |
| Conventional, as configured | 1.5540 | $11,011 | 108.2 °C | 181.13 W |
| Conventional, same 0.75 mm cooling | 1.8671 | $10,490 | 82.4 °C | 181.13 W |
| Direct-to-silicon control | 1.6945 | $11,565 | 81.3 °C | 181.13 W |
| Proposed design, as configured | 3.0571 | $6,479 | 60.3 °C | 6.67 W |
| Proposed, power-delivery advantage removed | 2.7099 | $7,243 | 65.0 °C | 181.13 W |
| Proposed, cost advantage removed | 2.1733 | $9,114 | 60.3 °C | 6.67 W |
| Proposed, both advantages removed | 1.9871 | $9,878 | 65.0 °C | 181.13 W |

The severe case (a harsher operating point) leaves the conventional
design as configured at 138.7 °C and not surviving, the matched
conventional design at 87.3 °C and surviving, and the proposed design
at 66.2 °C and surviving.

The parity check: equalizing the assigned yield alone brings the
proposed design to 1.9040. Equalizing yield, die and packaging cost,
power-delivery resistance, and amortized tooling cost brings it to
1.8733, against 1.8671 for the matched conventional design — a
**+0.332%** difference, effectively parity. This is an algebraic
counterfactual, not a claim that the designs are physically equal. It
shows that the nearly twofold modeled advantage is conditional on
several unmeasured values. The ablation output itself reproduces
exactly; the original six-step runner is numerically reproducible for
headline metrics but not byte-deterministic (figure hashes and
machine-epsilon receipt values change on regeneration).

### Stage 2 — Split-plane repair round

`frontier_repair_round_004.py` runs the same tournament model on a
physically coherent alternative: keep the proven signal interposer and
change only the back side (integrated cooling plus power delivery).

Expected results (`expected/r004_source_bound_results.json`):

| Variant | Score | Cost | Peak temp. | Change vs matched conventional |
| --- | --- | --- | --- | --- |
| Matched conventional | 1.8637 | $10,509 | 82.4 °C | — |
| Split-plane (interposer kept) | 1.8142 | $10,819 | 67.5 °C | −2.7% |
| Split-plane, optimistic power delivery | 1.9148 | $10,344 | 62.4 °C | +2.7% |
| Split-plane, assumed yield improvement | 2.2019 | $8,995 | 60.3 °C | +18.2% |
| Proposed design, as configured | 3.0571 | $6,479 | 60.3 °C | +64.0% |

The last two rows assume values that have not been demonstrated. The
split-plane result that uses no assumed advantage is the −2.7% row.

Note the matched conventional design scores 1.8637 here against
1.8671 in stage 1. The two matched arms are not identical: stage 1's
matched arm also changes the substrate to 4 mm of copper (thickness
and conductivity), while stage 2's matched arm changes only the
cooling pitch, interleaving, strainers, and cooling hardware cost.
Both are fair comparisons; they answer slightly different questions.

### Stage 3 — First-principles gates

`first_principles_gates_004.py` is plain arithmetic with no model
behind it. It checks three hard limits that no packaging change can
evade:

- **Electricity floor.** A 20-petaflops module drawing 1,000 W for five
  years (43,800 hours) at $0.10 per kilowatt-hour costs $4,380 in
  electricity alone. The best possible score at that power is therefore
  4.566 teraflops per dollar, and the largest advantage packaging alone
  can give over the matched conventional design is 2.45×. A 10× gain
  would need total five-year cost of $1,073 or less — below the
  electricity bill alone. Packaging alone cannot deliver it.
- **Power-delivery bound.** 1,000 W at 0.78 V is 1,282 A. Keeping the
  loss under 18 W needs an equivalent resistance under 10.95
  micro-ohms. The proposed design's claimed 6.67 W loss implies 4.06
  micro-ohms after a 0.29 adjustment factor. An ideal 4 mm solid copper
  path at that resistance needs about 17 mm² of cross-section — before
  vias, contacts, ground return, and the insulation that separates the
  fluid from the conductors. The claimed resistance is an assigned
  value, not a solved three-dimensional result.
- **Routing bound.** 8,192 parallel signal crossings on one 8 µm-pitch
  layer need 65.5 mm of width for a 45 mm cut. The routing result is
  therefore impossible on width alone, before any real pin map or
  layer count is considered.

Expected results: `expected/r004_first_principles_gates.json`.

### Stage 4 — Physical screening package and audit checks

`mif004/run_all_physical_experiment_004.py` regenerates the screening
package's evidence, bill of materials, CAD files, and figures, checks
that a second regeneration is byte-identical, runs the 7 unit tests in
standard and optimized mode, and verifies its 18-artifact manifest. It
prints `ALL 18 ARTIFACTS ... VERIFIED SUCCESSFULLY` when it passes.
(The original package's manifest counted 26 artifacts; the public tree
ships the runnable subset — the manufacturing protocol, the package
README, and the recovered upstream copies are not included — so the
count is 18. See `SOURCES.md`.)

Then `mif004/independent_challenge_004.py` re-runs the independent
audit's checks against the regenerated package and the driver compares
the key findings to `expected/independent_challenge_results.json`:

- Heater netlist: 16 heaters of 15 ohms at 24 V = **614.4 W**
  calculated, against 50 W claimed (12.288× over).
- Heater fit: four 15.76 mm packages need 63.04 mm; 45 mm available;
  not geometrically possible as drawn.
- STEP file: no solid body, closed shell, or faces; 139 reference
  points.
- Power-delivery solver: 16 × 16 grid, no third-dimension nodes.
- Signature: the fixed seed reconstructs the advertised public key, and
  a forged signature on altered evidence validates against it.
  Independent witness authority: false.
- Desalination replay: the solver returns 5.803 and 8.459 liters per
  kilowatt-hour at 69 °C and 85 °C, against 2.753 and 6.809 claimed in
  the receipt.

## Glossary

The code keeps the original authors' identifiers. This is what they mean:

- **A0** — the conventional design: chiplets on a commercial interposer
  with a lidded split-flow cold plate.
- **A1** — an existing direct-to-silicon control (pillars straight to
  the silicon, no interposer).
- **G2** — the proposed MIF-PWS v2 design, as configured by its author.
- **Matched conventional** — A0 given the same 0.75 mm interleaved
  counter-flow cooling geometry as the proposed design, so the
  comparison isolates what the rest of the proposal adds.
- **Split-plane** — a variant that keeps the proven signal interposer
  and changes only the back side (cooling and power delivery).
- **PDN** — power delivery network: the conductors that carry current
  from the package pins to the transistors.
- **RDL** — redistribution layer: the wiring layer that fans signals
  out from the die's fine pitch to the package's coarser pitch.
- **HBM3e** — high-bandwidth memory, generation 3e: stacked memory
  dies connected to the processor by thousands of short, dense wires.
- **CoWoS** — chip-on-wafer-on-substrate: TSMC's commercial
  interposer packaging (CoWoS-L uses sub-micron wiring; CoWoS-R uses
  six layers at 2 µm pitch).
- **TFLOPS per 5-year dollar** — the model's score: teraflops of
  compute divided by the five-year lifecycle cost per module in dollars.
- **Holdout survival** — the share of modeled operating cases in which
  the design stays within its thermal limits.
- **Yield** — the share of manufactured units that work. In this model
  it is an assigned number, not a measured one.
- **MED** — multi-effect distillation: a way to produce fresh water
  from warm water by evaporating it in stages. The GOR (gain output
  ratio) is the ratio of water produced to heat supplied.
- **TO-247** — a standard package for power transistors, 15.76 mm wide.
- **STEP / DXF / STL / SPICE** — file formats: STEP is a CAD exchange
  format for solid models, DXF is a 2D drawing format, STL is a mesh
  format, SPICE is a circuit-simulation netlist format.
- **Ed25519** — a digital signature scheme. A signature proves the
  signer held a private key; it proves nothing about whether the signed
  content is true, and if the key is derivable from public source, it
  proves nothing about who signed it either.

## What you can investigate with ordinary equipment

- **Everything in this reproduction.** A standard computer runs all
  four stages. No laboratory, no fabrication, and no special hardware
  is needed.
- **The arithmetic.** Every number in the tournament, the gates, and
  the audit checks can be recomputed by hand from the inputs listed in
  the code. The most useful check is the heater calculation: 24² / 15
  = 38.4 W per heater, × 16 = 614.4 W.
- **The CAD files.** The STEP files can be opened in any text editor;
  search for `MANIFOLD_SOLID_BREP`, `CLOSED_SHELL`, or `ADVANCED_FACE`
  and find zero occurrences. The DXF and STL can be opened in a free
  CAD viewer.

## What needs laboratory or fabrication equipment

- **A real cooling measurement** needs a machined cold plate, a pump,
  a flow meter, and temperature sensors — off-the-shelf laboratory
  components, but the test fixture must be redesigned first: the
  current heater layout does not fit and draws twelve times the stated
  power.
- **A real electrical measurement** needs a low-voltage, high-current
  supply (1,282 A at 0.78 V is a specialized supply), Kelvin sensing,
  and a licensed professional engineer plus a safety review before
  anything is energized.
- **Anything involving a silicon interposer, fine-pitch wiring, or a
  working chip** needs a foundry or an advanced packaging facility.
  That is not a bench experiment.

See [LIMITATIONS.md](LIMITATIONS.md) for what is still unknown and what
would have to change before any hardware work.
