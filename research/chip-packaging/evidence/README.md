# Evidence

These files are the independent checks, published unchanged so readers
can see what was found and how.

- `independent_acceptance_report.md` — the independent falsification
  of the original research. Disposition: the "verified" claim is
  falsified as stated; the work is adopted as a research hypothesis.
  It contains the tournament table, the parity calculation (+0.332%),
  and the negative results.
- `independent_review_004.md` — the independent audit of the physical
  screening package. Disposition: adopt as a computational study; hold
  drawing-based fabrication and physical performance claims. It lists
  the eight findings F1–F8, stated in full in `../LIMITATIONS.md`.
- `repair_round_004.md` — the repair-round analysis: the split-plane
  alternative, the electricity floor, the power-delivery bound, and
  the routing bound. It suspends the earlier water-positive figure
  until the model conserves heat, temperature, mass, plant energy,
  feedwater, and motive heat.
- `INDEPENDENT_RATCHET_003_FULL_STACK_REVIEW.md` — a full-stack
  review of the original research, preserved from the screening
  package. It falsifies the water-positive claim within the model's own
  claim boundary.
- `defective_heater_netlist.sp` — **do not energize.** The heater
  netlist from the screening package, published unchanged as evidence
  of finding F1. Sixteen 15-ohm resistors in parallel at 24 V draw
  614.4 W, not the 50 W the test stage claimed. It is included so any
  reader can run the calculation themselves
  (`simulation/mif004/independent_challenge_004.py` does exactly that).
  It is not a circuit to build.
- `independent_challenge_results.json` — the audit's recorded results
  for the checks above (heater power 614.4 W, no solid body, forgeable
  signature, desalination replay values). The reproduction script
  compares its fresh run against the copy in
  `simulation/expected/`.

The step-by-step manufacturing and test instructions from the
screening package are withheld; see `../SOURCES.md` for the exclusion
and its reason.
