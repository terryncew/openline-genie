"""Solar-Direct Brackish Reverse-Osmosis (RO) Desalination Microgrid Hub (`upstream/ro_desalination_hub.py`).

Real multi-constraint OpenLine engineering domain model with a 2-level transitive import chain:
  `upstream/ro_desalination_hub.py` -> `upstream/ro_membrane_physics.py` -> `upstream/subpkg/brine_thermodynamics.py`

Models hourly potable permeate output (`L/hr`) across 5 coupled physical capacities:
  1. `membrane`: Spiral-wound RO pressure vessels (`ro_vessels_count`, `applied_pressure_bar`, `feed_tds_g_per_l`)
  2. `high_pressure_pump`: VFD high-pressure pump kW envelope (`pump_power_kw_limit`)
  3. `remineralization`: Calcite contactor & UV post-treatment flow ceiling (`remin_uv_capacity_l_hr`)
  4. `permeate_storage`: Buffer tank dispatch ceiling (`storage_buffer_l_hr`)
  5. `demand`: Community clinic & potable distribution demand (`potable_demand_l_hr`)
"""
from __future__ import annotations

import copy
import math
from typing import Any

from upstream.ro_membrane_physics import (
    compute_membrane_permeate_l_hr,
    compute_pump_limited_permeate_l_hr,
)

RO_BASELINE_ASSUMPTIONS: dict[str, Any] = {
    "ro_vessels_count": 3,
    "applied_pressure_bar": 15.5,
    "feed_tds_g_per_l": 4.2,
    "recovery_fraction": 0.60,
    "antiscalant_dosing_active": False,
    "pump_power_kw_limit": 7.5,
    "remin_uv_capacity_l_hr": 3400,
    "storage_buffer_l_hr": 3800,
    "potable_demand_l_hr": 4000,
    "water_value_usd_per_1000l": 4.50,
    "daily_operating_cost_usd": 62.0,
    "uncertainty_pct": 6,
}

RO_CHANGE_PRICES: dict[str, dict[str, float]] = {
    "add_ro_vessel": {"capex_usd": 1400.0, "daily_cost_delta_usd": 6.0},
    "boost_vfd_pump": {"capex_usd": 950.0, "daily_cost_delta_usd": 14.0},
    "enable_antiscalant": {"capex_usd": 420.0, "daily_cost_delta_usd": 4.5},
    "expand_remin_uv": {"capex_usd": 800.0, "daily_cost_delta_usd": 3.5},
}


def ro_baseline_assumptions() -> dict[str, Any]:
    return copy.deepcopy(RO_BASELINE_ASSUMPTIONS)


def ro_next_step_patches(assumptions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    a = assumptions
    return {
        "add_ro_vessel": {
            "ro_vessels_count": int(a.get("ro_vessels_count", 3)) + 1,
        },
        "boost_vfd_pump": {
            "pump_power_kw_limit": round(float(a.get("pump_power_kw_limit", 7.5)) + 1.8, 4),
            "applied_pressure_bar": round(float(a.get("applied_pressure_bar", 15.5)) + 1.2, 4),
        },
        "enable_antiscalant": {
            "antiscalant_dosing_active": True,
        },
        "expand_remin_uv": {
            "remin_uv_capacity_l_hr": int(a.get("remin_uv_capacity_l_hr", 3400)) + 600,
        },
    }


def compute_ro_desalination(assumptions: dict[str, Any]) -> dict[str, Any]:
    a = dict(RO_BASELINE_ASSUMPTIONS)
    a.update(assumptions)
    for k in (
        "ro_vessels_count",
        "applied_pressure_bar",
        "feed_tds_g_per_l",
        "recovery_fraction",
        "pump_power_kw_limit",
        "remin_uv_capacity_l_hr",
        "storage_buffer_l_hr",
        "potable_demand_l_hr",
    ):
        v = a.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) <= 0:
            raise ValueError(f"invalid_ro_assumption:{k}")

    mem_cap = compute_membrane_permeate_l_hr(
        int(a["ro_vessels_count"]),
        float(a["applied_pressure_bar"]),
        float(a["feed_tds_g_per_l"]),
        float(a["recovery_fraction"]),
        bool(a.get("antiscalant_dosing_active", False)),
    )
    pump_cap = compute_pump_limited_permeate_l_hr(
        float(a["pump_power_kw_limit"]),
        float(a["applied_pressure_bar"]),
        float(a["recovery_fraction"]),
    )
    remin_cap = int(a["remin_uv_capacity_l_hr"])
    storage_cap = int(a["storage_buffer_l_hr"])
    demand_cap = int(a["potable_demand_l_hr"])

    capacities = {
        "membrane": mem_cap,
        "high_pressure_pump": pump_cap,
        "remineralization": remin_cap,
        "storage": storage_cap,
        "demand": demand_cap,
    }
    bottleneck_id = min(capacities, key=lambda k: capacities[k])
    throughput_l_hr = capacities[bottleneck_id]

    extra_vessels = max(0, int(a["ro_vessels_count"]) - 3)
    extra_pump_steps = max(0, int(round((float(a["pump_power_kw_limit"]) - 7.5) / 1.8)))
    extra_remin_steps = max(0, int(round((float(a["remin_uv_capacity_l_hr"]) - 3400.0) / 600.0)))
    anti_active = 1 if a.get("antiscalant_dosing_active") else 0

    capex = (
        extra_vessels * RO_CHANGE_PRICES["add_ro_vessel"]["capex_usd"]
        + extra_pump_steps * RO_CHANGE_PRICES["boost_vfd_pump"]["capex_usd"]
        + anti_active * RO_CHANGE_PRICES["enable_antiscalant"]["capex_usd"]
        + extra_remin_steps * RO_CHANGE_PRICES["expand_remin_uv"]["capex_usd"]
    )
    daily_cost = (
        float(a["daily_operating_cost_usd"])
        + extra_vessels * RO_CHANGE_PRICES["add_ro_vessel"]["daily_cost_delta_usd"]
        + extra_pump_steps * RO_CHANGE_PRICES["boost_vfd_pump"]["daily_cost_delta_usd"]
        + anti_active * RO_CHANGE_PRICES["enable_antiscalant"]["daily_cost_delta_usd"]
        + extra_remin_steps * RO_CHANGE_PRICES["expand_remin_uv"]["daily_cost_delta_usd"]
    )

    return {
        "capacities": capacities,
        "throughput_l_per_hr": throughput_l_hr,
        "bottleneck_id": bottleneck_id,
        "bottleneck_label": bottleneck_id.replace("_", " ").title(),
        "capex_usd": round(capex, 2),
        "daily_operating_cost_usd": round(daily_cost, 2),
        "unit": "L/hr",
    }
