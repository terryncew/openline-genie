#!/usr/bin/env python3
"""Bakery operating model for OpenLine Genie RC6 (`core/bakery.py`).

The engine holds structured bakery assumptions as ACCEPTED STATE — never
browser demo defaults. All numbers the living-world graph shows for a
bakery project come from here (via the accepted state's ``bakery``
record); the frozen ``graph_core.mjs`` only does the min-of-constraints
projection and the counterfactual arithmetic on top of those numbers.

Capacity math (deterministic, no invented business outcomes — only
computed capacity / cost / throughput from stated assumptions):

- oven_capacity   = ovens * decks_per_oven * batch_size_loaves
                    * (bake_window_minutes / cycle_minutes)
  Baseline: 1 * 1 * 29 * (300 / 50) = 174 loaves/day.
  (29 loaves/batch, 50-minute cycle, 6 batches across a 300-minute
  bake window, 05:00-10:00. The RC5U demo text said "24 loaves/batch";
  the engine is the authority and 24 x 7.25 batches is not a real
  bake plan, so the engine states 29/batch and the integration layer
  rewrites the demo's display text from this record.)
- staff_capacity  = loaves_per_baker_per_shift
                    + (bakers - 1) * extra_baker_loaves
                    + (staggered_shift_bonus_loaves if staggered_shift)
  Baseline: 240. A second baker adds 160 (shared bench), a staggered
  shift adds 60. Additive by construction, so the graph's path deltas
  (+160, +60) and the engine agree on every combo.
- ingredient_capacity = proofing_rack_loaves
                    + extra_retarder_racks * retarder_rack_loaves
  Baseline: 280. Each extra retarder rack adds 60.
- throughput = min(oven, staff, ingredients, demand, shop, schedule,
  wish, scenario) — the binding constraint is the minimum, exactly as
  ``computeConstraintResonance`` computes it.
- net_daily_usd = round(throughput * margin_per_loaf_usd - fixed_cost)
  with fixed_cost = base 140 + (ovens-1)*15 + (staggered? 35)
  + (bakers-1)*165 + extra_retarder_racks*12, and capex likewise from
  the same per-change prices (oven 18500, baker 600, retarder 3200).
  These per-change prices mirror the frozen graph_core path deltas;
  they are stated here so the engine and the graph can never drift.
- Uncertainty band is +/-uncertainty_pct (7%) around throughput.

No customer behaviour, demand forecast, or savings is invented:
demand_loaves_per_day is a stated assumption (320), and throughput
never exceeds it only because it is one of the min() inputs.
"""
from __future__ import annotations

import copy
from typing import Any

# Node ids in the frozen graph_core bakery demo. The engine's computed
# capacities are keyed by these ids so the integration layer can wire
# them straight into the projected graph.
NODE_IDS = (
    "wish", "demand", "ingredients", "staff", "oven",
    "schedule", "shop", "scenario",
)

BASELINE_ASSUMPTIONS: dict[str, Any] = {
    # Oven
    "ovens": 1,
    "decks_per_oven": 1,
    "batch_size_loaves": 29,
    "cycle_minutes": 50,
    "bake_window_minutes": 300,
    # Staff
    "bakers": 1,
    "loaves_per_baker_per_shift": 240,
    "extra_baker_loaves": 160,
    "staggered_shift_bonus_loaves": 60,
    "shift_pattern": "05:00-13:00",
    "staggered_shift": False,
    # Ingredients / proofing
    "proofing_rack_loaves": 280,
    "extra_retarder_racks": 0,
    "retarder_rack_loaves": 60,
    # Fixed capacities (stated assumptions, not computed)
    "demand_loaves_per_day": 320,
    "shop_capacity_loaves": 300,
    "schedule_capacity_loaves": 360,
    "wish_capacity_loaves": 500,
    "scenario_capacity_loaves": 400,
    # Prices / costs (USD)
    "loaf_price_usd": 8.50,
    "variable_cost_per_loaf_usd": 4.00,
    "margin_per_loaf_usd": 4.50,
    "fixed_cost_usd_per_day": 140,
    "uncertainty_pct": 7,
}

# Per-change prices, mirroring the frozen graph_core bakery path deltas.
CHANGE_PRICES: dict[str, dict[str, float]] = {
    "oven2": {"capex_usd": 18500, "fixed_cost_delta_usd_per_day": 15},
    "hours": {"capex_usd": 0, "fixed_cost_delta_usd_per_day": 35},
    "add_baker": {"capex_usd": 600, "fixed_cost_delta_usd_per_day": 165},
    "retarder_rack": {"capex_usd": 3200, "fixed_cost_delta_usd_per_day": 12},
}

# Path id (frozen graph_core) -> assumption patch the living-world UI
# sends through POST /api/propose. One path = one reversible change.
# Patches are STATE-RELATIVE (next step from current assumptions), so a
# path offered again after an accept means the NEXT oven / baker / rack,
# and the graph preview (+delta) always matches what accept commits.
PATH_ASSUMPTION_PATCHES: dict[str, dict[str, Any]] = {
    "oven2": {"ovens": 2},
    "hours": {"staggered_shift": True, "shift_pattern": "04:30-14:30 staggered"},
    "add_baker": {"bakers": 2},
    "retarder_rack": {"extra_retarder_racks": 1},
}


def next_step_patches(assumptions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Assumption patch for each path, relative to current assumptions.

    oven2 / add_baker / retarder_rack are repeatable (next unit); hours
    is a one-time switch (already-staggered is a no-op patch, and the
    integration layer drops the spent path from the projected graph).
    """
    a = assumptions
    return {
        "oven2": {"ovens": int(a["ovens"]) + 1},
        "hours": {"staggered_shift": True, "shift_pattern": "04:30-14:30 staggered"},
        "add_baker": {"bakers": int(a["bakers"]) + 1},
        "retarder_rack": {"extra_retarder_racks": int(a["extra_retarder_racks"]) + 1},
    }

PATH_LABELS: dict[str, str] = {
    "oven2": "Another oven?",
    "hours": "Adjust shift schedule",
    "add_baker": "Add a second baker",
    "retarder_rack": "Add cold retarder rack",
}


def baseline_assumptions() -> dict[str, Any]:
    return copy.deepcopy(BASELINE_ASSUMPTIONS)


def compute_bakery(assumptions: dict[str, Any]) -> dict[str, Any]:
    """Deterministic capacity / throughput / economics from assumptions."""
    import math
    a = dict(BASELINE_ASSUMPTIONS)
    a.update(assumptions)
    for k in ("ovens", "decks_per_oven", "batch_size_loaves", "cycle_minutes", "bake_window_minutes", "bakers", "loaves_per_baker_per_shift", "proofing_rack_loaves", "demand_loaves_per_day", "shop_capacity_loaves", "schedule_capacity_loaves"):
        v = a.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) <= 0:
            raise ValueError(f"invalid_bakery_assumption:{k}")
    if int(a.get("extra_retarder_racks", 0)) < 0:
        raise ValueError("invalid_bakery_assumption:extra_retarder_racks")
    batches_per_day = a["bake_window_minutes"] / a["cycle_minutes"]
    oven = (
        int(a["ovens"])
        * int(a["decks_per_oven"])
        * int(a["batch_size_loaves"])
        * batches_per_day
    )
    oven_capacity = int(round(oven))
    staff_capacity = (
        int(a["loaves_per_baker_per_shift"])
        + (int(a["bakers"]) - 1) * int(a["extra_baker_loaves"])
        + (int(a["staggered_shift_bonus_loaves"]) if a.get("staggered_shift") else 0)
    )
    ingredient_capacity = int(a["proofing_rack_loaves"]) + int(
        a["extra_retarder_racks"]
    ) * int(a["retarder_rack_loaves"])
    capacities = {
        "wish": int(a["wish_capacity_loaves"]),
        "demand": int(a["demand_loaves_per_day"]),
        "ingredients": ingredient_capacity,
        "staff": staff_capacity,
        "oven": oven_capacity,
        "schedule": int(a["schedule_capacity_loaves"]),
        "shop": int(a["shop_capacity_loaves"]),
        "scenario": int(a["scenario_capacity_loaves"]),
    }
    bottleneck_id = min(capacities, key=lambda k: capacities[k])
    throughput = capacities[bottleneck_id]
    fixed_cost = (
        float(a["fixed_cost_usd_per_day"])
        + (int(a["ovens"]) - 1) * CHANGE_PRICES["oven2"]["fixed_cost_delta_usd_per_day"]
        + (CHANGE_PRICES["hours"]["fixed_cost_delta_usd_per_day"] if a.get("staggered_shift") else 0)
        + (int(a["bakers"]) - 1) * CHANGE_PRICES["add_baker"]["fixed_cost_delta_usd_per_day"]
        + int(a["extra_retarder_racks"]) * CHANGE_PRICES["retarder_rack"]["fixed_cost_delta_usd_per_day"]
    )
    capex = (
        (int(a["ovens"]) - 1) * CHANGE_PRICES["oven2"]["capex_usd"]
        + (int(a["bakers"]) - 1) * CHANGE_PRICES["add_baker"]["capex_usd"]
        + int(a["extra_retarder_racks"]) * CHANGE_PRICES["retarder_rack"]["capex_usd"]
    )
    margin = float(a["margin_per_loaf_usd"])
    net_daily = round(throughput * margin - fixed_cost)
    unc = float(a["uncertainty_pct"]) / 100.0
    throughput_low = round(throughput * (1 - unc))
    throughput_high = round(throughput * (1 + unc))
    return {
        "capacities": capacities,
        "oven_batches_per_day": batches_per_day,
        "oven_capacity": oven_capacity,
        "staff_capacity": staff_capacity,
        "ingredient_capacity": ingredient_capacity,
        "throughput_loaves_per_day": throughput,
        "bottleneck_id": bottleneck_id,
        "bottleneck_label": bottleneck_id.capitalize(),
        "margin_per_loaf_usd": margin,
        "fixed_cost_usd_per_day": fixed_cost,
        "capex_usd": capex,
        "net_daily_usd": net_daily,
        "uncertainty_pct": a["uncertainty_pct"],
        "throughput_band_loaves_per_day": [throughput_low, throughput_high],
        "net_daily_band_usd": [
            round(throughput_low * margin - fixed_cost),
            round(throughput_high * margin - fixed_cost),
        ],
        "unit": "loaves/day",
    }


def new_bakery_record(assumptions: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full bakery record stored in accepted state: assumptions + computed."""
    a = baseline_assumptions()
    if assumptions:
        a.update(assumptions)
    return {
        "assumptions": a,
        "computed": compute_bakery(a),
        "paths": {
            pid: {
                "label": PATH_LABELS[pid],
                "assumption_patch": patch,
                "capex_usd": CHANGE_PRICES[pid]["capex_usd"],
                "fixed_cost_delta_usd_per_day": CHANGE_PRICES[pid][
                    "fixed_cost_delta_usd_per_day"
                ],
            }
            # Next-step patches from THESE assumptions, so the stored
            # record never offers a step that is already applied.
            for pid, patch in next_step_patches(a).items()
        },
        "notes": (
            "Computed capacity/cost/throughput from stated assumptions only. "
            "No customer behaviour, demand forecast, or savings invented. "
            "Uncertainty band is +/-7% around throughput."
        ),
    }


def apply_path(assumptions: dict[str, Any], path_id: str) -> dict[str, Any]:
    """Assumptions after applying one graph path (reversible until accepted)."""
    if path_id not in PATH_ASSUMPTION_PATCHES:
        raise ValueError(f"unknown_bakery_path:{path_id}")
    new = copy.deepcopy(assumptions)
    new.update(PATH_ASSUMPTION_PATCHES[path_id])
    return new


def recompute_bakery_state(state: dict[str, Any]) -> dict[str, Any]:
    """Recompute the bakery record inside a candidate/accepted state dict.

    Returns the same dict (mutated). No-op when the state has no bakery
    record, so non-bakery projects pass through untouched.
    """
    bakery = state.get("bakery")
    if not isinstance(bakery, dict) or "assumptions" not in bakery:
        return state
    record = new_bakery_record(bakery["assumptions"])
    state["bakery"] = record
    return state


def is_bakery_prompt(prompt: str) -> bool:
    low = prompt.lower()
    return "baker" in low or "bakery" in low


def bakery_state_fields() -> list[dict[str, str]]:
    """Field descriptors for a bakery project state.

    The generic artifact verifier requires a non-empty ``fields`` list
    for non-fixture families; these describe the operating assumptions
    the bakery record carries, so a bakery project verifies.
    """
    return [
        {"key": "ovens", "label": "Deck ovens", "type": "number"},
        {"key": "batch_size_loaves", "label": "Loaves per batch", "type": "number"},
        {"key": "cycle_minutes", "label": "Bake cycle (minutes)", "type": "number"},
        {"key": "bakers", "label": "Bakers on shift", "type": "number"},
        {"key": "proofing_rack_loaves", "label": "Proofing rack (loaves/day)", "type": "number"},
        {"key": "demand_loaves_per_day", "label": "Stated demand (loaves/day)", "type": "number"},
        {"key": "margin_per_loaf_usd", "label": "Margin per loaf (USD)", "type": "number"},
        {"key": "fixed_cost_usd_per_day", "label": "Fixed cost (USD/day)", "type": "number"},
    ]
