"""Sub-package thermodynamic constants and Van 't Hoff osmotic pressure model (`upstream/subpkg/brine_thermodynamics.py`).

Used as a Depth-2 transitive engineering dependency by `upstream/ro_membrane_physics.py`
and `upstream/ro_desalination_hub.py`.
"""
from __future__ import annotations

# Standard brackish feedwater osmotic & fouling parameters (25 C)
VAN_T_HOFF_OSMOTIC_COEFF_BAR_PER_G_L: float = 0.78
BIOFOULING_RESISTANCE_MULTIPLIER: float = 1.00
PUMP_SPECIFIC_ENERGY_KWH_PER_M3_BAR: float = 0.036


def compute_osmotic_backpressure_bar(tds_g_per_l: float, recovery_fraction: float) -> float:
    """Compute concentrate-side osmotic backpressure (bar) across RO stage."""
    conc_factor = 1.0 / max(0.15, 1.0 - recovery_fraction)
    return round(tds_g_per_l * VAN_T_HOFF_OSMOTIC_COEFF_BAR_PER_G_L * conc_factor * BIOFOULING_RESISTANCE_MULTIPLIER, 4)


def compute_pump_power_kw(feed_flow_m3_hr: float, applied_pressure_bar: float) -> float:
    """Compute high-pressure RO pump shaft power demand (kW)."""
    return round(feed_flow_m3_hr * applied_pressure_bar * PUMP_SPECIFIC_ENERGY_KWH_PER_M3_BAR, 4)
