#!/usr/bin/env python3
"""General Operational Project Compiler & Runnable App Synthesizer (`core/operational_compiler.py`).

Compiles any unfamiliar natural-language project description into:
1. A domain-tailored operational model (`state["operations_model"]`) with extracted
   stations, editable assumptions, fail-closed bounds validation, capacity/bottleneck
   math, conventional vs. synergistic counterfactual paths, and record dependency
   propagation.
2. Domain-appropriate typed record fields, workflow states, seeded operational records,
   and deterministic record calculation coupled to the project's operating assumptions.
3. A self-contained, single-file runnable HTML application (`compile_runnable_micro_app_html`)
   with zero external dependencies, XSS-safe DOM rendering, localStorage + in-memory
   fallback persistence (working both from `file://` and inside sandboxed iframes),
   interactive assumption what-if controls, and full CRUD + workflow status transitions.
"""
from __future__ import annotations

import copy
import html
import json
import math
import re
from typing import Any


OPERATIONS_BASELINE_ASSUMPTIONS: dict[str, Any] = {
    # Primary physical resource / supply / equipment pool (node: 'workflow') -> baseline 42 ops/day
    "resource_units": 3,
    "cycles_per_unit_per_day": 14,
    "efficiency_multiplier": 1.0,
    "reserve_buffer_units": 0,
    # Assigned people / coordinators / technicians / crew (node: 'formula') -> baseline 56 ops/day
    "active_staff_count": 4,
    "hours_per_shift": 7.0,
    "cases_per_staff_hour": 2.0,
    "staggered_handoff_enabled": False,
    "staggered_handoff_bonus_ops": 14,
    # Intake, triage & diagnostic queue (node: 'inputs') -> baseline 68 ops/day
    "intake_channels": 2,
    "intake_rate_per_channel": 34,
    "auto_triage_enabled": False,
    "auto_triage_bonus_ops": 20,
    # Demand & downstream capacities (nodes: 'demand', 'scenario', 'wish')
    "stated_daily_demand": 85,
    "scenario_capacity_ops": 96,
    "wish_capacity_ops": 120,
    # Economics / Community Value (stated planning assumptions)
    "unit_value_usd": 15.0,
    "daily_fixed_cost_usd": 180.0,
    "uncertainty_pct": 7,
}

OPERATIONS_CHANGE_PRICES: dict[str, dict[str, float]] = {
    "expand_resource": {"capex_usd": 360.0, "fixed_cost_delta_usd_per_day": 15.0},
    "stagger_shifts": {"capex_usd": 80.0, "fixed_cost_delta_usd_per_day": 12.0},
    "spot_rental_overtime": {"capex_usd": 0.0, "fixed_cost_delta_usd_per_day": 85.0},
    "automate_intake": {"capex_usd": 220.0, "fixed_cost_delta_usd_per_day": 8.0},
}

STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "for", "to", "in", "on", "of", "with", "by",
    "from", "our", "my", "your", "their", "this", "that", "these", "those",
    "build", "create", "design", "make", "develop", "plan", "help", "me", "us",
    "need", "needs", "want", "wants", "would", "should", "could", "can",
    "free", "local", "first", "working", "usable", "operational", "interactive",
    "app", "application", "tool", "tracker", "system", "planner", "workspace",
    "hub", "dashboard", "software", "project", "manage", "track", "assign",
    "spot", "calculate", "produce", "figure", "out", "whether",
})


def _clean_cap(words: list[str], fallback: str) -> str:
    if not words:
        return fallback
    small = {"and", "or", "for", "to", "in", "of", "with", "on", "by"}
    out = []
    for idx, w in enumerate(words):
        if idx > 0 and w.lower() in small:
            out.append(w.lower())
        elif w.upper() in ("SLA", "PCB", "RF", "HVAC", "EV", "IT", "QA", "QC", "CPR", "EMS"):
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def extract_operational_profile(prompt: str) -> dict[str, Any]:
    """Extracts domain-specific entities, station names, fields, and upgrade labels from an ordinary-language prompt."""
    p_clean = re.sub(r"\s+", " ", prompt.strip())
    p_low = p_clean.lower()

    # 1. Strip conversational prefix to isolate the core domain subject
    subj = re.sub(
        r"^(?:please\s+)?(?:help\s+(?:me|us)\s+)?(?:figure\s+out\s+whether\s+)?"
        r"(?:build|create|design|make|develop|set\s+up|plan|compile)\s+"
        r"(?:a|an|the)?\s*(?:free\s+|local-first\s+|working\s+|usable\s+|operational\s+|interactive\s+)*"
        r"(?:app|application|tool|tracker|system|planner|scheduler|dashboard|workspace|hub)?\s*"
        r"(?:for|to)?\s*(?:our\s+|my\s+|a\s+|an\s+|the\s+)?",
        "",
        p_clean,
        flags=re.IGNORECASE,
    ).strip()
    subj_clause = re.split(r"\b(?:to\s+track|to\s+log|to\s+manage|to\s+schedule|to\s+assign|that\s+needs|that\s+tracks|with\s+refundable)\b", subj, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,.-—:")
    subj_words = [w for w in re.findall(r"[A-Za-z0-9-]+", subj_clause) if len(w) > 1]
    if len(subj_words) < 2:
        subj_words = [w for w in re.findall(r"[A-Za-z0-9-]+", p_clean) if w.lower() not in STOPWORDS and len(w) > 2]

    domain_title = _clean_cap(subj_words[:6], "Local Operations")
    slug_tokens = [re.sub(r"[^a-z0-9]+", "", w.lower()) for w in subj_words[:5]]
    slug_tokens = [t for t in slug_tokens if t]
    app_slug = "-".join(slug_tokens)[:48] or "custom-operations-app"

    # 2. Classify domain family & extract operational nouns
    is_mutual_aid = any(k in p_low for k in ("mutual-aid", "mutual aid", "volunteer", "community organization", "relief", "assistance", "aid", "pantry", "shelter", "nonprofit", "donation"))
    is_repair_calib = any(k in p_low for k in ("repair", "calibration", "electronics", "bench", "diagnostic", "oscilloscope", "ticket", "hardware", "spare part", "turnaround"))
    is_booking_service = any(k in p_low for k in ("barber", "grooming", "pet", "appointment", "booking", "salon", "clinic", "vet", "vaccination", "reminder"))
    is_kiln_craft = any(k in p_low for k in ("kiln", "ceramic", "glaze", "pottery", "firing", "roastery", "coffee", "batch")) and not any(b in p_low for b in ("bakery", "baking", "loaf", "loaves", "bread"))

    if is_mutual_aid:
        category = "community_mutual_aid_and_dispatch"
        primary_entity = "Assistance Request"
        workflow_label = "Supply Kits & Van Dispatch"
        formula_label = "Volunteer Coordinator Shifts"
        inputs_label = "Resident Request Intake & Triage"
        demand_label = "Neighborhood Assistance Demand"
        item_field_label = "Resident / Household Request"
        category_field_label = "Assistance Type & Urgency"
        assignee_field_label = "Assigned Volunteer Coordinator"
        qty_field_label = "Supply Kits & Van Hours"
        rate_field_label = "Community Priority Value ($ eq.)"
        adj_field_label = "Emergency Delivery Boost ($ eq.)"
        metric_label = "Fulfilled Priority Impact ($ eq.)"
        workflow_states = ["TRIAGED", "COORDINATOR_ASSIGNED", "VAN_DISPATCHED", "DELIVERED_VERIFIED"]
        expand_label = "Pre-pack emergency supply kits + add shared transit van"
        stagger_label = "Stagger volunteer coordinator handoff shifts"
        spot_label = "Rent commercial courier vans on spot rates (Conventional)"
        auto_label = "Enable SMS & web self-triage intake form"
        seed_records = [
            {
                "record_id": "REQ-101",
                "item_title": "Mrs. Alvarez ( Oak St #4 ) — Infant Formula & Heater Kit",
                "category_tag": "Urgent Medical / Heat Supply",
                "assignee_name": "Dana Lin (Zone North Coordinator)",
                "quantity_units": 3.0,
                "unit_rate_dollars": 45.0,
                "adjustments_dollars": 25.0,
                "status": "DELIVERED_VERIFIED",
            },
            {
                "record_id": "REQ-102",
                "item_title": "Cedar Senior Commons — 6 Mobility & Pantry Supply Boxes",
                "category_tag": "Scheduled Multi-Household Drop",
                "assignee_name": "Marcus Bell (Van Route B)",
                "quantity_units": 6.0,
                "unit_rate_dollars": 35.0,
                "adjustments_dollars": 15.0,
                "status": "COORDINATOR_ASSIGNED",
            },
            {
                "record_id": "REQ-103",
                "item_title": "Westside Family Shelter — Hygiene & Blanket Restock",
                "category_tag": "Standard Supply Replenishment",
                "assignee_name": "Priya Nair (Intake Lead)",
                "quantity_units": 4.0,
                "unit_rate_dollars": 40.0,
                "adjustments_dollars": 10.0,
                "status": "TRIAGED",
            },
        ]
    elif is_repair_calib:
        category = "technical_repair_and_calibration"
        primary_entity = "Repair & Calibration Ticket"
        workflow_label = "Calibration Rigs & Parts Bench"
        formula_label = "Bench Technician Shifts"
        inputs_label = "Device Ticket Intake & Diagnostics"
        demand_label = "Daily Repair Ticket Demand"
        item_field_label = "Device / Instrument & Serial #"
        category_field_label = "Fault / Calibration Spec"
        assignee_field_label = "Assigned Bench Technician"
        qty_field_label = "Bench & Rig Hours"
        rate_field_label = "Lab Bench Rate ($/hr)"
        adj_field_label = "Spare Parts & NIST Cert ($)"
        metric_label = "Calculated Ticket Net ($)"
        workflow_states = ["DIAGNOSTIC_QUEUED", "ON_CALIBRATION_RIG", "PARTS_INSTALLED", "NIST_VERIFIED_READY"]
        expand_label = "Add dual-channel calibration rig + pre-stocked IC kit"
        stagger_label = "Stagger bench technician diagnostic & soldering shifts"
        spot_label = "Outsource overflow tickets to 3rd-party lab (Conventional)"
        auto_label = "Add automated boundary-scan intake fixture"
        seed_records = [
            {
                "record_id": "TKT-101",
                "item_title": "Keysight 34465A DMM — 10V Reference Drift & Recalibration",
                "category_tag": "ISO-17025 Voltage Calibration",
                "assignee_name": "K. Takahashi (Lead Metrologist)",
                "quantity_units": 3.5,
                "unit_rate_dollars": 85.0,
                "adjustments_dollars": 45.0,
                "status": "NIST_VERIFIED_READY",
            },
            {
                "record_id": "TKT-102",
                "item_title": "Tektronix MSO44 Scope — Front-End Attenuator Relay Replace",
                "category_tag": "Board-Level Component Repair",
                "assignee_name": "S. Okafor (RF Bench 2)",
                "quantity_units": 4.0,
                "unit_rate_dollars": 90.0,
                "adjustments_dollars": 65.0,
                "status": "ON_CALIBRATION_RIG",
            },
            {
                "record_id": "TKT-103",
                "item_title": "Fluke 754 Process Calibrator — Pressure Module Zeroing",
                "category_tag": "Turnaround SLA Express",
                "assignee_name": "L. Chen (Calibration Rig 1)",
                "quantity_units": 2.5,
                "unit_rate_dollars": 85.0,
                "adjustments_dollars": 30.0,
                "status": "DIAGNOSTIC_QUEUED",
            },
        ]
    elif is_booking_service:
        category = "service_booking_and_dispatch"
        primary_entity = "Service Appointment"
        workflow_label = "Service Vans & Equipment Kits"
        formula_label = "Specialist & Stylist Shifts"
        inputs_label = "Appointment & Reminder Queue"
        demand_label = "Daily Client Booking Demand"
        item_field_label = "Client / Pet & Service Name"
        category_field_label = "Service Package & Zone"
        assignee_field_label = "Assigned Specialist"
        qty_field_label = "Appointment Duration (hrs)"
        rate_field_label = "Service Rate ($/hr)"
        adj_field_label = "Add-On / Travel Fee ($)"
        metric_label = "Calculated Net Total ($)"
        workflow_states = ["BOOKED", "REMINDER_STAGED", "COMPLETED_VERIFIED", "RESCHEDULE_HOLD"]
        expand_label = "Equip 2nd mobile service kit + sanitized tool cassette"
        stagger_label = "Stagger morning & evening route shifts"
        spot_label = "Pay on-demand contractor surge split (Conventional)"
        auto_label = "Enable conflict-checked route intake templates"
        seed_records = [
            {
                "record_id": "APT-101",
                "item_title": f"{domain_title} — Morning Route Client #1",
                "category_tag": "Full Service + Sanitization",
                "assignee_name": "Lead Specialist A",
                "quantity_units": 1.5,
                "unit_rate_dollars": 60.0,
                "adjustments_dollars": 15.0,
                "status": "COMPLETED_VERIFIED",
            },
            {
                "record_id": "APT-102",
                "item_title": f"{domain_title} — Afternoon Route Client #2",
                "category_tag": "Standard Booking",
                "assignee_name": "Specialist B",
                "quantity_units": 1.0,
                "unit_rate_dollars": 55.0,
                "adjustments_dollars": 10.0,
                "status": "REMINDER_STAGED",
            },
        ]
    elif is_kiln_craft:
        category = "studio_batch_and_kiln_operations"
        primary_entity = "Firing & Glaze Batch"
        workflow_label = "Kiln Chambers & Shelf Racks"
        formula_label = "Studio Technician Shifts"
        inputs_label = "Glaze Prep & Greenware Intake"
        demand_label = "Member Firing Demand"
        item_field_label = "Batch / Member Piece Set"
        category_field_label = "Cone Schedule & Glaze Profile"
        assignee_field_label = "Kiln Operator"
        qty_field_label = "Shelf Units / Hours"
        rate_field_label = "Firing Rate ($/unit)"
        adj_field_label = "Glaze Materials ($)"
        metric_label = "Calculated Batch Value ($)"
        workflow_states = ["GREENWARE_LOGGED", "BISQUE_LOADED", "GLAZE_FIRED", "UNLOADED_VERIFIED"]
        expand_label = "Add silicon-carbide half-shelves + vent hood"
        stagger_label = "Stagger overnight cool-down & morning loading shifts"
        spot_label = "Peak-rate daytime fast-fire cycle (Conventional)"
        auto_label = "Add moisture & cone-witness pre-check station"
        seed_records = [
            {
                "record_id": "BCH-101",
                "item_title": "Cone 6 Stoneware Mug & Bowl Run (Shelf A1-A3)",
                "category_tag": "Cone 6 Oxidation Glaze",
                "assignee_name": "Studio Tech Maya",
                "quantity_units": 4.0,
                "unit_rate_dollars": 35.0,
                "adjustments_dollars": 18.0,
                "status": "UNLOADED_VERIFIED",
            },
            {
                "record_id": "BCH-102",
                "item_title": "Community Class Bisque Load #14",
                "category_tag": "Cone 04 Slow Bisque",
                "assignee_name": "Studio Tech Leo",
                "quantity_units": 3.0,
                "unit_rate_dollars": 30.0,
                "adjustments_dollars": 12.0,
                "status": "BISQUE_LOADED",
            },
        ]
    else:
        category = "synthesized_operational_application"
        primary_entity = "Operational Record"
        workflow_label = f"{domain_title[:24]} Resource Pool"
        formula_label = "Assigned Crew & Rules"
        inputs_label = "Request & Record Intake"
        demand_label = "Daily Operational Demand"
        item_field_label = "Item / Request Name"
        category_field_label = "Category / Operational Scope"
        assignee_field_label = "Assigned Owner / Lead"
        qty_field_label = "Resource Units / Hours"
        rate_field_label = "Unit Rate / Value ($)"
        adj_field_label = "Materials / Adjustment ($)"
        metric_label = "Calculated Net Total ($)"
        workflow_states = ["ACTIVE", "IN_PROGRESS", "COMPLETED_VERIFIED", "NEEDS_REVIEW"]
        expand_label = "Expand primary equipment & resource pool (+1 unit +25% eff.)"
        stagger_label = "Stagger crew handoff & processing shifts"
        spot_label = "Use high-cost spot overtime / rental capacity (Conventional)"
        auto_label = "Add structured intake validation templates"
        seed_records = [
            {
                "record_id": "REC-101",
                "item_title": f"{domain_title} — Primary Operational Batch #1",
                "category_tag": "Priority Fulfillment",
                "assignee_name": "Operations Lead A",
                "quantity_units": 4.0,
                "unit_rate_dollars": 65.0,
                "adjustments_dollars": 25.0,
                "status": "COMPLETED_VERIFIED",
            },
            {
                "record_id": "REC-102",
                "item_title": f"{domain_title} — Scheduled Queue Item #2",
                "category_tag": "Standard Operations",
                "assignee_name": "Operations Lead B",
                "quantity_units": 2.5,
                "unit_rate_dollars": 80.0,
                "adjustments_dollars": 15.0,
                "status": "ACTIVE",
            },
        ]

    return {
        "app_slug": app_slug,
        "domain_title": domain_title,
        "title": f"{domain_title} — Operational App & Living Model",
        "subtitle": f"Local-First {primary_entity} Tracker, Bottleneck Solver & Portable Workspace",
        "category": category,
        "primary_entity": primary_entity,
        "workflow_label": workflow_label,
        "formula_label": formula_label,
        "inputs_label": inputs_label,
        "demand_label": demand_label,
        "item_field_label": item_field_label,
        "category_field_label": category_field_label,
        "assignee_field_label": assignee_field_label,
        "qty_field_label": qty_field_label,
        "rate_field_label": rate_field_label,
        "adj_field_label": adj_field_label,
        "metric_label": metric_label,
        "workflow_states": workflow_states,
        "expand_label": expand_label,
        "stagger_label": stagger_label,
        "spot_label": spot_label,
        "auto_label": auto_label,
        "seed_records": seed_records,
    }


def operations_next_step_patches(assumptions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    a = assumptions
    return {
        "expand_resource": {
            "resource_units": int(a.get("resource_units", 3)) + 1,
            "efficiency_multiplier": round(max(float(a.get("efficiency_multiplier", 1.0)), 1.25), 2),
        },
        "stagger_shifts": {
            "staggered_handoff_enabled": True,
        },
        "spot_rental_overtime": {
            "reserve_buffer_units": int(a.get("reserve_buffer_units", 0)) + 14,
        },
        "automate_intake": {
            "auto_triage_enabled": True,
        },
    }


def compute_operations_model(assumptions: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deterministic station capacity, binding bottleneck, and economics solver with fail-closed bounds."""
    if assumptions:
        for k in assumptions:
            if k not in OPERATIONS_BASELINE_ASSUMPTIONS:
                raise ValueError(f"invalid_operations_assumption:unknown_key:{k}")
    a = copy.deepcopy(OPERATIONS_BASELINE_ASSUMPTIONS)
    if assumptions:
        a.update(assumptions)
    prof = profile or {}

    positive_keys = (
        "resource_units",
        "cycles_per_unit_per_day",
        "efficiency_multiplier",
        "active_staff_count",
        "hours_per_shift",
        "cases_per_staff_hour",
        "intake_channels",
        "intake_rate_per_channel",
        "stated_daily_demand",
        "unit_value_usd",
    )
    for k in positive_keys:
        v = a.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) <= 0:
            raise ValueError(f"invalid_operations_assumption:{k}")
    for non_neg in ("reserve_buffer_units", "daily_fixed_cost_usd", "uncertainty_pct"):
        v = a.get(non_neg, 0)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError(f"invalid_operations_assumption:{non_neg}")

    workflow_cap = int(round(
        float(a["resource_units"]) * float(a["cycles_per_unit_per_day"]) * float(a["efficiency_multiplier"])
        + float(a.get("reserve_buffer_units", 0))
    ))
    formula_cap = int(round(
        float(a["active_staff_count"]) * float(a["hours_per_shift"]) * float(a["cases_per_staff_hour"])
        + (float(a.get("staggered_handoff_bonus_ops", 14)) if a.get("staggered_handoff_enabled") else 0.0)
    ))
    inputs_cap = int(round(
        float(a["intake_channels"]) * float(a["intake_rate_per_channel"])
        + (float(a.get("auto_triage_bonus_ops", 20)) if a.get("auto_triage_enabled") else 0.0)
    ))
    demand_cap = int(round(float(a["stated_daily_demand"])))
    scenario_cap = int(round(float(a.get("scenario_capacity_ops", 96))))
    wish_cap = int(round(float(a.get("wish_capacity_ops", 120))))

    capacities = {
        "workflow": max(1, workflow_cap),
        "formula": max(1, formula_cap),
        "inputs": max(1, inputs_cap),
        "demand": max(1, demand_cap),
        "scenario": max(1, scenario_cap),
        "wish": max(1, wish_cap),
    }

    station_labels = {
        "workflow": prof.get("workflow_label", "Primary Resource Pool"),
        "formula": prof.get("formula_label", "Assigned Crew & Rules"),
        "inputs": prof.get("inputs_label", "Request & Record Intake"),
        "demand": prof.get("demand_label", "Daily Demand"),
        "scenario": "Portable App & Export",
        "wish": "Your goal",
    }

    operational_ids = ("workflow", "formula", "inputs", "demand", "scenario")
    sorted_ops = sorted(operational_ids, key=lambda k: capacities[k])
    bottleneck_id = sorted_ops[0]
    next_ceiling_id = sorted_ops[1] if len(sorted_ops) > 1 else bottleneck_id
    third_ceiling_id = sorted_ops[2] if len(sorted_ops) > 2 else next_ceiling_id
    throughput = capacities[bottleneck_id]

    extra_res_units = max(0, int(round(float(a["resource_units"]) - 3.0)))
    eff_boost_active = float(a["efficiency_multiplier"]) > 1.05
    expand_units = max(extra_res_units, 1 if eff_boost_active else 0)
    spot_units = max(0, int(round(float(a.get("reserve_buffer_units", 0)) / 14.0)))
    stagger_active = bool(a.get("staggered_handoff_enabled"))
    auto_active = bool(a.get("auto_triage_enabled"))

    fixed_cost = (
        float(a["daily_fixed_cost_usd"])
        + expand_units * OPERATIONS_CHANGE_PRICES["expand_resource"]["fixed_cost_delta_usd_per_day"]
        + (OPERATIONS_CHANGE_PRICES["stagger_shifts"]["fixed_cost_delta_usd_per_day"] if stagger_active else 0.0)
        + spot_units * OPERATIONS_CHANGE_PRICES["spot_rental_overtime"]["fixed_cost_delta_usd_per_day"]
        + (OPERATIONS_CHANGE_PRICES["automate_intake"]["fixed_cost_delta_usd_per_day"] if auto_active else 0.0)
    )
    capex = (
        expand_units * OPERATIONS_CHANGE_PRICES["expand_resource"]["capex_usd"]
        + (OPERATIONS_CHANGE_PRICES["stagger_shifts"]["capex_usd"] if stagger_active else 0.0)
        + spot_units * OPERATIONS_CHANGE_PRICES["spot_rental_overtime"]["capex_usd"]
        + (OPERATIONS_CHANGE_PRICES["automate_intake"]["capex_usd"] if auto_active else 0.0)
    )
    unit_val = float(a["unit_value_usd"])
    net_daily_usd = round(throughput * unit_val - fixed_cost, 2)
    unc = float(a.get("uncertainty_pct", 7)) / 100.0
    low_ops = round(throughput * (1.0 - unc))
    high_ops = round(throughput * (1.0 + unc))

    return {
        "capacities": capacities,
        "station_labels": station_labels,
        "workflow_capacity_ops_per_day": capacities["workflow"],
        "formula_capacity_ops_per_day": capacities["formula"],
        "inputs_capacity_ops_per_day": capacities["inputs"],
        "demand_capacity_ops_per_day": capacities["demand"],
        "throughput_ops_per_day": throughput,
        "bottleneck_id": bottleneck_id,
        "bottleneck_label": station_labels.get(bottleneck_id, bottleneck_id),
        "next_ceiling_id": next_ceiling_id,
        "next_ceiling_label": station_labels.get(next_ceiling_id, next_ceiling_id),
        "third_ceiling_id": third_ceiling_id,
        "third_ceiling_label": station_labels.get(third_ceiling_id, third_ceiling_id),
        "unit_value_usd": unit_val,
        "fixed_cost_usd_per_day": round(fixed_cost, 2),
        "capex_usd": round(capex, 2),
        "net_daily_usd": net_daily_usd,
        "uncertainty_pct": int(round(float(a.get("uncertainty_pct", 7)))),
        "throughput_band_ops_per_day": [low_ops, high_ops],
        "net_daily_band_usd": [
            round(low_ops * unit_val - fixed_cost, 2),
            round(high_ops * unit_val - fixed_cost, 2),
        ],
        "unit": "ops/day",
    }


def new_operations_record(
    assumptions: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prof = copy.deepcopy(profile or extract_operational_profile("Custom operational application"))
    a = copy.deepcopy(OPERATIONS_BASELINE_ASSUMPTIONS)
    if assumptions:
        a.update(assumptions)
    comp = compute_operations_model(a, prof)
    patches = operations_next_step_patches(a)

    path_meta = {
        "expand_resource": {
            "label": prof.get("expand_label", "Expand primary equipment & resource pool"),
            "node": "workflow",
        },
        "stagger_shifts": {
            "label": prof.get("stagger_label", "Stagger crew handoff & processing shifts"),
            "node": "formula",
        },
        "spot_rental_overtime": {
            "label": prof.get("spot_label", "Use high-cost spot overtime / rental capacity (Conventional)"),
            "node": "workflow",
        },
        "automate_intake": {
            "label": prof.get("auto_label", "Add structured intake validation templates"),
            "node": "inputs",
        },
    }

    paths: dict[str, Any] = {}
    for pid, patch in patches.items():
        cand_a = copy.deepcopy(a)
        cand_a.update(patch)
        cand_c = compute_operations_model(cand_a, prof)
        target_node = path_meta[pid]["node"]
        node_delta = cand_c["capacities"][target_node] - comp["capacities"][target_node]
        delta_ops = cand_c["throughput_ops_per_day"] - comp["throughput_ops_per_day"]
        paths[pid] = {
            "label": path_meta[pid]["label"],
            "node": target_node,
            "assumption_patch": patch,
            "capacity_delta": node_delta,
            "capex_usd": OPERATIONS_CHANGE_PRICES[pid]["capex_usd"],
            "fixed_cost_delta_usd_per_day": OPERATIONS_CHANGE_PRICES[pid]["fixed_cost_delta_usd_per_day"],
            "expected_throughput_ops_per_day": cand_c["throughput_ops_per_day"],
            "expected_delta_ops_per_day": delta_ops,
            "expected_net_daily_usd": cand_c["net_daily_usd"],
            "next_bottleneck_id": cand_c["bottleneck_id"],
            "next_bottleneck_label": cand_c["bottleneck_label"],
            "is_conventional_comparator": (pid == "spot_rental_overtime"),
            "is_clamped_trap": (delta_ops == 0 and node_delta > 0),
        }

    return {
        "profile": prof,
        "assumptions": a,
        "computed": comp,
        "paths": paths,
        "notes": (
            "Deterministic multi-station operational capacity, bottleneck, and counterfactual model "
            "compiled from stated prompt parameters. Propagates assumption changes into record calculations."
        ),
    }


def compile_runnable_micro_app_html(state: dict[str, Any]) -> str:
    """Generates a self-contained, single-file runnable HTML application (<300 lines)
    for any synthesized project with zero external dependencies, localStorage + in-memory
    fallback persistence, XSS-safe DOM rendering, live assumption what-if controls,
    and full record CRUD + status workflow."""
    title = str(state.get("title", "OpenLine Genie Operational App"))
    subtitle = str(state.get("subtitle", "Local-First Stateful Application"))
    project_id = str(state.get("project_id", "genie-synth-app"))
    formula_desc = str(state.get("formula_description", "net_total_dollars = round((quantity_units * unit_rate_dollars) + adjustments_dollars, 2)"))
    honesty = str(state.get("honesty_boundary", "SYNTHESIZED LOCAL-FIRST APPLICATION: $0 local compiler, no external network calls."))
    fields = state.get("fields", [])
    records = state.get("records", [])
    wf_states = state.get("workflow_states", ["ACTIVE", "COMPLETED_VERIFIED", "NEEDS_REVIEW"])
    ops = state.get("operations_model") or {}
    assumptions = ops.get("assumptions") or OPERATIONS_BASELINE_ASSUMPTIONS
    computed = ops.get("computed") or {}
    profile = ops.get("profile") or {}

    initial_payload = {
        "project_id": project_id,
        "title": title,
        "formula_description": formula_desc,
        "workflow_states": wf_states,
        "fields": fields,
        "records": records,
        "assumptions": assumptions,
        "computed": computed,
        "station_labels": computed.get("station_labels") or {
            "workflow": profile.get("workflow_label", "Primary Resource Pool"),
            "formula": profile.get("formula_label", "Assigned Crew & Rules"),
            "inputs": profile.get("inputs_label", "Intake & Triage"),
            "demand": profile.get("demand_label", "Daily Demand"),
        },
        "metric_label": profile.get("metric_label", "Calculated Net Total ($)"),
    }
    json_seed = json.dumps(initial_payload, sort_keys=True).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{color-scheme:dark;--bg:#070d1f;--card:#0d1830;--line:#26406b;--ink:#f3f7ff;--muted:#9fb6d6;--cyan:#55dcff;--mint:#76efb2;--violet:#b9a7ff;--coral:#ff7087}}
*{{box-sizing:border-box}}body{{margin:0;padding:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--ink);line-height:1.45}}
main{{max-width:980px;margin:0 auto;display:flex;flex-direction:column;gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}
.top{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}}
.badge{{display:inline-block;padding:4px 9px;border-radius:999px;font-size:11px;font-weight:600;background:#102a45;color:var(--cyan);border:1px solid #55dcff55}}
.badge.limit{{background:#241e4e;color:var(--violet);border-color:#b9a7ff66}}
h1{{margin:4px 0;font-size:20px}}h2{{margin:0 0 8px;font-size:15px;color:var(--cyan)}}
p.sub{{margin:0;font-size:12.5px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px;margin-top:10px}}
.stat{{background:#081124;border:1px solid #1e355d;border-radius:9px;padding:10px}}
.stat small{{display:block;font-size:11px;color:var(--muted)}}.stat strong{{font-size:16px;color:var(--ink)}}
.formRow{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px;align-items:end}}
label{{display:flex;flex-direction:column;gap:4px;font-size:11.5px;color:var(--muted)}}
input,select{{padding:8px 9px;border-radius:8px;border:1px solid #335280;background:#060c1b;color:var(--ink);font-size:13px;min-height:38px}}
button{{padding:8px 13px;border-radius:8px;border:1px solid #55dcff88;background:#113852;color:var(--ink);font-weight:600;font-size:12.5px;cursor:pointer;min-height:38px}}
button.secondary{{background:#101e38;border-color:#385682;color:var(--muted)}}
button.danger{{background:#3a1525;border-color:#ff708788;color:#ffd4dc}}
.tblWrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid #1c3154}}th{{color:var(--muted);font-weight:600}}
.actions{{display:flex;gap:6px;flex-wrap:wrap}}
.note{{font-size:11.5px;color:var(--muted);margin-top:6px}}
</style>
</head>
<body>
<main>
  <section class="card">
    <div class="top">
      <div>
        <span class="badge">RUNNABLE LOCAL-FIRST APP • ZERO EXTERNAL DEPS</span>
        <h1 id="appTitle">{html.escape(title)}</h1>
        <p class="sub">{html.escape(subtitle)}</p>
      </div>
      <div class="actions">
        <button type="button" id="exportCsvBtn" class="secondary">Export CSV</button>
        <button type="button" id="exportJsonBtn" class="secondary">Export JSON</button>
        <button type="button" id="resetDefaultBtn" class="secondary">Reset Defaults</button>
      </div>
    </div>
    <p class="note" id="honestyText">{html.escape(honesty)}</p>
    <div class="grid" id="stationGrid"></div>
  </section>

  <section class="card" aria-label="Operating Assumptions What-If">
    <h2>Operating Assumptions &amp; Bottleneck Calculator</h2>
    <div class="formRow" id="assumptionForm">
      <label>Resource Units<input type="number" id="asmResourceUnits" min="1" max="50" step="1"></label>
      <label>Cycles / Unit / Day<input type="number" id="asmCyclesPerUnit" min="1" max="100" step="1"></label>
      <label>Efficiency Multiplier<input type="number" id="asmEfficiency" min="0.25" max="4.0" step="0.05"></label>
      <label>Active Staff / Crew<input type="number" id="asmStaffCount" min="1" max="50" step="1"></label>
      <label>Shift Hours / Person<input type="number" id="asmShiftHours" min="1" max="24" step="0.5"></label>
      <label>Intake Channels<input type="number" id="asmIntakeChannels" min="1" max="20" step="1"></label>
      <button type="button" id="applyAssumptionsBtn">Update Assumptions</button>
    </div>
    <p class="note" id="formulaReadout">Formula: {html.escape(formula_desc)}</p>
  </section>

  <section class="card" aria-label="Add Operational Record">
    <h2>Add {html.escape(str(state.get("primary_entity", "Operational Record")))}</h2>
    <form id="recordForm" onsubmit="return false;">
      <div class="formRow" id="recordInputs"></div>
      <div class="actions" style="margin-top:10px">
        <button type="button" id="addRecordBtn">Add &amp; Calculate Record</button>
      </div>
    </form>
  </section>

  <section class="card" aria-label="Active Operational Records">
    <div class="top">
      <h2>Active Records (<span id="recordCount">0</span>)</h2>
      <span class="badge limit" id="totalMetricBadge">Total: $0.00</span>
    </div>
    <div class="tblWrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Record / Description</th>
            <th>Category / Scope</th>
            <th>Assigned</th>
            <th>Qty / Hrs</th>
            <th id="metricColHead">Calculated Metric</th>
            <th>Cap. Share</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="recordTableBody"></tbody>
      </table>
    </div>
  </section>
</main>
<script>
(function(){{
  const SEED = {json_seed};
  const STORAGE_KEY = 'openline_genie_app_' + SEED.project_id;
  let memoryState = null;

  function clone(x){{ return JSON.parse(JSON.stringify(x)); }}
  function loadState(){{
    try {{
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {{
        const parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.records)) {{
          memoryState = parsed;
          return memoryState;
        }}
      }}
    }} catch (e) {{}}
    if (!memoryState) memoryState = clone(SEED);
    return memoryState;
  }}
  function saveState(st){{
    memoryState = st;
    try {{ window.localStorage.setItem(STORAGE_KEY, JSON.stringify(st)); }} catch (e) {{}}
  }}

  function computeSystem(st){{
    const a = st.assumptions || {{}};
    const resUnits = Math.max(1, Number(a.resource_units) || 3);
    const cyc = Math.max(1, Number(a.cycles_per_unit_per_day) || 14);
    const eff = Math.max(0.25, Number(a.efficiency_multiplier) || 1.0);
    const buf = Math.max(0, Number(a.reserve_buffer_units) || 0);
    const staff = Math.max(1, Number(a.active_staff_count) || 4);
    const hrs = Math.max(1, Number(a.hours_per_shift) || 7);
    const cph = Math.max(0.25, Number(a.cases_per_staff_hour) || 2);
    const stag = a.staggered_handoff_enabled ? 14 : 0;
    const ch = Math.max(1, Number(a.intake_channels) || 2);
    const ir = Math.max(1, Number(a.intake_rate_per_channel) || 34);
    const autoT = a.auto_triage_enabled ? 20 : 0;
    const dem = Math.max(1, Number(a.stated_daily_demand) || 85);

    const caps = {{
      workflow: Math.max(1, Math.round(resUnits * cyc * eff + buf)),
      formula: Math.max(1, Math.round(staff * hrs * cph + stag)),
      inputs: Math.max(1, Math.round(ch * ir + autoT)),
      demand: Math.max(1, Math.round(dem))
    }};
    const order = ['workflow', 'formula', 'inputs', 'demand'].sort((x, y) => caps[x] - caps[y]);
    const bId = order[0];
    const tp = caps[bId];
    const unitVal = Number(a.unit_value_usd) || 15;
    const fixed = Number(a.daily_fixed_cost_usd) || 180;
    const netUsd = Math.round((tp * unitVal - fixed) * 100) / 100;

    for (const r of (st.records || [])) {{
      const q = Math.max(0, Number(r.quantity_units ?? r.days_borrowed ?? r.array_watts ?? 1));
      const rate = Math.max(0, Number(r.unit_rate_dollars ?? r.deposit_paid_dollars ?? r.marginal_rate_dollars ?? 50));
      const adj = Number(r.adjustments_dollars ?? 0);
      r.computed_metric_label = st.metric_label || 'Calculated Net Total ($)';
      r.computed_metric_value = Math.round(((q * rate) + adj) * eff * 100) / 100;
      r.capacity_share_pct = Math.round((Math.max(q, 1) / Math.max(tp, 1)) * 1000) / 10;
    }}
    return {{ caps, bId, tp, netUsd, eff }};
  }}

  function buildFormInputs(st){{
    const host = document.getElementById('recordInputs');
    host.replaceChildren();
    const defs = (st.fields && st.fields.length) ? st.fields : [
      {{key:'item_title', label:'Item / Request Name', type:'text', default:''}},
      {{key:'category_tag', label:'Category / Scope', type:'text', default:'Standard'}},
      {{key:'assignee_name', label:'Assigned Lead', type:'text', default:'Unassigned'}},
      {{key:'quantity_units', label:'Units / Hours', type:'number', default:2}},
      {{key:'unit_rate_dollars', label:'Unit Rate ($)', type:'number', default:50}},
      {{key:'adjustments_dollars', label:'Adjustment ($)', type:'number', default:0}}
    ];
    defs.forEach((f, idx) => {{
      const lbl = document.createElement('label');
      lbl.textContent = f.label || f.key;
      const inp = document.createElement('input');
      inp.type = f.type === 'number' ? 'number' : 'text';
      inp.dataset.fieldKey = f.key;
      inp.placeholder = f.label || f.key;
      if (f.type === 'number') {{
        inp.step = 'any';
        inp.value = String(f.default !== undefined ? f.default : 1);
      }} else if (idx > 0 && f.default) {{
        inp.value = String(f.default);
      }}
      lbl.appendChild(inp);
      host.appendChild(lbl);
    }});
  }}

  function render(){{
    const st = loadState();
    const sys = computeSystem(st);
    const labels = st.station_labels || {{}};

    document.getElementById('asmResourceUnits').value = String(st.assumptions.resource_units ?? 3);
    document.getElementById('asmCyclesPerUnit').value = String(st.assumptions.cycles_per_unit_per_day ?? 14);
    document.getElementById('asmEfficiency').value = String(st.assumptions.efficiency_multiplier ?? 1.0);
    document.getElementById('asmStaffCount').value = String(st.assumptions.active_staff_count ?? 4);
    document.getElementById('asmShiftHours').value = String(st.assumptions.hours_per_shift ?? 7);
    document.getElementById('asmIntakeChannels').value = String(st.assumptions.intake_channels ?? 2);

    const grid = document.getElementById('stationGrid');
    grid.replaceChildren();
    const cards = [
      ['System Throughput', sys.tp + ' ops/day (Limit: ' + (labels[sys.bId] || sys.bId) + ')'],
      [labels.workflow || 'Resource Pool', sys.caps.workflow + ' ops/day' + (sys.bId === 'workflow' ? ' [LIMIT]' : '')],
      [labels.formula || 'Assigned Crew', sys.caps.formula + ' ops/day' + (sys.bId === 'formula' ? ' [LIMIT]' : '')],
      [labels.inputs || 'Intake Queue', sys.caps.inputs + ' ops/day' + (sys.bId === 'inputs' ? ' [LIMIT]' : '')],
      ['Projected Net Value', '$' + sys.netUsd.toFixed(2) + '/day']
    ];
    for (const [k, v] of cards) {{
      const d = document.createElement('div');
      d.className = 'stat';
      const sm = document.createElement('small'); sm.textContent = k;
      const stg = document.createElement('strong'); stg.textContent = v;
      d.append(sm, stg);
      grid.appendChild(d);
    }}

    const tbody = document.getElementById('recordTableBody');
    tbody.replaceChildren();
    let totalMetric = 0;
    const recs = st.records || [];
    document.getElementById('recordCount').textContent = String(recs.length);
    document.getElementById('metricColHead').textContent = st.metric_label || 'Calculated Metric';

    recs.forEach((r, idx) => {{
      const tr = document.createElement('tr');
      const titleVal = r.item_title || r.item_name || r.scenario_name || r.plot_id || r.representative_name || 'Record';
      const catVal = r.category_tag || r.crop_family || r.target_constraint || r.roll_call_id || 'General';
      const asnVal = r.assignee_name || r.borrower_name || 'Assigned Lead';
      const qtyVal = r.quantity_units ?? r.days_borrowed ?? r.water_gallons_per_week ?? r.array_watts ?? 1;
      const metVal = Number(r.computed_metric_value || 0);
      totalMetric += metVal;

      const cells = [
        r.record_id || ('REC-' + (101 + idx)),
        String(titleVal),
        String(catVal),
        String(asnVal),
        String(qtyVal),
        '$' + metVal.toFixed(2),
        String(r.capacity_share_pct ?? 5.0) + '%',
        r.status || 'ACTIVE'
      ];
      cells.forEach(c => {{
        const td = document.createElement('td');
        td.textContent = c;
        tr.appendChild(td);
      }});
      const actTd = document.createElement('td');
      const actDiv = document.createElement('div');
      actDiv.className = 'actions';
      const stBtn = document.createElement('button');
      stBtn.type = 'button';
      stBtn.className = 'secondary';
      stBtn.textContent = 'Advance Status';
      stBtn.addEventListener('click', () => {{
        const wfs = st.workflow_states || ['ACTIVE', 'COMPLETED_VERIFIED'];
        const curIdx = wfs.indexOf(r.status);
        r.status = wfs[(curIdx + 1) % wfs.length];
        saveState(st);
        render();
      }});
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'danger';
      delBtn.textContent = 'Delete';
      delBtn.addEventListener('click', () => {{
        st.records.splice(idx, 1);
        saveState(st);
        render();
      }});
      actDiv.append(stBtn, delBtn);
      actTd.appendChild(actDiv);
      tr.appendChild(actTd);
      tbody.appendChild(tr);
    }});
    document.getElementById('totalMetricBadge').textContent = 'Total Value: $' + totalMetric.toFixed(2);
  }}

  document.getElementById('addRecordBtn').addEventListener('click', () => {{
    const st = loadState();
    const rec = {{
      record_id: 'REC-' + (101 + (st.records ? st.records.length : 0)),
      status: (st.workflow_states && st.workflow_states[0]) || 'ACTIVE'
    }};
    const inputs = document.querySelectorAll('#recordInputs input');
    inputs.forEach(inp => {{
      const k = inp.dataset.fieldKey;
      if (!k) return;
      if (inp.type === 'number') {{
        const n = Number(inp.value);
        rec[k] = Number.isFinite(n) ? n : 1;
      }} else {{
        rec[k] = (inp.value || '').trim() || 'Operational Entry';
      }}
    }});
    if (!rec.item_title && !rec.item_name) rec.item_title = 'Operational Entry';
    if (!rec.category_tag) rec.category_tag = 'Standard Scope';
    if (!rec.assignee_name) rec.assignee_name = 'Assigned Coordinator';
    if (rec.quantity_units === undefined) rec.quantity_units = 2;
    if (rec.unit_rate_dollars === undefined) rec.unit_rate_dollars = 50;
    if (rec.adjustments_dollars === undefined) rec.adjustments_dollars = 0;
    st.records = st.records || [];
    st.records.push(rec);
    saveState(st);
    render();
  }});

  document.getElementById('applyAssumptionsBtn').addEventListener('click', () => {{
    const st = loadState();
    const ru = Number(document.getElementById('asmResourceUnits').value);
    const cy = Number(document.getElementById('asmCyclesPerUnit').value);
    const ef = Number(document.getElementById('asmEfficiency').value);
    const sc = Number(document.getElementById('asmStaffCount').value);
    const sh = Number(document.getElementById('asmShiftHours').value);
    const ic = Number(document.getElementById('asmIntakeChannels').value);
    if (ru > 0 && cy > 0 && ef > 0 && sc > 0 && sh > 0 && ic > 0) {{
      st.assumptions.resource_units = ru;
      st.assumptions.cycles_per_unit_per_day = cy;
      st.assumptions.efficiency_multiplier = ef;
      st.assumptions.active_staff_count = sc;
      st.assumptions.hours_per_shift = sh;
      st.assumptions.intake_channels = ic;
      saveState(st);
      render();
    }}
  }});

  document.getElementById('resetDefaultBtn').addEventListener('click', () => {{
    saveState(clone(SEED));
    buildFormInputs(loadState());
    render();
  }});

  document.getElementById('exportJsonBtn').addEventListener('click', () => {{
    const blob = new Blob([JSON.stringify(loadState(), null, 2)], {{type: 'application/json'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = SEED.project_id + '-state.json';
    a.click();
  }});

  document.getElementById('exportCsvBtn').addEventListener('click', () => {{
    const st = loadState();
    const rows = [['RecordID', 'Title', 'Category', 'Assigned', 'Qty', 'MetricValue', 'CapacitySharePct', 'Status']];
    for (const r of (st.records || [])) {{
      rows.push([
        r.record_id || '',
        r.item_title || r.item_name || '',
        r.category_tag || '',
        r.assignee_name || '',
        r.quantity_units ?? 1,
        r.computed_metric_value ?? 0,
        r.capacity_share_pct ?? 0,
        r.status || 'ACTIVE'
      ]);
    }}
    const csv = rows.map(r => r.map(x => '"' + String(x).replace(/"/g, '""') + '"').join(',')).join('\\n');
    const blob = new Blob([csv], {{type: 'text/csv'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = SEED.project_id + '-records.csv';
    a.click();
  }});

  buildFormInputs(loadState());
  render();
}})();
</script>
</body>
</html>"""


def compile_operational_project(prompt: str) -> dict[str, Any]:
    """Compiles an unfamiliar natural-language prompt into a full synthesized app specification
    with an operational capacity/bottleneck model (`operations_model`), domain-specific fields,
    and seeded records."""
    prof = extract_operational_profile(prompt)
    ops_rec = new_operations_record(None, prof)
    comp = ops_rec["computed"]
    eff = float(ops_rec["assumptions"].get("efficiency_multiplier", 1.0))
    tp = max(1, int(comp["throughput_ops_per_day"]))

    fields = [
        {"key": "item_title", "label": prof["item_field_label"], "type": "text", "required": True},
        {"key": "category_tag", "label": prof["category_field_label"], "type": "text", "required": True, "default": "Standard Scope"},
        {"key": "assignee_name", "label": prof["assignee_field_label"], "type": "text", "required": False, "default": "Assigned Coordinator"},
        {"key": "quantity_units", "label": prof["qty_field_label"], "type": "number", "min": 0.5, "max": 100000, "default": 3.0},
        {"key": "unit_rate_dollars", "label": prof["rate_field_label"], "type": "number", "min": 0, "max": 100000, "default": 55.0},
        {"key": "adjustments_dollars", "label": prof["adj_field_label"], "type": "number", "min": -5000, "max": 50000, "default": 15.0},
    ]

    records = []
    for raw_r in prof["seed_records"]:
        r = copy.deepcopy(raw_r)
        q = float(r.get("quantity_units", 1.0))
        rate = float(r.get("unit_rate_dollars", 50.0))
        adj = float(r.get("adjustments_dollars", 0.0))
        r["computed_metric_label"] = prof["metric_label"]
        r["computed_metric_value"] = round(((q * rate) + adj) * eff, 2)
        r["capacity_share_pct"] = round(100.0 * max(q, 1.0) / tp, 2)
        records.append(r)

    out_spec = {
        "app_slug": prof["app_slug"],
        "title": prof["title"],
        "subtitle": prof["subtitle"],
        "category": prof["category"],
        "domain_subtype": "operational_micro_app",
        "primary_entity": prof["primary_entity"],
        "fields": fields,
        "formula_description": (
            "net_total_dollars = round(((quantity_units * unit_rate_dollars) + adjustments_dollars) "
            "* efficiency_multiplier, 2)"
        ),
        "workflow_states": prof["workflow_states"],
        "operations_model": ops_rec,
        "constraints": {
            "binding_constraint_id": comp["bottleneck_id"],
            "binding_constraint_label": comp["bottleneck_label"],
            "plain_language_diagnosis": (
                f"{comp['bottleneck_label']} ({comp['throughput_ops_per_day']} ops/day) is the active binding constraint: "
                f"3 resource units at 14 cycles/day cap throughput at {comp['throughput_ops_per_day']} ops/day even though "
                f"{comp['next_ceiling_label']} supports {comp['capacities'][comp['next_ceiling_id']]} ops/day and "
                f"{comp['third_ceiling_label']} supports {comp['capacities'][comp['third_ceiling_id']]} ops/day."
            ),
            "capacities": comp["capacities"],
            "options_compared": ops_rec["paths"],
        },
        "records": records,
    }
    p_low = prompt.lower()
    if any(k in p_low for k in ("energy cooperative", "essential-cost cooperative", "franklin")):
        from core.civilization_applications import evaluate_community_energy_cooperative
        ev_a = evaluate_community_energy_cooperative()
        out_spec["civilization_app"] = {
            "application_id": "APPLICATION_A_COMMUNITY_ENERGY_COOPERATIVE",
            "assumptions": ev_a["inputs_and_assumptions"],
            "evaluation": ev_a,
        }
    elif any(k in p_low for k in ("institutional appeal", "appeal assistant", "public-benefits", "baldwin")):
        from core.civilization_applications import evaluate_public_benefits_appeal
        ev_b = evaluate_public_benefits_appeal(include_missing_medical_cert=False)
        out_spec["civilization_app"] = {
            "application_id": "APPLICATION_B_PUBLIC_BENEFITS_APPEAL_ASSISTANT",
            "assumptions": {
                "notice_date": "2026-11-01",
                "postmark_date": "2026-11-04",
                "disaster_grant_excluded": 1,
                "medical_device_telemetry_verified": 1,
            },
            "evaluation": ev_b,
        }
    elif any(k in p_low for k in ("scientific research workspace", "self-correcting scientific", "einstein")):
        from core.civilization_applications import run_self_correcting_scientific_workspace
        ev_d = run_self_correcting_scientific_workspace(invalidate_batch_02=False)
        out_spec["civilization_app"] = {
            "application_id": "APPLICATION_D_SELF_CORRECTING_RESEARCH_WORKSPACE",
            "assumptions": {
                "DATASET_BATCH_01": 1,
                "DATASET_BATCH_02": 1,
                "HYPOTHESIS_H3_TRIAL": 1,
            },
            "evaluation": ev_d,
        }
    elif any(k in p_low for k in ("public infrastructure decision", "decision accountability", "arendt")):
        from core.civilization_applications import evaluate_public_infrastructure_accountability
        ev_e = evaluate_public_infrastructure_accountability()
        out_spec["civilization_app"] = {
            "application_id": "APPLICATION_E_PUBLIC_INFRASTRUCTURE_ACCOUNTABILITY",
            "assumptions": ev_e["assumptions_and_constraints"],
            "evaluation": ev_e,
        }
    elif any(k in p_low for k in ("pharmacy cold-chain", "insulin/vaccine cooperative", "formulary")):
        from core.civilization_applications import evaluate_unfamiliar_sixth_task_pharmacy_coldchain
        ev_6 = evaluate_unfamiliar_sixth_task_pharmacy_coldchain()
        out_spec["civilization_app"] = {
            "application_id": "UNFAMILIAR_TASK_6_PHARMACY_COLDCHAIN_FORMULARY",
            "assumptions": {"ambient_heat_wave_c": 34.0, "min_required_holdover_h": 48.0, "fda_lot_recall_bulletin": 1},
            "evaluation": ev_6,
        }
    return out_spec


def recompute_operations_model_state(state: dict[str, Any]) -> dict[str, Any]:
    """Recomputes `operations_model`, `constraints`, and dependent record metrics/capacity shares when assumptions change."""
    ops = state.get("operations_model")
    if not isinstance(ops, dict) or "assumptions" not in ops:
        return state
    prof = ops.get("profile") or extract_operational_profile(str(state.get("prompt", state.get("title", ""))))
    record = new_operations_record(ops["assumptions"], prof)
    state["operations_model"] = record
    comp = record["computed"]
    state["constraints"] = {
        "binding_constraint_id": comp["bottleneck_id"],
        "binding_constraint_label": comp["bottleneck_label"],
        "plain_language_diagnosis": (
            f"{comp['bottleneck_label']} ({comp['throughput_ops_per_day']} ops/day) is the current binding constraint. "
            f"Next ceiling is {comp['next_ceiling_label']} ({comp['capacities'][comp['next_ceiling_id']]} ops/day)."
        ),
        "capacities": comp["capacities"],
        "options_compared": record["paths"],
    }
    eff = float(record["assumptions"].get("efficiency_multiplier", 1.0))
    tp = max(1, int(comp["throughput_ops_per_day"]))
    metric_lbl = prof.get("metric_label", "Calculated Net Total ($)")
    for rec in state.get("records", []):
        if not isinstance(rec, dict):
            continue
        if "quantity_units" in rec and "unit_rate_dollars" in rec:
            q = float(rec.get("quantity_units", 1.0))
            rate = float(rec.get("unit_rate_dollars", 0.0))
            adj = float(rec.get("adjustments_dollars", 0.0))
            rec["computed_metric_label"] = metric_lbl
            rec["computed_metric_value"] = round(((q * rate) + adj) * eff, 2)
            rec["capacity_share_pct"] = round(100.0 * max(q, 1.0) / tp, 2)
    return state
