# Simulation

Everything in this directory runs on a standard computer with Python
3.10 or later. See `../REPRODUCE.md` for the one-command reproduction
and the glossary of terms used in the code.

## Layout

- `tournament_model/` — the tournament model: one module, copied
  unchanged from the research archive, plus a short provenance note.
  It depends only on numpy and scipy.
- `tournament_ablation.py` — the independent ablation: seven
  controlled variants, one severe case, and the parity check.
- `frontier_repair_round_004.py` — the split-plane repair round: six
  variants on the same model.
- `first_principles_gates_004.py` — the electricity-floor,
  power-delivery, and routing bounds. Standard library only.
- `mif004/` — the physical screening package: the physics simulation,
  the falsification battery, the bill-of-materials generator, the CAD
  generator, the one-command runner, and the 7-test suite. It also
  holds `independent_challenge_004.py`, the independent audit's checks.
- `expected/` — the expected results for every stage. The reproduction
  script compares its fresh outputs against these files exactly.
- `run_reproduction.py` — the one-command driver. Run it from this
  directory.
- `requirements.txt` — pinned dependencies.

## A note on the code's language

The code keeps the original authors' identifiers (A0, G2, and so on).
They are defined in the glossary in `../REPRODUCE.md`. The code files
themselves are historical artifacts; their comments use the original
wording. The prose in this section — the README, the reproduction
guide, the limitations, and the sources — is written in plain language
and does not rely on those identifiers.

## Generated outputs

Running the reproduction writes fresh outputs into this directory
(`ablation_results.json`, the two `RATCHET_003_ROUND_004_*.json`
files, and inside `mif004/` the regenerated evidence, figures, CAD
files, and manifest). Those files are generated outputs, not part of
the tree, and are listed in `.gitignore`. The regenerated CAD files
and netlist are unqualified research artifacts; see `../cad/README.md`
and `../LIMITATIONS.md`. Do not energize anything they describe.
