# Extending this research or submitting a correction

Corrections are welcome. The most useful ones are the ones that replace
an assigned value with a measured one.

## What would move this research forward

In order of value:

1. **A measured yield.** A defect distribution from a real wafer or
   package run, or a measured yield from a built coupon. The modeled
   advantage depends on the assigned 0.945 vs 0.865 yields; a measured
   number would settle the parity question.
2. **A solved three-dimensional power-delivery resistance.** A
   resistance extracted from a real layout with vias, contacts, ground
   return, and insulation — not an assigned value. The bound is 10.95
   micro-ohms for under 18 W of loss at 1,282 A.
3. **A routed netlist.** A real HBM3e pin map routed on the proposed
   wiring, or a demonstration that a different pitch or layer count
   closes the gap. The current result is 343 of 1,750 nets on one
   8 µm layer.
4. **A quoted fabrication cost.** A quotation from a machine shop or
   packaging house against a real solid model. The current cost figures
   are engineering estimates, not quotations.
5. **A measured thermal result.** A built cold plate, a pump, a flow
   meter, and temperature sensors — after the electrical design is
   corrected and a safety review is done.

## How to submit a correction

- Open an issue on the repository with the finding, the file and line
  it concerns, and the corrected value with its source. A correction
  that changes a number should include the calculation or the
  measurement behind it.
- For a code change, keep the reproduction passing:
  `simulation/run_reproduction.py` must print
  `REPRODUCTION PASSED`. If your change intentionally changes an
  expected result, update the corresponding file in
  `simulation/expected/` and say why in the pull request.
- Do not submit hardware build instructions. The hardware is on HOLD
  (see [LIMITATIONS.md](LIMITATIONS.md)); step-by-step fabrication or
  energized-test instructions will not be accepted until the findings
  there are resolved.
- Do not submit a new signature scheme that derives a key from a fixed
  seed. See finding F6 in [LIMITATIONS.md](LIMITATIONS.md).

## Style

Write in plain language. Define every abbreviation at first use. Keep
model outputs and measurements in separate sentences — never present a
model output as a measurement. If a claim depends on an assumption,
state the assumption in the same paragraph as the claim.
