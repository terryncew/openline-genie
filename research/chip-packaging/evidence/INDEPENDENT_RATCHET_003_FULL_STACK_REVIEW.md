# Independent Ratchet 003 repaired full-stack review — November 16, 2026

## Disposition
**Software packaging HOLD; water-positive civilization-ratchet claim FALSIFIED within the supplied model's own claim boundary.** This is not a claim that waste-heat desalination is physically impossible; it is a finding that this package does not substantiate it.

## Artifact
Repaired complete archive `OPENLINE_CIVILIZATION_RATCHET_003_REPAIRED_FULL_STACK.zip`, SHA-256 `ca322f0ac0637ca223fe88655b112b7280b6e3ab9b9fc06d6d9aebd15e3bbc1f`, 6,797,637 bytes. This matches Argon's screenshot. The associated Google Doc still mentions `119ecb...` as a repaired-stack hash, so it is not a receipt for this exact ZIP.

## Reproducibility receipt
Archive extracts, but its root `SHA256SUMS.txt` lists **343** artifacts of which **329 match** and **14 are absent** (8 case-packet ZIPs and 6 browser artifacts). No hash mismatches among extant listed files. Root manifest therefore FAILS in a clean extract. The earlier original standalone research ZIP may have separate acceptance and is not overwritten. A full local unittest run did not conclude within the execution window and generated SQLite ResourceWarnings; this report does not certify Argon's 201/201 or Muse 24/24.

## Discriminating scientific falsifier
In `core/civilization_ratchet_003_physics.py` / `evaluate_lifecycle_economics_across_scales`, warm-water options are assigned fixed `site_wue_l_per_kwh` = 0.0 and MED options are assigned **-2.82 L/kWh** whenever `nominal_coolant_inlet_c >= 50`. Cooling overhead fractions, equipment CAPEX and water credit rates are likewise selected from constants. The calculation does **not** derive MED recovered heat, motive source temperature feasibility, gain-output-ratio performance, feedwater availability/quality, condenser heat rejection, brine disposal, electricity use, plant CAPEX/maintenance, or water sale/distribution constraints from physical inputs.

Using the exact unmodified model function and all identical inputs except `mean_coolant_outlet_c`, we independently got WUE=-2.82 L/kWh and PUE=1.0563 at **40, 55, 69, and 85 °C**. The model's stated MED motive source threshold is 65 °C, so 40 °C should not yield the same positive distillate. Even a model-independent dry cooler would need source ambient, thermal approach, heat rejection, fallback and hourly climate constraints, which are absent from this economic function.

The headline 123.52 million liters/year is arithmetically **5,000 kW × 8,760 hours/year × 2.82 L/kWh**. It is not a calculated consequence of distillation thermo-hydraulics. This means the claimed 195.79-million-liter annual net swing is not a verified design outcome; it adds baseline evaporative consumption to assumed distillate production, which are different water-accounting quantities.

## Appropriate next gate
For water-positive deployment claims, a legitimate independent plant-level solver must close heat & mass balances for MED (including temperatures, approach, finite pinch, effect-by-effect GOR, source water, salinity, pumping and discharge), alternative dry/wet cooling heat rejection under hourly weather, safety margin at real chip/HBM thermal limits, credible installed cost and rated operations. Then compare to a **matched modern dry/hybrid cooling and waste-heat-recovery baseline**, not a water-heavy legacy tower. The decisive hardware experiment remains separately required to establish package feasibility and signal-routing capability.

## Classification
Research mechanism **HOLD** (physical integration may be plausible), standalone software **FAIL root manifest**, civilization-ratchet and water-positive numerical claims **NOT ACCEPTED**. Replay code `independent_check.py` and full `independent_receipt.json` are enclosed. No physical testing or paid engineering was performed.
