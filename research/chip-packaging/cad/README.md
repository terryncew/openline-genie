# CAD files — unqualified research artifacts

**Do not build from these files. The hardware is on HOLD.**

These files are published so readers can inspect what was drawn and
verify the independent audit's findings. They are not fabrication
drawings and not a build package.

- `mif_pws_v2_hybrid_coldplate.step` — described in its source package
  as a solid model of a 45 × 45 × 6.0 mm cold plate with 60 channels.
  It is not a solid: it is a text wrapper containing 139 reference
  points, with no solid body, closed shell, or faces (finding F3 in
  `../LIMITATIONS.md`). A machine shop cannot make a part from it.
- `mif_pws_v2_cmc_kerf_bridge.step` — described as a solid model of a
  45 × 45 × 1.5 mm copper-molybdenum-copper bridge with an 8 × 8 kerf
  grid. Same defect: 30 reference points, no solid body.
- `mif_pws_v2_hybrid_coldplate.stl` — a mesh of the cold plate (732
  facets). A mesh is a surface for viewing, not a machinable solid.
- `mif_pws_v2_machining_drawing.dxf` — a 2D machining drawing with a
  45 × 45 mm outline. It is a drawing of a design whose thermal model
  and physical dimensions disagree (finding F4): the model counts 60
  passes per header where the drawing has 30 channels, and the model
  uses a 22.5 mm channel length against about 42 mm drawn.

The concept illustration in `../figures/` (the fabrication blueprint
SVG) is a drawing, not a CAD model, and carries the same HOLD status.

Before any fabrication could be quoted or attempted, a real solid
model would have to be produced in CAD, the channel count and length
reconciled with the thermal model, and the electrical design corrected
(findings F1 and F2). See `../LIMITATIONS.md`.
