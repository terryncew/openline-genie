#!/usr/bin/env python3
"""Community Garden Crop Rotation, Drip Cistern & Volunteer Operating Model (`core/community_garden.py`).

Provides a genuinely unrelated, unfamiliar second customer domain alongside
the Hearth & Crumb Bakery model (`core/bakery.py`).

Models a neighborhood community garden with:
- 4 crop-rotation families (`legume`, `solanaceae`, `brassica`, `root`) across beds,
- Weekly irrigation supply (`cistern_gallons_per_week`, baseline 420 gal/wk, 4.0 gal/lb water demand -> 105 lbs/wk),
- Volunteer labor capacity (`volunteer_hours_per_week`, baseline 18 hrs/wk * 7.5 lbs/hr -> 135 lbs/wk),
- Raised-bed soil & plot capacity (`plot_beds_count`, baseline 12 beds * 12.5 lbs/bed -> 150 lbs/wk),
- Harvest shed & cold-wash station capacity (`wash_station_capacity_lbs`, baseline 180 lbs/wk),
- Neighborhood pantry & member demand (`member_demand_lbs_per_week`, baseline 200 lbs/wk).

Binding constraint arithmetic:
- Weekly harvest output (lbs/wk) = min(water_capacity_lbs, volunteer_capacity_lbs, plot_capacity_lbs, wash_capacity_lbs, demand_lbs).
- Baseline: min(105 [water], 135 [volunteers], 150 [plots], 180 [wash], 200 [demand]) = 105 lbs/wk (Watering / Cistern is the binding constraint).
- Counterfactual options include:
  1. `drip_mulch` (OpenLine Discovery: Drip emitters + straw mulch moisture retention + legume nitrogen rotation):
     cuts water needed per lb from 4.0 to 2.625 gal/lb (effective water capacity 160 lbs/wk), shifting the binding constraint to `volunteers` (135 lbs/wk, +30 lbs/wk gain, $280 CapEx, $0/wk operating cost).
  2. `municipal_tap` (Competent Conventional Comparator: Municipal metered hose timer):
     adds +120 gal/wk municipal water (total 540 gal/wk -> 135 lbs/wk water capacity), also reaching 135 lbs/wk (+30 lbs/wk gain, $0 CapEx, +$18/wk utility water bill).
  3. `weekend_workday` (Volunteer shift expansion: +4 hrs/wk -> 165 lbs/wk volunteer capacity):
     alone yields +0 lbs/wk (clamped trap while water is capped at 105 lbs/wk!), but combined with `drip_mulch` unlocks 150 lbs/wk (+45 lbs/wk super-additive synergy, shifting the next ceiling to `plots`).
  4. `extra_beds` (+4 raised beds -> 200 lbs/wk plot capacity):
     unlocks 165 lbs/wk once both `drip_mulch` and `weekend_workday` are active.
"""
from __future__ import annotations

import copy
from typing import Any

GARDEN_BASELINE_ASSUMPTIONS: dict[str, Any] = {
    "cistern_gallons_per_week": 420,
    "municipal_supp_gallons_per_week": 0,
    "gallons_per_lb_produce": 4.0,
    "drip_mulch_enabled": False,
    "volunteer_hours_per_week": 18,
    "lbs_per_volunteer_hour": 7.5,
    "plot_beds_count": 12,
    "lbs_per_bed_per_week": 12.5,
    "legume_rotation_coverage_pct": 25,
    "wash_station_capacity_lbs": 180,
    "member_demand_lbs_per_week": 200,
    "produce_value_usd_per_lb": 3.50,
    "weekly_operating_cost_usd": 45.0,
    "uncertainty_pct": 8,
}

GARDEN_CHANGE_PRICES: dict[str, dict[str, float]] = {
    "drip_mulch": {"capex_usd": 280.0, "weekly_cost_delta_usd": 0.0},
    "municipal_tap": {"capex_usd": 0.0, "weekly_cost_delta_usd": 18.0},
    "weekend_workday": {"capex_usd": 60.0, "weekly_cost_delta_usd": 8.0},
    "extra_beds": {"capex_usd": 640.0, "weekly_cost_delta_usd": 10.0},
}

GARDEN_PATH_LABELS: dict[str, str] = {
    "drip_mulch": "Install drip headers + mulch & legume rotation (Discovery)",
    "municipal_tap": "Add metered municipal hose timer (Conventional)",
    "weekend_workday": "Add Saturday 4-hr volunteer shift",
    "extra_beds": "Build 4 additional raised beds",
}


def garden_baseline_assumptions() -> dict[str, Any]:
    return copy.deepcopy(GARDEN_BASELINE_ASSUMPTIONS)


def garden_next_step_patches(assumptions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    a = assumptions
    return {
        "drip_mulch": {
            "drip_mulch_enabled": True,
            "gallons_per_lb_produce": 2.625,
            "legume_rotation_coverage_pct": 50,
        },
        "municipal_tap": {
            "municipal_supp_gallons_per_week": int(a.get("municipal_supp_gallons_per_week", 0)) + 120,
        },
        "weekend_workday": {
            "volunteer_hours_per_week": int(a.get("volunteer_hours_per_week", 18)) + 4,
        },
        "extra_beds": {
            "plot_beds_count": int(a.get("plot_beds_count", 12)) + 4,
        },
    }


def compute_garden(assumptions: dict[str, Any]) -> dict[str, Any]:
    import math
    a = dict(GARDEN_BASELINE_ASSUMPTIONS)
    a.update(assumptions)
    for k in ("cistern_gallons_per_week", "volunteer_hours_per_week", "lbs_per_volunteer_hour", "plot_beds_count", "lbs_per_bed_per_week", "wash_station_capacity_lbs", "member_demand_lbs_per_week"):
        v = a.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) <= 0:
            raise ValueError(f"invalid_garden_assumption:{k}")
    if float(a.get("municipal_supp_gallons_per_week", 0)) < 0:
        raise ValueError("invalid_garden_assumption:municipal_supp_gallons_per_week")

    total_water_gal = float(a["cistern_gallons_per_week"]) + float(a.get("municipal_supp_gallons_per_week", 0))
    gal_per_lb = 2.625 if a.get("drip_mulch_enabled") else float(a.get("gallons_per_lb_produce", 4.0))
    if gal_per_lb <= 0:
        raise ValueError("invalid_gallons_per_lb_produce")

    water_cap = int(round(total_water_gal / gal_per_lb))
    volunteer_cap = int(round(float(a["volunteer_hours_per_week"]) * float(a["lbs_per_volunteer_hour"])))
    plot_cap = int(round(float(a["plot_beds_count"]) * float(a["lbs_per_bed_per_week"])))
    wash_cap = int(a["wash_station_capacity_lbs"])
    demand_cap = int(a["member_demand_lbs_per_week"])

    capacities = {
        "water": water_cap,
        "volunteers": volunteer_cap,
        "plots": plot_cap,
        "wash_station": wash_cap,
        "demand": demand_cap,
    }
    bottleneck_id = min(capacities, key=lambda k: capacities[k])
    throughput_lbs = capacities[bottleneck_id]

    extra_muni_units = max(0, int(round(float(a.get("municipal_supp_gallons_per_week", 0)) / 120.0)))
    extra_vol_units = max(0, int(round((float(a["volunteer_hours_per_week"]) - 18.0) / 4.0)))
    extra_bed_units = max(0, int(round((float(a["plot_beds_count"]) - 12.0) / 4.0)))

    weekly_cost = (
        float(a["weekly_operating_cost_usd"])
        + (GARDEN_CHANGE_PRICES["drip_mulch"]["weekly_cost_delta_usd"] if a.get("drip_mulch_enabled") else 0.0)
        + extra_muni_units * GARDEN_CHANGE_PRICES["municipal_tap"]["weekly_cost_delta_usd"]
        + extra_vol_units * GARDEN_CHANGE_PRICES["weekend_workday"]["weekly_cost_delta_usd"]
        + extra_bed_units * GARDEN_CHANGE_PRICES["extra_beds"]["weekly_cost_delta_usd"]
    )
    capex = (
        (GARDEN_CHANGE_PRICES["drip_mulch"]["capex_usd"] if a.get("drip_mulch_enabled") else 0.0)
        + extra_muni_units * GARDEN_CHANGE_PRICES["municipal_tap"]["capex_usd"]
        + extra_vol_units * GARDEN_CHANGE_PRICES["weekend_workday"]["capex_usd"]
        + extra_bed_units * GARDEN_CHANGE_PRICES["extra_beds"]["capex_usd"]
    )
    val_per_lb = float(a["produce_value_usd_per_lb"])
    net_weekly_value = round(throughput_lbs * val_per_lb - weekly_cost, 2)
    unc = float(a["uncertainty_pct"]) / 100.0
    low_lbs = round(throughput_lbs * (1.0 - unc))
    high_lbs = round(throughput_lbs * (1.0 + unc))

    sorted_caps = sorted(capacities.items(), key=lambda kv: kv[1])
    next_ceiling_id = sorted_caps[1][0] if len(sorted_caps) > 1 else bottleneck_id
    third_ceiling_id = sorted_caps[2][0] if len(sorted_caps) > 2 else next_ceiling_id

    return {
        "capacities": capacities,
        "water_capacity_lbs_per_week": water_cap,
        "volunteer_capacity_lbs_per_week": volunteer_cap,
        "plot_capacity_lbs_per_week": plot_cap,
        "throughput_lbs_per_week": throughput_lbs,
        "bottleneck_id": bottleneck_id,
        "bottleneck_label": bottleneck_id.replace("_", " ").title(),
        "next_ceiling_id": next_ceiling_id,
        "third_ceiling_id": third_ceiling_id,
        "weekly_operating_cost_usd": round(weekly_cost, 2),
        "capex_usd": round(capex, 2),
        "net_weekly_community_value_usd": net_weekly_value,
        "uncertainty_pct": a["uncertainty_pct"],
        "throughput_band_lbs_per_week": [low_lbs, high_lbs],
        "unit": "lbs/week",
    }


def new_garden_record(assumptions: dict[str, Any] | None = None) -> dict[str, Any]:
    a = garden_baseline_assumptions()
    if assumptions:
        a.update(assumptions)
    comp = compute_garden(a)
    patches = garden_next_step_patches(a)
    paths: dict[str, Any] = {}
    for pid, patch in patches.items():
        cand_a = copy.deepcopy(a)
        cand_a.update(patch)
        cand_c = compute_garden(cand_a)
        delta_lbs = cand_c["throughput_lbs_per_week"] - comp["throughput_lbs_per_week"]
        paths[pid] = {
            "label": GARDEN_PATH_LABELS[pid],
            "assumption_patch": patch,
            "capex_usd": GARDEN_CHANGE_PRICES[pid]["capex_usd"],
            "weekly_cost_delta_usd": GARDEN_CHANGE_PRICES[pid]["weekly_cost_delta_usd"],
            "expected_throughput_lbs_per_week": cand_c["throughput_lbs_per_week"],
            "expected_delta_lbs_per_week": delta_lbs,
            "next_bottleneck_id": cand_c["bottleneck_id"],
            "is_conventional_comparator": (pid == "municipal_tap"),
            "is_clamped_trap": (delta_lbs == 0),
        }
    return {
        "assumptions": a,
        "computed": comp,
        "paths": paths,
        "notes": (
            "Deterministic crop-rotation, drip-cistern water balance, and volunteer labor capacity model. "
            "Compares OpenLine drip+mulch+legume rotation discovery against conventional municipal tap expansion."
        ),
    }


def recompute_garden_state(state: dict[str, Any]) -> dict[str, Any]:
    garden = state.get("garden")
    if not isinstance(garden, dict) or "assumptions" not in garden:
        return state
    record = new_garden_record(garden["assumptions"])
    state["garden"] = record
    comp = record["computed"]
    state["constraints"] = {
        "binding_constraint_id": comp["bottleneck_id"],
        "binding_constraint_label": comp["bottleneck_label"],
        "plain_language_diagnosis": (
            f"{comp['bottleneck_label']} ({comp['throughput_lbs_per_week']} lbs/week) is the current binding constraint. "
            f"Next ceiling is {comp['next_ceiling_id']} ({comp['capacities'][comp['next_ceiling_id']]} lbs/week)."
        ),
        "capacities": comp["capacities"],
        "options_compared": record["paths"],
    }
    return state


def is_garden_prompt(prompt: str) -> bool:
    low = prompt.lower()
    return any(k in low for k in ("garden", "crop rotation", "harvest", "plot assignment", "compost", "volunteer"))
