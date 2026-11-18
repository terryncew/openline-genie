"""Reverse-Osmosis (RO) spiral-wound membrane transport physics (`upstream/ro_membrane_physics.py`).

Imports Depth-2 thermodynamic helper `upstream.subpkg.brine_thermodynamics` and provides
permeate flux and pump-head calculations to `upstream/ro_desalination_hub.py`.
"""
from __future__ import annotations

from upstream.subpkg.brine_thermodynamics import (
    BIOFOULING_RESISTANCE_MULTIPLIER,
    compute_osmotic_backpressure_bar,
    compute_pump_power_kw,
)

# Membrane water permeability A (L / (m^2 * hr * bar)) for brackish low-energy polyamide elements
MEMBRANE_PERMEABILITY_L_M2_HR_BAR: float = 4.25
ACTIVE_AREA_PER_VESSEL_M2: float = 37.0


def compute_membrane_permeate_l_hr(
    vessels_count: int,
    applied_pressure_bar: float,
    feed_tds_g_per_l: float,
    recovery_fraction: float,
    antiscalant_dosing_active: bool = False,
) -> int:
    """Compute net RO membrane permeate production (L/hr) from transmembrane net driving pressure."""
    osm_bar = compute_osmotic_backpressure_bar(feed_tds_g_per_l, recovery_fraction)
    scaling_penalty = 0.88 if not antiscalant_dosing_active and recovery_fraction > 0.55 else 1.00
    net_driving_bar = max(0.0, applied_pressure_bar - osm_bar)
    eff_permeability = (MEMBRANE_PERMEABILITY_L_M2_HR_BAR * scaling_penalty) / max(0.1, BIOFOULING_RESISTANCE_MULTIPLIER)
    flux_l_hr = vessels_count * ACTIVE_AREA_PER_VESSEL_M2 * eff_permeability * net_driving_bar
    return int(round(flux_l_hr))


def compute_pump_limited_permeate_l_hr(
    pump_power_budget_kw: float,
    applied_pressure_bar: float,
    recovery_fraction: float,
) -> int:
    """Compute maximum permeate production (L/hr) supported by high-pressure pump power ceiling."""
    unit_kw_per_m3_hr = compute_pump_power_kw(1.0, applied_pressure_bar)
    if unit_kw_per_m3_hr <= 0:
        return 0
    max_feed_m3_hr = pump_power_budget_kw / unit_kw_per_m3_hr
    return int(round(max_feed_m3_hr * recovery_fraction * 1000.0))
