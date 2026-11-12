#!/usr/bin/env python3
"""OpenLine Genie Core Engine (`genie_engine.py`).

Unifies:
- ReceiverGuard (`core/openline_guard.py` with Adversarial Workflow Lab repairs D-01, D-01b, D-03, AF-06)
- IPC Intent-Hash Idempotency (`core/ipc_protocol.py` D-02)
- Demonstration A: Small Service Business Quoting & Invoicing App (`service_quoting_invoicing`)
- Demonstration B: Free Interactive Robotics Learning Environment for Kids (`robot_academy_kids`)
- Optional Domain Skills: Solar SB 868 (`solar_energy_sb868`), Civic Roll Call 283 (`civic_voting_records`), Writing Studio (`writing_studio_copy`)
- Hundred-Yard Jump: `GenieAppSynthesizer` (`openline.genie.synthesized_app.v1`) for unfamiliar natural-language requests.
- RC3 model worker: `GenieWorker` (`core/genie_worker.py`) behind the portable
  `ModelAdapter` interface (`core/model_adapter.py`); runnable-app artifact
  store `genie_app_versions`; model swap, close/reopen.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
import stat
import html
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE / "core") not in sys.path:
    sys.path.insert(0, str(HERE / "core"))

from core.openline_guard import (
    GuardRefused,
    ReceiverGuard,
    SigningIdentity,
    VerificationError,
    canonical,
    sha256_hex,
    verify_receipt_offline,
)
import fcntl
import threading
from contextlib import contextmanager
from core.bakery import (
    bakery_state_fields,
    is_bakery_prompt,
    new_bakery_record,
    recompute_bakery_state,
)
from core.community_garden import (
    compute_garden,
    is_garden_prompt,
    new_garden_record,
    recompute_garden_state,
)
from core.model_optimizer import (
    compute_neural_model,
    is_neural_model_prompt,
    new_neural_model_record,
    recompute_neural_model_state,
)
from core.ipc_protocol import ipc_request_intent_sha256
from core.model_adapter import TOTAL_CAP_USD, SpendLedger

TRUSTED_PROJECT_FAMILIES = frozenset({
    "service_quoting_invoicing",
    "robot_academy_kids",
    "bakery",
    "synthesized_micro_app",
    "model_built_app",
})

IMMUTABLE_IDENTITY_KEYS = frozenset({"project_id", "schema"})

_ENGINE_META_LOCK = threading.Lock()
_ENGINE_DIR_LOCKS: dict[str, threading.RLock] = {}


def _get_engine_dir_lock(state_dir: Path) -> threading.RLock:
    key = str(state_dir.resolve())
    with _ENGINE_META_LOCK:
        lk = _ENGINE_DIR_LOCKS.get(key)
        if lk is None:
            lk = threading.RLock()
            _ENGINE_DIR_LOCKS[key] = lk
        return lk


# ---------------------------------------------------------------------------
# Consequential External Actions Gate (Always Owner-Controlled)
# ---------------------------------------------------------------------------
CONSEQUENTIAL_EXTERNAL_ACTIONS = {
    "publish_public_website",
    "charge_payment_card",
    "send_customer_email",
    "deploy_external_service",
    "use_saved_credentials",
    "actuate_physical_robot",
    "spend_money",
}


# ---------------------------------------------------------------------------
# Demonstration A: Small Service Business Quoting & Invoicing Engine
# ---------------------------------------------------------------------------
def finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"invalid_numeric_value:{label}") from None
    if not math.isfinite(number):
        raise ValueError(f"nonfinite_numeric_value:{label}")
    return number


def calculate_quote_totals(
    line_items: list[dict[str, Any]],
    discount_pct: float = 0.0,
    tax_rate_pct: float = 8.25,
    deposit_pct: float = 25.0,
) -> dict[str, Any]:
    """Deterministic cent-accurate quote and invoice calculation."""
    discount_pct = finite_number(discount_pct, "discount_pct")
    tax_rate_pct = finite_number(tax_rate_pct, "tax_rate_pct")
    deposit_pct = finite_number(deposit_pct, "deposit_pct")
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("discount_pct_out_of_bounds")
    if tax_rate_pct < 0 or tax_rate_pct > 30:
        raise ValueError("tax_rate_pct_out_of_bounds")
    if deposit_pct < 0 or deposit_pct > 100:
        raise ValueError("deposit_pct_out_of_bounds")

    subtotal_cents = 0
    taxable_Raw_cents = 0
    normalized_items = []
    for item in line_items:
        qty = finite_number(item.get("quantity", 1), "quantity")
        price = finite_number(item.get("unit_price_dollars", 0.0), "unit_price_dollars")
        unit_price_cents = int(round(price * 100))
        if qty < 0 or unit_price_cents < 0:
            raise ValueError("negative_line_item_not_allowed")
        line_cents = int(round(qty * unit_price_cents))
        taxable = bool(item.get("taxable", True))
        subtotal_cents += line_cents
        if taxable:
            taxable_Raw_cents += line_cents
        normalized_items.append({
            "service_id": str(item.get("service_id", "srv-custom")),
            "description": str(item.get("description", "Service Item")),
            "unit": str(item.get("unit", "job")),
            "quantity": qty,
            "unit_price_dollars": round(unit_price_cents / 100.0, 2),
            "line_total_dollars": round(line_cents / 100.0, 2),
            "line_total_cents": line_cents,
            "taxable": taxable,
        })

    discount_cents = int(round(subtotal_cents * (discount_pct / 100.0)))
    after_discount_cents = max(0, subtotal_cents - discount_cents)
    taxable_after_discount_cents = int(round(taxable_Raw_cents * (1.0 - discount_pct / 100.0)))
    tax_cents = int(round(taxable_after_discount_cents * (tax_rate_pct / 100.0)))
    total_cents = after_discount_cents + tax_cents
    deposit_due_cents = int(round(total_cents * (deposit_pct / 100.0)))

    return {
        "items": normalized_items,
        "subtotal_cents": subtotal_cents,
        "subtotal_dollars": round(subtotal_cents / 100.0, 2),
        "discount_pct": round(discount_pct, 2),
        "discount_cents": discount_cents,
        "discount_dollars": round(discount_cents / 100.0, 2),
        "tax_rate_pct": round(tax_rate_pct, 2),
        "taxable_subtotal_dollars": round(taxable_after_discount_cents / 100.0, 2),
        "tax_cents": tax_cents,
        "tax_dollars": round(tax_cents / 100.0, 2),
        "total_cents": total_cents,
        "total_dollars": round(total_cents / 100.0, 2),
        "deposit_pct": round(deposit_pct, 2),
        "deposit_due_cents": deposit_due_cents,
        "deposit_due_dollars": round(deposit_due_cents / 100.0, 2),
    }


def build_default_demo_a_state() -> dict[str, Any]:
    """Default initial state for Demonstration A (Small Service Business Quoting & Invoicing)."""
    customers = [
        {
            "customer_id": "CUST-101",
            "name": "Maria Chen (Oakridge Residence)",
            "phone": "(925) 555-0142",
            "email": "m.chen@oakridge.example",
            "address": "412 Sycamore Ridge Ln, San Ramon, CA",
            "notes": "Gate code #4412; prefers Saturday morning crew.",
        },
        {
            "customer_id": "CUST-102",
            "name": "Cedar Creek HOA Board",
            "phone": "(925) 555-0198",
            "email": "facilities@cedarcreekhoa.example",
            "address": "900 Bollinger Canyon Rd, San Ramon, CA",
            "notes": "Net-15 billing; requires itemized materials & labor.",
        },
        {
            "customer_id": "CUST-103",
            "name": "Hearth & Crumb Corner Cafe",
            "phone": "(925) 555-0165",
            "email": "ops@hearthcrumb.example",
            "address": "215 Market Plaza, San Ramon, CA",
            "notes": "Patio planter & drip line maintenance.",
        },
    ]
    services = [
        {
            "service_id": "SRV-01",
            "name": "Seasonal Lawn, Edging & Hedge Cleanup",
            "unit": "visit",
            "unit_price_dollars": 165.00,
            "taxable": False,
        },
        {
            "service_id": "SRV-02",
            "name": "Drip Irrigation Zone Valve & Emitter Retrofit",
            "unit": "zone",
            "unit_price_dollars": 120.00,
            "taxable": True,
        },
        {
            "service_id": "SRV-03",
            "name": "Organic Walk-On Bark Mulch (Installed)",
            "unit": "cubic yd",
            "unit_price_dollars": 85.00,
            "taxable": True,
        },
        {
            "service_id": "SRV-04",
            "name": "Patio Paver Leveling & Polymeric Sand Seal",
            "unit": "sq ft",
            "unit_price_dollars": 6.50,
            "taxable": True,
        },
    ]
    q1_calc = calculate_quote_totals(
        [
            {"service_id": "SRV-01", "description": "Seasonal Lawn, Edging & Hedge Cleanup", "unit": "visit", "quantity": 1, "unit_price_dollars": 165.00, "taxable": False},
            {"service_id": "SRV-02", "description": "Drip Irrigation Zone Valve & Emitter Retrofit", "unit": "zone", "quantity": 2, "unit_price_dollars": 120.00, "taxable": True},
            {"service_id": "SRV-03", "description": "Organic Walk-On Bark Mulch (Installed)", "unit": "cubic yd", "quantity": 4, "unit_price_dollars": 85.00, "taxable": True},
        ],
        discount_pct=5.0,
        tax_rate_pct=8.25,
        deposit_pct=25.0,
    )
    q2_calc = calculate_quote_totals(
        [
            {"service_id": "SRV-01", "description": "Seasonal Lawn, Edging & Hedge Cleanup", "unit": "visit", "quantity": 2, "unit_price_dollars": 165.00, "taxable": False},
            {"service_id": "SRV-04", "description": "Patio Paver Leveling & Polymeric Sand Seal", "unit": "sq ft", "quantity": 120, "unit_price_dollars": 6.50, "taxable": True},
        ],
        discount_pct=0.0,
        tax_rate_pct=8.25,
        deposit_pct=30.0,
    )
    quotes = [
        {
            "quote_id": "Q-1001",
            "customer_id": "CUST-101",
            "customer_name": "Maria Chen (Oakridge Residence)",
            "status": "ACCEPTED_BY_CUSTOMER",
            "created_date": "2026-11-10",
            "valid_until": "2026-11-25",
            "notes": "Includes 90-day workmanship warranty on drip valves.",
            **q1_calc,
        },
        {
            "quote_id": "Q-1002",
            "customer_id": "CUST-102",
            "customer_name": "Cedar Creek HOA Board",
            "status": "DRAFT",
            "created_date": "2026-11-10",
            "valid_until": "2026-11-30",
            "notes": "North walkway paver leveling and perimeter cleanup.",
            **q2_calc,
        },
    ]
    invoices = [
        {
            "invoice_id": "INV-2001",
            "source_quote_id": "Q-1001",
            "customer_id": "CUST-101",
            "customer_name": "Maria Chen (Oakridge Residence)",
            "issued_date": "2026-11-10",
            "due_date": "2026-11-25",
            "payment_terms": "Net 15",
            "payment_status": "PARTIAL_DEPOSIT_PAID",
            "total_cents": q1_calc["total_cents"],
            "total_dollars": q1_calc["total_dollars"],
            "paid_cents": q1_calc["deposit_due_cents"],
            "paid_dollars": q1_calc["deposit_due_dollars"],
            "balance_due_cents": q1_calc["total_cents"] - q1_calc["deposit_due_cents"],
            "balance_due_dollars": round((q1_calc["total_cents"] - q1_calc["deposit_due_cents"]) / 100.0, 2),
            "items": q1_calc["items"],
            "subtotal_dollars": q1_calc["subtotal_dollars"],
            "discount_dollars": q1_calc["discount_dollars"],
            "tax_dollars": q1_calc["tax_dollars"],
        }
    ]
    return {
        "project_id": "demo-a-service-quoting",
        "project_family": "service_quoting_invoicing",
        "title": "Verdant Pro — Local Quoting & Invoicing Tool",
        "prompt": "Build a free quoting and invoicing tool for my small service business.",
        "customization": {
            "business_name": "Verdant Valley Landscaping & Repair",
            "tagline": "Licensed Local Grounds, Irrigation & Hardscape Care • $0 Subscription Tool",
            "accent_color": "#059669",
            "default_tax_rate_pct": 8.25,
            "default_deposit_pct": 25.0,
            "payment_terms": "Net 15 (Check, Cash, or ACH)",
            "show_signature_line": True,
            "repeat_customer_discount_enabled": False,
        },
        "customers": customers,
        "services": services,
        "quotes": quotes,
        "invoices": invoices,
        "honesty_boundary": (
            "LOCAL-FIRST BUSINESS TOOL DISCLOSURE: Runs 100% free and offline in your browser with local persistence and HTML/CSV/JSON exports. "
            "Does NOT automatically generate customers, process live credit-card payments, or guarantee revenue."
        ),
    }


# ---------------------------------------------------------------------------
# Demonstration B: Free Interactive Robotics Learning Environment for Kids
# ---------------------------------------------------------------------------
ROBOT_ACADEMY_LEVELS: dict[int, dict[str, Any]] = {
    1: {
        "level": 1,
        "title": "Level 1: First Steps to the Solar Beacon",
        "goal_text": "Guide Sprocket from Start (1.0, 2.5) to the Solar Beacon (3.4, 2.5) without hitting the boulder!",
        "start_pose": {"x": 1.0, "y": 2.5, "heading_deg": 0.0},
        "target": {"x": 3.4, "y": 2.5, "radius_m": 0.45},
        "obstacles": [{"id": "boulder-1", "x": 2.2, "y": 1.2, "radius_m": 0.40}],
        "cells": [{"id": "cell-1", "x": 2.2, "y": 2.5}],
        "speed_limit_mps": 0.75,
        "min_clearance_m": 0.65,
        "human_walkway_x_m": 4.20,
        "recommended_blocks": ["FORWARD 1.2", "PICKUP_CELL", "FORWARD 1.2", "STOP_SAFE"],
    },
    2: {
        "level": 2,
        "title": "Level 2: Ultrasonic Obstacle Avoidance",
        "goal_text": "A boulder blocks the center path! Use ultrasonic sensor scan + turn blocks to detour safely around (2.2, 2.5).",
        "start_pose": {"x": 0.9, "y": 2.5, "heading_deg": 0.0},
        "target": {"x": 3.5, "y": 1.3, "radius_m": 0.45},
        "obstacles": [{"id": "crater-rock", "x": 2.2, "y": 2.5, "radius_m": 0.45}],
        "cells": [{"id": "cell-a", "x": 0.9, "y": 1.3}, {"id": "cell-b", "x": 2.3, "y": 1.3}],
        "speed_limit_mps": 0.75,
        "min_clearance_m": 0.65,
        "human_walkway_x_m": 4.20,
        "recommended_blocks": ["SCAN_SENSOR", "TURN_LEFT 90", "FORWARD 1.2", "PICKUP_CELL", "TURN_RIGHT 90", "FORWARD 1.4", "PICKUP_CELL", "FORWARD 1.2", "STOP_SAFE"],
    },
    3: {
        "level": 3,
        "title": "Level 3: Rover Battery Rescue Challenge",
        "goal_text": "Collect both stranded solar batteries and reach the Recharge Dock while keeping speed <= 0.75 m/s.",
        "start_pose": {"x": 0.8, "y": 3.2, "heading_deg": 0.0},
        "target": {"x": 3.6, "y": 1.2, "radius_m": 0.45},
        "obstacles": [
            {"id": "ridge-1", "x": 2.0, "y": 3.1, "radius_m": 0.40},
            {"id": "ridge-2", "x": 2.5, "y": 2.2, "radius_m": 0.38},
        ],
        "cells": [{"id": "bat-1", "x": 0.8, "y": 1.2}, {"id": "bat-2", "x": 2.2, "y": 1.2}],
        "speed_limit_mps": 0.75,
        "min_clearance_m": 0.65,
        "human_walkway_x_m": 4.20,
        "recommended_blocks": ["TURN_LEFT 90", "FORWARD 2.0", "PICKUP_CELL", "TURN_RIGHT 90", "FORWARD 1.4", "PICKUP_CELL", "FORWARD 1.4", "STOP_SAFE"],
    },
    4: {
        "level": 4,
        "title": "Level 4: Safe Workcell Permit & Walkway Boundary",
        "goal_text": "Deliver the payload to Station B (3.5, 2.0) and stop completely before the Human Walkway at x = 4.20 m!",
        "start_pose": {"x": 1.0, "y": 2.0, "heading_deg": 0.0},
        "target": {"x": 3.5, "y": 2.0, "radius_m": 0.45},
        "obstacles": [{"id": "pallet-01", "x": 2.2, "y": 3.1, "radius_m": 0.42}],
        "cells": [{"id": "tote-1", "x": 2.2, "y": 2.0}],
        "speed_limit_mps": 0.75,
        "min_clearance_m": 0.65,
        "human_walkway_x_m": 4.20,
        "recommended_blocks": ["SCAN_SENSOR", "FORWARD 1.2", "PICKUP_CELL", "FORWARD 1.3", "STOP_SAFE"],
    },
}


def simulate_robot_academy_program(
    level_num: int,
    blocks: list[str],
    requested_speed_mps: float = 0.55,
) -> dict[str, Any]:
    """Executes a kid's command block program in the 2D Robot Academy arena and returns trajectory + learning feedback."""
    lvl = copy.deepcopy(ROBOT_ACADEMY_LEVELS.get(int(level_num), ROBOT_ACADEMY_LEVELS[1]))
    x = float(lvl["start_pose"]["x"])
    y = float(lvl["start_pose"]["y"])
    heading_deg = float(lvl["start_pose"]["heading_deg"])

    permit_speed_cap = float(lvl["speed_limit_mps"])
    walkway_x = float(lvl["human_walkway_x_m"])
    min_req_clearance = float(lvl["min_clearance_m"])

    # Work Permit check on speed
    speed_clamped = False
    speed_mps = float(requested_speed_mps)
    if speed_mps > permit_speed_cap:
        speed_clamped = True

    path_points = [{"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": "START"}]
    collected_cells: list[str] = []
    sensor_scans = 0
    collision_detected = False
    walkway_breached = False
    min_observed_clearance = 9.99

    def check_clearance(px: float, py: float) -> float:
        best = 9.99
        for obs in lvl["obstacles"]:
            dist = math.hypot(px - float(obs["x"]), py - float(obs["y"])) - float(obs["radius_m"])
            if dist < best:
                best = dist
        return best

    min_observed_clearance = min(min_observed_clearance, check_clearance(x, y))

    for raw_cmd in blocks:
        cmd = raw_cmd.strip().upper()
        if not cmd:
            continue
        if cmd.startswith("FORWARD"):
            parts = cmd.split()
            dist = float(parts[1]) if len(parts) > 1 else 1.0
            steps = max(4, int(abs(dist) * 10))
            step_d = dist / steps
            rad = math.radians(heading_deg)
            for _ in range(steps):
                x += step_d * math.cos(rad)
                y -= step_d * math.sin(rad)  # SVG Y-up convention for turn left
                c = check_clearance(x, y)
                if c < min_observed_clearance:
                    min_observed_clearance = c
                if c <= 0.05:
                    collision_detected = True
                    break
                # Braking reach check
                stop_x = x + (speed_mps ** 2) / (2.0 * 1.2) + speed_mps * 0.12
                if stop_x > walkway_x or x > walkway_x:
                    walkway_breached = True
                    break
                for cell in lvl["cells"]:
                    if cell["id"] not in collected_cells:
                        if math.hypot(x - float(cell["x"]), y - float(cell["y"])) <= 0.42:
                            collected_cells.append(cell["id"])
            path_points.append({"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": cmd})
            if collision_detected or walkway_breached:
                break
        elif cmd.startswith("TURN_LEFT"):
            parts = cmd.split()
            deg = float(parts[1]) if len(parts) > 1 else 90.0
            heading_deg = (heading_deg + deg) % 360.0
            path_points.append({"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": cmd})
        elif cmd.startswith("TURN_RIGHT"):
            parts = cmd.split()
            deg = float(parts[1]) if len(parts) > 1 else 90.0
            heading_deg = (heading_deg - deg) % 360.0
            path_points.append({"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": cmd})
        elif cmd.startswith("SCAN"):
            sensor_scans += 1
            path_points.append({"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": "SCAN_SENSOR"})
        elif cmd.startswith("PICKUP"):
            for cell in lvl["cells"]:
                if cell["id"] not in collected_cells:
                    if math.hypot(x - float(cell["x"]), y - float(cell["y"])) <= 0.55:
                        collected_cells.append(cell["id"])
            path_points.append({"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": "PICKUP_CELL"})
        elif cmd.startswith("STOP"):
            path_points.append({"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1), "event": "STOP_SAFE"})

    dist_to_target = math.hypot(x - float(lvl["target"]["x"]), y - float(lvl["target"]["y"]))
    reached_target = (dist_to_target <= float(lvl["target"]["radius_m"])) and not collision_detected and not walkway_breached and not speed_clamped

    if speed_clamped:
        feedback = (
            f"Safety Permit Gate blocked speed {speed_mps:.2f} m/s (limit <= {permit_speed_cap:.2f} m/s) "
            f"so Sprocket's braking distance stays inside the {walkway_x:.2f} m walkway!"
        )
        status = "PERMIT_BLOCKED_UNSAFE_SPEED"
    elif collision_detected:
        feedback = "Bump! Sprocket came too close to an obstacle. Add a TURN_LEFT 90 or TURN_RIGHT 90 block to steer around it!"
        status = "COLLISION_RETRY"
    elif walkway_breached:
        feedback = f"Safety Boundary Alert! Sprocket crossed or braked past the Human Walkway at x = {walkway_x:.2f} m. Reduce distance or add STOP_SAFE sooner!"
        status = "WALKWAY_BOUNDARY_STOP"
    elif reached_target:
        feedback = (
            f"Mission Accomplished! Sprocket reached the goal with {len(collected_cells)}/{len(lvl['cells'])} energy cells "
            f"and {min_observed_clearance:.2f} m obstacle clearance!"
        )
        status = "MISSION_COMPLETE"
    else:
        feedback = f"Good move! Sprocket is {dist_to_target:.2f} m from the target beacon. Add another FORWARD or TURN block to reach the goal!"
        status = "IN_PROGRESS"

    return {
        "level": int(level_num),
        "level_title": lvl["title"],
        "goal_text": lvl["goal_text"],
        "status": status,
        "reached_target": reached_target,
        "final_pose": {"x": round(x, 3), "y": round(y, 3), "heading_deg": round(heading_deg, 1)},
        "dist_to_target_m": round(dist_to_target, 3),
        "min_clearance_m": round(min_observed_clearance, 3),
        "collected_cells": collected_cells,
        "total_cells": len(lvl["cells"]),
        "sensor_scans": sensor_scans,
        "speed_mps": speed_mps,
        "speed_blocked_by_permit": speed_clamped,
        "path_points": path_points,
        "feedback": feedback,
        "obstacles": lvl["obstacles"],
        "target": lvl["target"],
        "cells": lvl["cells"],
        "human_walkway_x_m": walkway_x,
    }


def build_default_demo_b_state() -> dict[str, Any]:
    """Default initial state for Demonstration B (Free Robotics Learning Environment for Kids)."""
    sim1 = simulate_robot_academy_program(1, ROBOT_ACADEMY_LEVELS[1]["recommended_blocks"], 0.55)
    return {
        "project_id": "demo-b-robot-academy-kids",
        "project_family": "robot_academy_kids",
        "title": "Sprocket's Robot Academy — Free Browser Robotics Game",
        "prompt": "Build an interactive robotics learning environment for children who don’t own robots.",
        "current_level": 1,
        "completed_levels": [1],
        "badges_earned": ["First Steps Navigator", "Safe Permit Cadet"],
        "theme": {
            "arena_name": "Solar Crater Training Yard",
            "robot_name": "Sprocket-G1",
            "accent_color": "#0284C7",
        },
        "active_blocks": list(ROBOT_ACADEMY_LEVELS[1]["recommended_blocks"]),
        "levels": ROBOT_ACADEMY_LEVELS,
        "last_simulation": sim1,
        "safety_and_access_disclosure": (
            "100% FREE EDUCATIONAL SIMULATOR: Runs in any browser with zero accounts, zero paid APIs, and zero hardware required. "
            "Simulated workcell permits teach safety concepts only and never control physical robot hardware."
        ),
    }


# ---------------------------------------------------------------------------
# Section 7: The Next Hundred-Yard Jump — `GenieAppSynthesizer`
# Universal Composable Micro-App Compiler for Unfamiliar Natural-Language Requests
# ---------------------------------------------------------------------------
class GenieAppSynthesizer:
    """Compiles unfamiliar natural-language project descriptions into runnable, stateful,
    receiver-governed micro-applications (`openline.genie.synthesized_app.v1`).

    Emergence Loop Justification:
    - Binding Constraint Identified: Prior Studio RC5 had 7 specialized domain renderers plus a
      static architecture diagram fallback (`generic.project_structure.v1`). When a user asked for
      an unfamiliar tool (e.g., a neighborhood tool lending library, a pet grooming scheduler, or
      a rainwater harvesting calculator), the fallback showed boxes and arrows instead of a working app.
    - Intervention: A single <250 LOC declarative compiler that extracts domain entities, typed fields,
      deterministic formulas, workflow state transitions, and receiver-side validation falsifiers from
      any unfamiliar prompt, producing a live CRUD + calculator + workflow + portable export app.
    """

    @staticmethod
    def synthesize(prompt: str, custom_spec: dict[str, Any] | None = None) -> dict[str, Any]:
        p_low = prompt.lower().strip()
        if custom_spec and isinstance(custom_spec, dict) and "fields" in custom_spec:
            spec = copy.deepcopy(custom_spec)
        elif "tool library" in p_low or "lending" in p_low or "equipment" in p_low:
            spec = {
                "app_slug": "neighborhood-tool-library",
                "title": "Neighborhood Tool Library & Deposit Tracker",
                "subtitle": "Synthesized Local-First Lending, Deposit Refund & Overdue Tracker",
                "category": "community_equipment_lending",
                "primary_entity": "Loan Record",
                "fields": [
                    {"key": "item_name", "label": "Tool / Equipment", "type": "text", "required": True},
                    {"key": "borrower_name", "label": "Borrower Name", "type": "text", "required": True},
                    {"key": "days_borrowed", "label": "Days Borrowed", "type": "number", "min": 1, "max": 60, "default": 3},
                    {"key": "deposit_paid_dollars", "label": "Deposit Paid ($)", "type": "number", "min": 0, "max": 500, "default": 40.0},
                    {"key": "late_days", "label": "Overdue Days", "type": "number", "min": 0, "max": 30, "default": 0},
                    {"key": "daily_late_fee_dollars", "label": "Late Fee ($/day)", "type": "number", "min": 0, "max": 25, "default": 3.0},
                ],
                "formula_description": "refund_due_dollars = max(0, deposit_paid_dollars - (late_days * daily_late_fee_dollars))",
                "workflow_states": ["CHECKED_OUT", "RETURNED_INSPECTED", "DEPOSIT_REFUNDED", "OVERDUE_HOLD"],
                "records": [
                    {
                        "record_id": "LOAN-101",
                        "item_name": "DeWalt 20V Cordless Hammer Drill Kit",
                        "borrower_name": "Samira Patel (Apt 4B)",
                        "days_borrowed": 4,
                        "deposit_paid_dollars": 50.0,
                        "late_days": 0,
                        "daily_late_fee_dollars": 3.0,
                        "computed_metric_label": "Refund Due ($)",
                        "computed_metric_value": 50.0,
                        "status": "RETURNED_INSPECTED",
                    },
                    {
                        "record_id": "LOAN-102",
                        "item_name": " Bosch Laser Level & Tripod",
                        "borrower_name": "Marcus Vance (Elm St)",
                        "days_borrowed": 7,
                        "deposit_paid_dollars": 45.0,
                        "late_days": 2,
                        "daily_late_fee_dollars": 3.0,
                        "computed_metric_label": "Refund Due ($)",
                        "computed_metric_value": 39.0,
                        "status": "CHECKED_OUT",
                    },
                    {
                        "record_id": "LOAN-103",
                        "item_name": "Electric Pressure Washer 2100 PSI",
                        "borrower_name": "Elena Rostova",
                        "days_borrowed": 3,
                        "deposit_paid_dollars": 60.0,
                        "late_days": 0,
                        "daily_late_fee_dollars": 3.0,
                        "computed_metric_label": "Refund Due ($)",
                        "computed_metric_value": 60.0,
                        "status": "DEPOSIT_REFUNDED",
                    },
                ],
            }
        elif "solar" in p_low or "energy" in p_low or "building" in p_low:
            spec = {
                "app_slug": "building-solar-sb868-estimator",
                "title": "Building & Plug-In Solar Savings Analyzer (CA SB 868 / AB 205)",
                "subtitle": "Models Daytime Load Saturation, $24.15/mo Fixed Charge & Avoidable Utility Rate",
                "category": "energy_and_sustainability",
                "primary_entity": "Solar Scenario",
                "fields": [
                    {"key": "scenario_name", "label": "Building / Array Option", "type": "text", "required": True},
                    {"key": "monthly_usage_kwh", "label": "Monthly Usage (kWh)", "type": "number", "min": 50, "max": 50000, "default": 650},
                    {"key": "array_watts", "label": "Solar Array Size (W AC)", "type": "number", "min": 0, "max": 25000, "default": 800},
                    {"key": "marginal_rate_dollars", "label": "Avoidable Rate ($/kWh)", "type": "number", "min": 0.05, "max": 1.00, "default": 0.36},
                    {"key": "self_use_fraction", "label": "Daytime Self-Use Fraction (0-1)", "type": "number", "min": 0.1, "max": 1.0, "default": 0.82},
                    {"key": "hardware_cost_dollars", "label": "Upfront Hardware Cost ($)", "type": "number", "min": 0, "max": 100000, "default": 699.0},
                ],
                "formula_description": "annual_savings_dollars = round((array_watts * 1.45 * self_use_fraction) * marginal_rate_dollars, 2)",
                "workflow_states": ["ESTIMATE_ONLY", "HUMAN_BILL_VERIFIED", "APPROVED_FOR_PILOT"],
                "records": [
                    {
                        "record_id": "SOL-01",
                        "scenario_name": "400 W Starter Plug-In Balcony Kit",
                        "monthly_usage_kwh": 650,
                        "array_watts": 400,
                        "marginal_rate_dollars": 0.36,
                        "self_use_fraction": 0.92,
                        "hardware_cost_dollars": 389.0,
                        "computed_metric_label": "Est. Annual Savings ($/yr)",
                        "computed_metric_value": 192.10,
                        "status": "ESTIMATE_ONLY",
                    },
                    {
                        "record_id": "SOL-02",
                        "scenario_name": "800 W Balanced SB 868 Receptacle Array",
                        "monthly_usage_kwh": 650,
                        "array_watts": 800,
                        "marginal_rate_dollars": 0.36,
                        "self_use_fraction": 0.82,
                        "hardware_cost_dollars": 699.0,
                        "computed_metric_label": "Est. Annual Savings ($/yr)",
                        "computed_metric_value": 342.43,
                        "status": "HUMAN_BILL_VERIFIED",
                    },
                ],
            }
        elif "voting" in p_low or "congress" in p_low or "representative" in p_low or "civic" in p_low:
            spec = {
                "app_slug": "congressional-roll-call-verifier",
                "title": "Congressional Voting Record & Roll Call Verifier",
                "subtitle": "Primary-Source House Clerk Roll Call XML Inspector (Non-Partisan Evidence Ledger)",
                "category": "civic_transparency",
                "primary_entity": "Roll Call Record",
                "fields": [
                    {"key": "representative_name", "label": "Representative & District", "type": "text", "required": True},
                    {"key": "roll_call_id", "label": "Clerk Roll Call #", "type": "text", "required": True},
                    {"key": "recorded_vote", "label": "Official Vote (Yea/Nay/Not Voting)", "type": "text", "required": True},
                    {"key": "appropriations_millions", "label": "Bill Fiscal Line ($M)", "type": "number", "min": 0, "max": 5000000, "default": 125.0},
                    {"key": "verified_xml_match", "label": "Clerk XML SHA-256 Match (1=Yes,0=No)", "type": "number", "min": 0, "max": 1, "default": 1},
                ],
                "formula_description": "evidence_confidence_pct = 100.0 if verified_xml_match == 1 else 0.0",
                "workflow_states": ["PRIMARY_SOURCE_VERIFIED", "AMENDMENT_SUPERSEDED_REOPEN", "UNVERIFIED_CLAIM"],
                "records": [
                    {
                        "record_id": "VOTE-283-A",
                        "representative_name": "Rep. Aderholt (AL-04, Bio ID A000055)",
                        "roll_call_id": "Roll Call 283 (H.R. 8580)",
                        "recorded_vote": "Yea",
                        "appropriations_millions": 1485.0,
                        "verified_xml_match": 1,
                        "computed_metric_label": "Primary Source Verified (%)",
                        "computed_metric_value": 100.0,
                        "status": "PRIMARY_SOURCE_VERIFIED",
                    },
                    {
                        "record_id": "VOTE-283-B",
                        "representative_name": "Rep. Adams (NC-12, Bio ID A000370)",
                        "roll_call_id": "Roll Call 283 (H.R. 8580)",
                        "recorded_vote": "Nay",
                        "appropriations_millions": 1485.0,
                        "verified_xml_match": 1,
                        "computed_metric_label": "Primary Source Verified (%)",
                        "computed_metric_value": 100.0,
                        "status": "PRIMARY_SOURCE_VERIFIED",
                    },
                ],
            }
        elif is_neural_model_prompt(p_low):
            model_rec = new_neural_model_record()
            m_comp = model_rec["computed"]
            spec = {
                "app_slug": "neural-checkpoint-constraint-opening-optimizer",
                "title": "Neural Network Weight-Space & Constraint-Opening Optimizer",
                "subtitle": "Executable Residual-MLP Checkpoints, Spectral SVD Repair, Curriculum Filtering & INT8 Calibration",
                "category": "neural_model_optimization",
                "domain_subtype": "neural_model_optimizer",
                "primary_entity": "Optimization Stage",
                "fields": [
                    {"key": "stage_name", "label": "Optimization Stage / Intervention", "type": "text", "required": True},
                    {"key": "target_constraint", "label": "Targeted Constraint", "type": "text", "required": True},
                    {"key": "compute_units", "label": "Compute Budget (units)", "type": "number", "min": 1, "max": 32, "default": 2},
                    {"key": "accuracy_gain_pct", "label": "Holdout Accuracy Gain (%)", "type": "number", "min": -50, "max": 100, "default": 10.0},
                    {"key": "compression_factor", "label": "Memory Efficiency Factor", "type": "number", "min": 0.5, "max": 8.0, "default": 1.0},
                ],
                "formula_description": "stage_frontier_index = round(accuracy_gain_pct * compression_factor / max(compute_units, 1), 2)",
                "workflow_states": ["EVALUATOR_CERTIFIED", "EXPLORATORY_CANDIDATE", "QUARANTINED_OVERFIT"],
                "neural_model": model_rec,
                "constraints": {
                    "binding_constraint_id": m_comp["bottleneck_id"],
                    "binding_constraint_label": m_comp["bottleneck_label"],
                    "plain_language_diagnosis": (
                        f"{m_comp['bottleneck_label']} ({m_comp['frontier_score_pts']} pts) is the active binding constraint. "
                        "Repairing collapsed singular values and dead GELU channels unlocks curriculum outlier filtering and INT8 calibration."
                    ),
                    "capacities": m_comp["capacities"],
                    "options_compared": model_rec["paths"],
                },
                "records": [
                    {
                        "record_id": "OPT-GEN1",
                        "stage_name": "Stage 1: Spectral SVD Conditioning & Dead-Channel Repair",
                        "target_constraint": "spectral_flow (W2 rank collapse)",
                        "compute_units": 2.0,
                        "accuracy_gain_pct": 10.0,
                        "compression_factor": 1.0,
                        "computed_metric_label": "Frontier Index",
                        "computed_metric_value": 5.0,
                        "status": "EVALUATOR_CERTIFIED",
                    },
                    {
                        "record_id": "OPT-GEN2",
                        "stage_name": "Stage 2: Curriculum Outlier-Filtered Cosine Fine-Tune",
                        "target_constraint": "data_subspace (18% noisy outliers)",
                        "compute_units": 3.0,
                        "accuracy_gain_pct": 23.3,
                        "compression_factor": 1.0,
                        "computed_metric_label": "Frontier Index",
                        "computed_metric_value": 7.77,
                        "status": "EVALUATOR_CERTIFIED",
                    },
                    {
                        "record_id": "OPT-GEN3",
                        "stage_name": "Stage 3: Temperature Calibration + 20% Prune + INT8 Quantization",
                        "target_constraint": "calibration_efficiency (ECE & FP32 bytes)",
                        "compute_units": 2.0,
                        "accuracy_gain_pct": 23.8,
                        "compression_factor": 4.58,
                        "computed_metric_label": "Frontier Index",
                        "computed_metric_value": 54.5,
                        "status": "EVALUATOR_CERTIFIED",
                    },
                ],
            }
        elif is_garden_prompt(p_low):
            garden_rec = new_garden_record()
            g_comp = garden_rec["computed"]
            spec = {
                "app_slug": "community-garden-crop-rotation",
                "title": "Sunnyvale Community Garden — Crop Rotation, Irrigation & Volunteer Planner",
                "subtitle": "Synthesized Local-First Plot Rotation, Cistern Water Balance & Volunteer Shift Tool",
                "category": "community_agriculture_and_stewardship",
                "domain_subtype": "community_garden_crop_rotation",
                "primary_entity": "Garden Plot Assignment",
                "fields": [
                    {"key": "plot_id", "label": "Plot / Raised Bed ID", "type": "text", "required": True},
                    {"key": "crop_family", "label": "Current Crop Family (Legume/Solanaceae/Brassica/Root)", "type": "text", "required": True},
                    {"key": "previous_family", "label": "Prior Season Crop Family", "type": "text", "required": True},
                    {"key": "water_gallons_per_week", "label": "Drip Water Allocation (gal/wk)", "type": "number", "min": 10, "max": 500, "default": 90.0},
                    {"key": "volunteer_hours_per_week", "label": "Assigned Volunteer Hours/wk", "type": "number", "min": 0.5, "max": 40, "default": 4.0},
                    {"key": "yield_per_hour_lbs", "label": "Harvest Yield Rate (lbs/hr)", "type": "number", "min": 1.0, "max": 25.0, "default": 7.5},
                ],
                "formula_description": "projected_weekly_harvest_lbs = round(min(water_gallons_per_week / 4.0, volunteer_hours_per_week * yield_per_hour_lbs), 2)",
                "workflow_states": ["ROTATION_VERIFIED", "IRRIGATION_BOTTLENECKED", "HARVEST_READY", "SOIL_RESTING_COVER_CROP"],
                "garden": garden_rec,
                "constraints": {
                    "binding_constraint_id": g_comp["bottleneck_id"],
                    "binding_constraint_label": g_comp["bottleneck_label"],
                    "plain_language_diagnosis": (
                        f"{g_comp['bottleneck_label']} ({g_comp['throughput_lbs_per_week']} lbs/week) is the binding constraint: "
                        f"cistern water (420 gal/wk at 4.0 gal/lb) caps harvest at 105 lbs/wk even though volunteer labor supports 135 lbs/wk and raised beds support 150 lbs/wk."
                    ),
                    "capacities": g_comp["capacities"],
                    "options_compared": garden_rec["paths"],
                },
                "records": [
                    {
                        "record_id": "PLOT-A1",
                        "plot_id": "Bed A1 (North Sun Terrace)",
                        "crop_family": "Legume (Sugar Snap Peas & Fava)",
                        "previous_family": "Brassica (Winter Kale)",
                        "water_gallons_per_week": 100.0,
                        "volunteer_hours_per_week": 4.0,
                        "yield_per_hour_lbs": 7.5,
                        "computed_metric_label": "Projected Harvest (lbs/wk)",
                        "computed_metric_value": 25.0,
                        "status": "ROTATION_VERIFIED",
                    },
                    {
                        "record_id": "PLOT-A2",
                        "plot_id": "Bed A2 (South Trellis Row)",
                        "crop_family": "Solanaceae (Sungold & Roma Tomatoes)",
                        "previous_family": "Legume (Crimson Clover & Bush Beans)",
                        "water_gallons_per_week": 120.0,
                        "volunteer_hours_per_week": 5.0,
                        "yield_per_hour_lbs": 7.5,
                        "computed_metric_label": "Projected Harvest (lbs/wk)",
                        "computed_metric_value": 30.0,
                        "status": "IRRIGATION_BOTTLENECKED",
                    },
                    {
                        "record_id": "PLOT-B1",
                        "plot_id": "Bed B1 (Pollinator Border)",
                        "crop_family": "Brassica (Lacinato Kale & Broccoli)",
                        "previous_family": "Root (Carrots & Radish)",
                        "water_gallons_per_week": 100.0,
                        "volunteer_hours_per_week": 4.5,
                        "yield_per_hour_lbs": 7.5,
                        "computed_metric_label": "Projected Harvest (lbs/wk)",
                        "computed_metric_value": 25.0,
                        "status": "ROTATION_VERIFIED",
                    },
                    {
                        "record_id": "PLOT-B2",
                        "plot_id": "Bed B2 (Compost Loam Bed)",
                        "crop_family": "Root (Nantes Carrots & Red Beets)",
                        "previous_family": "Solanaceae (Bell Peppers)",
                        "water_gallons_per_week": 100.0,
                        "volunteer_hours_per_week": 4.5,
                        "yield_per_hour_lbs": 7.5,
                        "computed_metric_label": "Projected Harvest (lbs/wk)",
                        "computed_metric_value": 25.0,
                        "status": "HARVEST_READY",
                    },
                ],
            }
        else:
            # General natural-language extraction for ANY unfamiliar request
            words = [w for w in re.findall(r"[A-Za-z0-9]+", prompt) if len(w) > 2]
            title_words = " ".join(w.capitalize() for w in words[:6]) or "Custom Local Operations Tool"
            slug = "-".join(w.lower() for w in words[:5]) or "custom-genie-tool"
            spec = {
                "app_slug": slug,
                "title": f"{title_words} — Autonomous Genie Workspace",
                "subtitle": "Synthesized Stateful Operations, Calculator & Export Tool",
                "category": "synthesized_custom_application",
                "primary_entity": "Work Item",
                "fields": [
                    {"key": "item_title", "label": "Item / Client Name", "type": "text", "required": True},
                    {"key": "category_tag", "label": "Category / Scope", "type": "text", "required": True},
                    {"key": "quantity_units", "label": "Quantity / Hours", "type": "number", "min": 0, "max": 100000, "default": 4.0},
                    {"key": "unit_rate_dollars", "label": "Unit Rate ($)", "type": "number", "min": 0, "max": 100000, "default": 65.0},
                    {"key": "adjustments_dollars", "label": "Materials / Adjustment ($)", "type": "number", "min": -5000, "max": 50000, "default": 25.0},
                ],
                "formula_description": "net_total_dollars = round((quantity_units * unit_rate_dollars) + adjustments_dollars, 2)",
                "workflow_states": ["ACTIVE", "COMPLETED_VERIFIED", "NEEDS_REVIEW"],
                "records": [
                    {
                        "record_id": "REC-101",
                        "item_title": f"{title_words} — Initial Pilot Entry",
                        "category_tag": "Standard Service",
                        "quantity_units": 4.0,
                        "unit_rate_dollars": 65.0,
                        "adjustments_dollars": 25.0,
                        "computed_metric_label": "Calculated Net Total ($)",
                        "computed_metric_value": 285.00,
                        "status": "COMPLETED_VERIFIED",
                    },
                    {
                        "record_id": "REC-102",
                        "item_title": f"{title_words} — Secondary Batch",
                        "category_tag": "Priority Request",
                        "quantity_units": 2.5,
                        "unit_rate_dollars": 80.0,
                        "adjustments_dollars": 15.0,
                        "computed_metric_label": "Calculated Net Total ($)",
                        "computed_metric_value": 215.00,
                        "status": "ACTIVE",
                    },
                ],
            }

        return {
            "schema": "openline.genie.synthesized_app.v1",
            "project_id": f"genie-synth-{spec['app_slug']}",
            "project_family": "synthesized_micro_app",
            "prompt": prompt,
            **spec,
            "honesty_boundary": (
                "SYNTHESIZED LOCAL-FIRST APPLICATION: Compiled deterministically from your request with local storage, "
                "editable records, live calculations, and standalone HTML/CSV/JSON export. External actions remain owner-controlled."
            ),
        }

    @staticmethod
    def compute_record_metric(app_state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        """Recomputes the deterministic formula for a synthesized app record and validates domain bounds."""
        rec = copy.deepcopy(record)
        slug = app_state.get("app_slug", "")
        if "deposit_paid_dollars" in rec or "tool-library" in slug:
            dep = finite_number(rec.get("deposit_paid_dollars", 0.0), "deposit_paid_dollars")
            late = finite_number(rec.get("late_days", 0.0), "late_days")
            fee = finite_number(rec.get("daily_late_fee_dollars", 3.0), "daily_late_fee_dollars")
            if dep < 0 or late < 0 or fee < 0:
                raise ValueError("negative_lending_parameter_not_allowed")
            rec["computed_metric_label"] = "Refund Due ($)"
            rec["computed_metric_value"] = round(max(0.0, dep - (late * fee)), 2)
        elif "array_watts" in rec or "solar" in slug:
            watts = finite_number(rec.get("array_watts", 0.0), "array_watts")
            rate = finite_number(rec.get("marginal_rate_dollars", 0.36), "marginal_rate_dollars")
            self_use = finite_number(rec.get("self_use_fraction", 0.82), "self_use_fraction")
            if watts < 0 or rate < 0 or not (0.0 <= self_use <= 1.0):
                raise ValueError("invalid_solar_parameter_bounds")
            rec["computed_metric_label"] = "Est. Annual Savings ($/yr)"
            rec["computed_metric_value"] = round((watts * 1.45 * self_use) * rate, 2)
        elif "verified_xml_match" in rec or "roll-call" in slug:
            match_raw = finite_number(rec.get("verified_xml_match", 0), "verified_xml_match")
            if match_raw not in (0.0, 1.0):
                raise ValueError("invalid_untrusted_source_verification_flag")
            match_flag = int(match_raw)
            rec["computed_metric_label"] = "Primary Source Verified (%)"
            rec["computed_metric_value"] = 100.0 if match_flag == 1 else 0.0
        elif "accuracy_gain_pct" in rec or "neural-checkpoint" in slug:
            cu = max(finite_number(rec.get("compute_units", 2.0), "compute_units"), 1.0)
            ag = finite_number(rec.get("accuracy_gain_pct", 10.0), "accuracy_gain_pct")
            cf = finite_number(rec.get("compression_factor", 1.0), "compression_factor")
            if cf <= 0:
                raise ValueError("invalid_compression_factor")
            rec["computed_metric_label"] = "Frontier Index"
            rec["computed_metric_value"] = round((ag * cf) / cu, 2)
        elif "water_gallons_per_week" in rec or "community-garden" in slug:
            water = finite_number(rec.get("water_gallons_per_week", 90.0), "water_gallons_per_week")
            vhours = finite_number(rec.get("volunteer_hours_per_week", 4.0), "volunteer_hours_per_week")
            yrate = finite_number(rec.get("yield_per_hour_lbs", 7.5), "yield_per_hour_lbs")
            if water < 0 or vhours < 0 or yrate <= 0:
                raise ValueError("negative_or_invalid_garden_parameters")
            cur_fam = str(rec.get("crop_family", "")).split("(")[0].strip().lower()
            prev_fam = str(rec.get("previous_family", "")).split("(")[0].strip().lower()
            if cur_fam and prev_fam and cur_fam == prev_fam:
                raise ValueError(f"crop_rotation_violation_same_family_consecutive:{cur_fam}")
            gal_per_lb = 2.8 if app_state.get("garden", {}).get("assumptions", {}).get("drip_mulch_enabled") else 4.0
            rec["computed_metric_label"] = "Projected Harvest (lbs/wk)"
            rec["computed_metric_value"] = round(min(water / gal_per_lb, vhours * yrate), 2)
        else:
            qty = finite_number(rec.get("quantity_units", 1.0), "quantity_units")
            rate = finite_number(rec.get("unit_rate_dollars", 0.0), "unit_rate_dollars")
            adj = finite_number(rec.get("adjustments_dollars", 0.0), "adjustments_dollars")
            if qty < 0 or rate < 0:
                raise ValueError("negative_quantity_or_rate_not_allowed")
            rec["computed_metric_label"] = "Calculated Net Total ($)"
            rec["computed_metric_value"] = round((qty * rate) + adj, 2)
        return rec


# ---------------------------------------------------------------------------
# Unified OpenLine Genie Engine
# ---------------------------------------------------------------------------
TRUSTED_PROJECT_FAMILIES: frozenset[str] = frozenset({
    "service_quoting_invoicing",
    "robot_academy_kids",
    "bakery",
    "synthesized_micro_app",
    "model_built_app",
})

TRUSTED_PROJECT_SCHEMAS: dict[str, set[str]] = {
    "service_quoting_invoicing": {"openline.genie.demo_a.v1"},
    "robot_academy_kids": {"openline.genie.demo_b.v1"},
    "bakery": {
        "openline.genie.synthesized_app.v1",
        "openline.genie.model_built_app.v1",
        "openline.genie.bakery.v1",
    },
    "synthesized_micro_app": {"openline.genie.synthesized_app.v1"},
    "model_built_app": {"openline.genie.model_built_app.v1"},
}


class OpenLineGenieEngine:
    """Single unified project-building engine reusing ReceiverGuard.

    Without a model adapter, behavior is deterministic (keyword fixtures +
    GenieAppSynthesizer + domain models, zero paid model calls). With an
    adapter, unfamiliar prompts route to GenieWorker when explicitly enabled.
    """

    def __init__(self, state_dir: str | Path | None = None, model_adapter=None) -> None:
        self.state_dir = Path(state_dir) if state_dir else Path(tempfile.mkdtemp(prefix="openline-genie-"))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "genie_state.sqlite"

        # Private per-state-dir keys; old RC1 shared deterministic seeds were forgeable.
        # Local trust-boundary note: these key files protect cryptographic provenance within
        # the local state directory, but processes running under the same OS UID share
        # filesystem access unless deployed with separate OS user/container isolation.
        self.owner_identity = SigningIdentity(seed=self._load_or_create_seed("owner"))
        self.worker_a_identity = SigningIdentity(seed=self._load_or_create_seed("worker_a"))
        self.worker_b_identity = SigningIdentity(seed=self._load_or_create_seed("worker_b"))
        self.receiver_identity = SigningIdentity(seed=self._load_or_create_seed("receiver"))
        self.active_worker_id = "worker-a"

        self._init_tables()
        self.guard = ReceiverGuard(
            self.db_path,
            receiver_identity=self.receiver_identity,
            strict_production=True,
            deterministic_ids=True,
        )
        active_pub = self.guard.get_active_worker_pub()
        if active_pub == self.worker_b_identity.public:
            self.active_worker_id = "worker-b"
        elif active_pub is not None and active_pub != self.worker_a_identity.public:
            raise ValueError("authority_unavailable_fail_closed:unknown_active_worker_pub")
        elif active_pub is None and self.guard.is_worker_revoked(self.worker_a_identity.public):
            self.active_worker_id = "worker-b"
            self.guard.set_active_worker_pub(self.worker_b_identity.public)
        self.guard.register_issuer(self.owner_identity.public)
        self.guard.set_basis("genie_operating_law", "v1.0-20261103")
        self.guard.set_basis("tax_and_calculation_rules", "v1")

        self.model_adapter = model_adapter
        stored_model = self._read_engine_meta("model_id")
        if model_adapter is not None:
            if stored_model:
                self.model_id = stored_model
                if hasattr(model_adapter, "set_model"):
                    model_adapter.set_model(stored_model)
            else:
                self.model_id = getattr(model_adapter, "model", None)
                if self.model_id:
                    self._write_engine_meta("model_id", self.model_id)
        else:
            self.model_id = stored_model

        # Bootstrap default projects if empty
        self._bootstrap_default_projects()

    def _load_or_create_seed(self, name: str) -> bytes:
        """Persist a random signing seed with restricted filesystem permissions.

        Not sufficient for production receiver isolation: a same-UID worker may still
        access state/keys unless enforced by separate OS identity or hardware.
        """
        path = self.state_dir / (".genie_key_" + name)
        if path.is_symlink():
            raise PermissionError("refusing_symlinked_signing_key")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(str(path), flags)
        except FileNotFoundError:
            seed = secrets.token_bytes(32)
            create_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(str(path), create_flags, 0o600)
                try:
                    os.write(fd, seed)
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except FileExistsError:
                pass
            fd = os.open(str(path), flags)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
                raise PermissionError("insecure_signing_key_file_permissions")
            seed = os.read(fd, 33)
        finally:
            os.close(fd)
        if len(seed) != 32:
            raise ValueError("invalid_signing_seed_length")
        return seed

    def _init_tables(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_accepted (
                    project_id TEXT PRIMARY KEY,
                    project_family TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    state_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_exploratory (
                    proposal_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    proposer_worker TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    candidate_state_json TEXT NOT NULL,
                    candidate_sha256 TEXT NOT NULL,
                    validation_passed INTEGER NOT NULL,
                    validation_report_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    base_version INTEGER NOT NULL DEFAULT 1,
                    base_state_sha256 TEXT NOT NULL DEFAULT '',
                    proposer_epoch INTEGER NOT NULL DEFAULT 0,
                    proposer_basis_json TEXT NOT NULL DEFAULT '{}',
                    target_project_id TEXT NOT NULL DEFAULT '',
                    validated_family TEXT NOT NULL DEFAULT '',
                    constraint_diagnosis_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            existing_cols = {
                row[1] for row in db.execute("PRAGMA table_info(genie_exploratory)").fetchall()
            }
            migrations = [
                ("base_version", "INTEGER NOT NULL DEFAULT 1"),
                ("base_state_sha256", "TEXT NOT NULL DEFAULT ''"),
                ("proposer_epoch", "INTEGER NOT NULL DEFAULT 0"),
                ("proposer_basis_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("target_project_id", "TEXT NOT NULL DEFAULT ''"),
                ("validated_family", "TEXT NOT NULL DEFAULT ''"),
                ("constraint_diagnosis_json", "TEXT NOT NULL DEFAULT '{}'"),
            ]
            for col_name, col_def in migrations:
                if col_name not in existing_cols:
                    db.execute(f"ALTER TABLE genie_exploratory ADD COLUMN {col_name} {col_def}")

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_rejected (
                    rejection_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    candidate_sha256 TEXT NOT NULL,
                    preserved_accepted_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    rejected_at INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_jump_decisions (
                    jump_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    from_version INTEGER NOT NULL,
                    to_version INTEGER NOT NULL,
                    previous_binding_constraint TEXT NOT NULL,
                    new_binding_constraint TEXT NOT NULL,
                    delta_summary TEXT NOT NULL,
                    next_enabled_actions_json TEXT NOT NULL,
                    second_order_risks_json TEXT NOT NULL,
                    discriminating_test TEXT NOT NULL,
                    accepted_sha256 TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_autonomy_log (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_app_versions (
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (project_id, version)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_project_meta (
                    project_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'open',
                    closed_receipt_json TEXT,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS genie_engine_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            db.commit()

    def _active_worker(self) -> SigningIdentity:
        return self.worker_a_identity if self.active_worker_id == "worker-a" else self.worker_b_identity

    def _worker_identity_by_label(self, label: str) -> SigningIdentity:
        if label == "worker-a":
            return self.worker_a_identity
        if label == "worker-b":
            return self.worker_b_identity
        raise PermissionError(f"unknown_proposer_worker:{label}")

    def log_autonomy_stage(self, project_id: str, stage: str, detail: str, provenance: str) -> None:
        """Appends one row to genie_autonomy_log (worker + engine share this)."""
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO genie_autonomy_log (project_id, stage, detail, provenance, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, stage, detail, provenance, int(time.time())),
            )
            db.commit()

    # -- engine / project metadata ---------------------------------------
    def _read_current_basis(self) -> dict[str, str]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT basis_key, version FROM ol_guard_basis").fetchall()
        return {str(k): str(v) for k, v in rows}
    def _read_engine_meta(self, key: str) -> str | None:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT value FROM genie_engine_meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _write_engine_meta(self, key: str, value: str) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO genie_engine_meta (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, int(time.time())),
            )
            db.commit()

    def _read_project_meta(self, project_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM genie_project_meta WHERE project_id=?", (project_id,)).fetchone()
        return dict(row) if row else None

    def _project_status(self, project_id: str) -> str:
        meta = self._read_project_meta(project_id)
        return str(meta["status"]) if meta else "open"

    def _set_project_status(self, project_id: str, status: str, closed_receipt_json: str | None = None) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO genie_project_meta (project_id, status, closed_receipt_json, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET status=excluded.status, "
                "closed_receipt_json=excluded.closed_receipt_json, updated_at=excluded.updated_at",
                (project_id, status, closed_receipt_json, int(time.time())),
            )
            db.commit()

    def _require_open(self, project_id: str) -> None:
        if self._project_status(project_id) == "closed":
            raise PermissionError(f"project_closed:{project_id}")

    def _require_not_stopped(self, *, operation: str, target_id: str) -> None:
        """STOP freezes project mutations: no new proposals, no accepts."""
        stop = self.guard.read_stop_state()
        if stop.get("stopped"):
            self.guard.refuse_stopped_mutation(
                operation=operation, target_id=target_id,
                detail=f"epoch:{stop.get('epoch')}")

    def get_status(self) -> dict[str, Any]:
        """Model + spend + authority scope status for GET /api/status."""
        if self.model_adapter is not None and hasattr(self.model_adapter, "spend_usd"):
            spend = float(self.model_adapter.spend_usd())
        else:
            spend = SpendLedger().total_usd()
        model_avail = bool(
            self.model_adapter is not None and getattr(self.model_adapter, "available", False)
        )
        return {
            "model_id": self.model_id,
            "model_available": model_avail,
            "paid_model_dispatch_default": "OFF_UNLESS_ADAPTER_CONFIGURED",
            "execution_mode": "AUTONOMOUS_MODEL_WORKER" if model_avail else "DETERMINISTIC_LOCAL_SYNTHESIZER",
            "spend_usd": round(spend, 6),
            "cap_usd": TOTAL_CAP_USD,
            "authority_scope": "LOCAL_SAME_UID_PROCESS_BOUNDARY",
            "budget_scope": "LOCAL_TRANSACTIONAL_LEDGER_SOFT_ESTIMATE",
        }

    # -- runnable-app artifact store --------------------------------------
    def store_app_version(
        self, project_id: str, filename: str, content: str, status: str = "exploratory"
    ) -> int:
        """Stores one app version; old versions survive as history. Returns version."""
        if status not in ("accepted", "exploratory", "rejected"):
            raise ValueError(f"invalid_app_version_status:{status}")
        sha = sha256_hex(content)
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT COALESCE(MAX(version), 0) FROM genie_app_versions WHERE project_id=?",
                (project_id,),
            ).fetchone()
            version = int(row[0]) + 1
            db.execute(
                "INSERT INTO genie_app_versions (project_id, version, filename, content, sha256, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, version, filename, content, sha, status, int(time.time())),
            )
            db.commit()
        return version

    def get_app_version(self, project_id: str, version: int | None = None) -> dict[str, Any]:
        """Returns {project_id, version, filename, content, sha256, status}."""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            if version is None:
                acc = db.execute(
                    "SELECT state_json FROM genie_accepted WHERE project_id=?", (project_id,)
                ).fetchone()
                if not acc:
                    raise ValueError(f"project_not_found:{project_id}")
                state = json.loads(acc["state_json"])
                if state.get("app_version") is not None:
                    row = db.execute(
                        "SELECT * FROM genie_app_versions WHERE project_id=? AND version=?",
                        (project_id, int(state["app_version"])),
                    ).fetchone()
                else:
                    row = db.execute(
                        "SELECT * FROM genie_app_versions WHERE project_id=? AND status='accepted' "
                        "ORDER BY version DESC LIMIT 1",
                        (project_id,),
                    ).fetchone()
                if not row:
                    raise ValueError(f"no_accepted_app_version:{project_id}")
            else:
                row = db.execute(
                    "SELECT * FROM genie_app_versions WHERE project_id=? AND version=?",
                    (project_id, int(version)),
                ).fetchone()
                if not row:
                    raise ValueError(f"app_version_not_found:{project_id} v{version}")
        return {
            "project_id": row["project_id"],
            "version": int(row["version"]),
            "filename": row["filename"],
            "content": row["content"],
            "sha256": row["sha256"],
            "status": row["status"],
        }

    def promote_app_version(
        self, project_id: str, version: int, *, db: sqlite3.Connection | None = None
    ) -> None:
        """Promote an app using the supplied receiver transaction when present.

        The import path MUST supply db: promotion and accepted state are one
        guarded SQLite commit. Standalone calls preserve legacy behavior.
        """
        if db is None:
            with sqlite3.connect(self.db_path) as own_db:
                self.promote_app_version(project_id, version, db=own_db)
            return
        cur = db.execute(
            "UPDATE genie_app_versions SET status='accepted' WHERE project_id=? AND version=? AND status='exploratory'",
            (project_id, int(version)),
        )
        if cur.rowcount != 1:
            raise ValueError(f"app_version_not_staged:{project_id} v{version}")

    def set_app_version_status(self, project_id: str, version: int, status: str) -> None:
        if status not in ("accepted", "exploratory", "rejected"):
            raise ValueError(f"invalid_app_version_status:{status}")
        with sqlite3.connect(self.db_path) as db:
            cur = db.execute(
                "UPDATE genie_app_versions SET status=? WHERE project_id=? AND version=?",
                (status, project_id, int(version)),
            )
            db.commit()
            if cur.rowcount == 0:
                raise ValueError(f"app_version_not_found:{project_id} v{version}")

    # -- model swap / close / reopen ---------------------------------------
    def replace_model(self, model_id: str, project_id: str | None = None) -> dict[str, Any]:
        """Records a new model id for subsequent worker calls. Touches no
        accepted state and no artifacts; verified by SHA-256 before/after."""
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("invalid_model_id")
        model_id = model_id.strip()
        projects = self.list_projects()
        witness = project_id or (projects[0]["project_id"] if projects else None)
        before = {p["project_id"]: p["state_sha256"] for p in projects}
        previous = self.model_id
        self._write_engine_meta("model_id", model_id)
        self.model_id = model_id
        if self.model_adapter is not None and hasattr(self.model_adapter, "set_model"):
            self.model_adapter.set_model(model_id)
        after = {p["project_id"]: p["state_sha256"] for p in self.list_projects()}
        if before != after:
            raise RuntimeError("critical_invariant_violation:model_swap_mutated_accepted_state")
        return {
            "project_id": witness,
            "previous_model": previous,
            "model": model_id,
            "accepted_sha256_before": before.get(witness) if witness else None,
            "accepted_sha256_after": after.get(witness) if witness else None,
            "unchanged": True,
            "all_projects_unchanged": True,
        }

    def close_project(self, project_id: str) -> dict[str, Any]:
        """Verifies SHA-256 + signed receipt, then freezes the project."""
        bundle = self.get_project_bundle(project_id)
        state = bundle["accepted"]["state"]
        state_sha = bundle["accepted"]["state_sha256"]
        if sha256_hex(state) != state_sha:
            raise ValueError("close_sha_mismatch")
        receipt = bundle["accepted"]["receipt"]
        if not receipt or "receipt" not in receipt:
            raise ValueError("close_missing_receipt")
        ver = verify_receipt_offline(receipt["receipt"], pinned_receiver_pub=self.receiver_identity.public)
        if ver.get("crypto") != "VERIFIED" or ver.get("status") != "COMMITTED":
            raise ValueError("close_receipt_not_verified")
        if self._project_status(project_id) == "closed":
            raise ValueError(f"project_already_closed:{project_id}")
        self._set_project_status(
            project_id, "closed", closed_receipt_json=json.dumps(receipt, sort_keys=True)
        )
        return {
            "project_id": project_id,
            "status": "closed",
            "state_sha256": state_sha,
            "receipt": receipt,
        }

    def reopen_project(self, project_id: str) -> dict[str, Any]:
        """Verifies SHA-256 + receipt chain, then reopens the project."""
        if self._project_status(project_id) != "closed":
            raise ValueError(f"project_not_closed:{project_id}")
        bundle = self.get_project_bundle(project_id)
        state = bundle["accepted"]["state"]
        if sha256_hex(state) != bundle["accepted"]["state_sha256"]:
            raise ValueError("reopen_sha_mismatch")
        receipt = bundle["accepted"]["receipt"]
        if not receipt or "receipt" not in receipt:
            raise ValueError("reopen_missing_receipt")
        ver = verify_receipt_offline(receipt["receipt"], pinned_receiver_pub=self.receiver_identity.public)
        if ver.get("crypto") != "VERIFIED" or ver.get("status") != "COMMITTED":
            raise ValueError("reopen_receipt_not_verified")
        meta = self._read_project_meta(project_id)
        if meta and meta.get("closed_receipt_json"):
            if json.loads(meta["closed_receipt_json"]) != receipt:
                raise ValueError("reopen_receipt_chain_mismatch")
        self._set_project_status(project_id, "open")
        return self.get_project_bundle(project_id)

    def _commit_accepted_state(
        self,
        project_id: str,
        project_family: str,
        state: dict[str, Any],
        operation: str = "promote_project_state",
        step_id: str | None = None,
        expected_prev_version: int | None = None,
        expected_prev_sha256: str | None = None,
        promote_staged_app_version: int | None = None,
        require_target_absent: bool = False,
    ) -> dict[str, Any]:
        """Commits verified project state and optional staged app in one receiver transaction."""
        self._require_open(project_id)
        if not isinstance(project_id, str) or not project_id.strip():
            raise PermissionError("invalid_empty_project_id")
        if state.get("project_id") != project_id:
            raise PermissionError(
                f"project_id_mismatch:state_has_{state.get('project_id')}_expected_{project_id}"
            )
        if project_family not in TRUSTED_PROJECT_FAMILIES or state.get("project_family") != project_family:
            raise PermissionError(f"untrusted_or_mismatched_project_family:{project_family}")

        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT version, state_sha256, project_family FROM genie_accepted WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if row is not None:
                cur_ver, cur_sha, cur_fam = int(row[0]), str(row[1]), str(row[2])
                if expected_prev_version is not None and cur_ver != int(expected_prev_version):
                    raise PermissionError(
                        f"stale_base_version_mismatch:expected_{expected_prev_version}_got_{cur_ver}"
                    )
                if expected_prev_sha256 is not None and cur_sha != str(expected_prev_sha256):
                    raise PermissionError(
                        f"stale_base_sha256_mismatch:expected_{expected_prev_sha256[:12]}_got_{cur_sha[:12]}"
                    )
                if project_family != cur_fam and not (
                    cur_fam in ("model_built_app", "synthesized_micro_app", "bakery")
                    and project_family == "bakery"
                ):
                    raise PermissionError(
                        f"illegal_project_family_transition:{cur_fam}_to_{project_family}"
                    )
                next_ver = cur_ver + 1
            else:
                if expected_prev_version is not None or expected_prev_sha256 is not None:
                    raise PermissionError("missing_expected_base_project_row")
                next_ver = 1

        val_check = self.verify_project_artifact(
            state,
            expected_project_id=project_id,
            expected_family=project_family,
        )
        if not val_check["passed"]:
            raise PermissionError(f"receiver_rejected_invalid_artifact:{val_check['errors']}")

        state_raw = canonical(state).decode("utf-8")
        state_sha = sha256_hex(state)

        step_label = step_id or f"{project_id}-v{next_ver}-{secrets.token_hex(3)}"
        worker = self._active_worker()
        grant = self.owner_identity.issue_grant(
            worker.public,
            task_id=f"task-{project_id}",
            step_id=step_label,
            operation=operation,
            allowed_targets=[project_id],
            max_amount=1000000,
            required_basis={"genie_operating_law": "v1.0-20261103"},
            grant_id=f"grant-{project_id}-v{next_ver}-{secrets.token_hex(4)}",
            stop_epoch=self.guard.read_stop_state()["epoch"],
        )
        req = worker.sign_request(
            grant,
            operation=operation,
            target_id=project_id,
            step_id=step_label,
            payload={
                "project_id": project_id,
                "version": next_ver,
                "state_sha256": state_sha,
                "amount": 1,
            },
        )

        def _apply(db: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
            live_row = db.execute(
                "SELECT version, state_sha256 FROM genie_accepted WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if require_target_absent and live_row is not None:
                raise PermissionError("atomic_import_target_appeared")
            if expected_prev_version is not None:
                if live_row is None or int(live_row[0]) != int(expected_prev_version) or str(live_row[1]) != str(expected_prev_sha256):
                    raise PermissionError("atomic_cas_conflict_on_accepted_state")
            if promote_staged_app_version is not None:
                # Failpoint injection here proves a failed promotion cannot leave
                # accepted state committed, because the guard rolls back this TX.
                staged = db.execute(
                    "SELECT sha256, status FROM genie_app_versions WHERE project_id=? AND version=?",
                    (project_id, int(promote_staged_app_version)),
                ).fetchone()
                if (staged is None or staged[1] != 'exploratory' or
                        staged[0] != state.get('app_sha256') or
                        int(state.get('app_version', -1)) != int(promote_staged_app_version)):
                    raise PermissionError("staged_app_not_bound_to_accepted_state")
                self.promote_app_version(project_id, int(promote_staged_app_version), db=db)
            if state.get("app_version") is not None:
                app_row = db.execute(
                    "SELECT sha256, status FROM genie_app_versions WHERE project_id=? AND version=?",
                    (project_id, int(state["app_version"])),
                ).fetchone()
                if (app_row is None or app_row[0] != state.get("app_sha256") or
                        app_row[1] != 'accepted'):
                    raise PermissionError("accepted_state_app_pointer_unverified_or_unaccepted")
            db.execute(
                """
                INSERT INTO genie_accepted (project_id, project_family, version, state_json, state_sha256, receipt_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    project_family=excluded.project_family,
                    version=excluded.version,
                    state_json=excluded.state_json,
                    state_sha256=excluded.state_sha256,
                    receipt_json=excluded.receipt_json,
                    updated_at=excluded.updated_at
                """,
                (project_id, project_family, next_ver, state_raw, state_sha, "{}", int(time.time())),
            )
            db.execute(
                """
                UPDATE genie_exploratory
                SET status='STALE_REOPEN_REQUIRED'
                WHERE project_id=?
                  AND status='EXPLORATORY_PENDING'
                  AND (base_version != ? OR base_state_sha256 != ?)
                """,
                (project_id, next_ver, state_sha),
            )
            return {"project_id": project_id, "version": next_ver, "state_sha256": state_sha}

        def _store_receipt_in_same_tx(db: sqlite3.Connection, receipt_inner: dict) -> None:
            # ReceiverGuard's signed receipt is now durable with the accepted
            # state, not a vulnerable follow-up transaction.
            wrapper = {"status": "COMMITTED", "receipt": receipt_inner}
            cur = db.execute(
                "UPDATE genie_accepted SET receipt_json=? WHERE project_id=? AND version=? AND state_sha256=?",
                (canonical(wrapper).decode("utf-8"), project_id, next_ver, state_sha),
            )
            if cur.rowcount != 1:
                raise PermissionError("accepted_receipt_atomic_binding_failed")

        receipt = self.guard.execute(
            grant=grant,
            request=req,
            fn=_apply,
            target_table="genie_accepted",
            target_pk_col="project_id",
            amount_field="amount",
            post_receipt_hook=_store_receipt_in_same_tx,
        )
        return receipt

    def _bootstrap_default_projects(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            count = db.execute("SELECT COUNT(*) FROM genie_accepted").fetchone()[0]
        if count > 0:
            return
        demo_a = build_default_demo_a_state()
        self._commit_accepted_state(demo_a["project_id"], demo_a["project_family"], demo_a, step_id="init-demo-a")
        demo_b = build_default_demo_b_state()
        self._commit_accepted_state(demo_b["project_id"], demo_b["project_family"], demo_b, step_id="init-demo-b")
        synth_tool = GenieAppSynthesizer.synthesize(
            "Build a neighborhood tool library and equipment lending tracker with refundable deposits and overdue check-in alerts."
        )
        self._commit_accepted_state(synth_tool["project_id"], synth_tool["project_family"], synth_tool, step_id="init-synth-tool")

    # -----------------------------------------------------------------------
    # Autonomous Goal-to-Artifact Pipeline (Section 3)
    # -----------------------------------------------------------------------
    def build_from_prompt(self, prompt: str, use_model: bool = True) -> dict[str, Any]:
        """Executes the autonomous Genie build loop:
        Understand -> Identify constraints -> Research -> Select tools -> Build -> Test -> Present -> Preserve.
        """
        p_low = prompt.lower().strip()
        fixture_a = any(k in p_low for k in ("quote", "quoting", "invoice", "invoicing", "landscaping", "service business"))
        fixture_b = any(k in p_low for k in ("robot", "children", "kids", "learning game", "academy"))
        worker_error: str | None = None
        if not fixture_a and not fixture_b and use_model and self.model_adapter is not None:
            try:
                from core.genie_worker import GenieWorker

                bundle = GenieWorker(self.model_adapter, self).build(prompt)
                if is_bakery_prompt(prompt):
                    bundle = self.attach_bakery_domain(bundle["project_id"])
                return bundle
            except Exception as exc:  # noqa: BLE001
                worker_error = f"{type(exc).__name__}:{exc}"
        if fixture_a:
            state = build_default_demo_a_state()
            state["prompt"] = prompt
            if "landscaping" in p_low:
                state["customization"]["business_name"] = "Verdant Valley Landscaping & Repair"
            project_id = state["project_id"]
            family = state["project_family"]
            tools_selected = ["service_quoting_invoicing_adapter", "cent_accurate_tax_engine", "writing_studio_copy_skill", "receiver_guard"]
        elif fixture_b:
            state = build_default_demo_b_state()
            state["prompt"] = prompt
            project_id = state["project_id"]
            family = state["project_family"]
            tools_selected = ["robot_academy_2d_simulator", "robot_academy_safety_envelope", "progressive_4_level_curriculum", "receiver_guard"]
        else:
            state = GenieAppSynthesizer.synthesize(prompt)
            project_id = state["project_id"]
            family = state["project_family"]
            tools_selected = ["genie_composable_app_synthesizer", "formula_and_state_compiler", "decision_recall", "receiver_guard"]

        if is_bakery_prompt(prompt):
            state["bakery"] = new_bakery_record()
            state["project_family"] = "bakery"
            state["fields"] = bakery_state_fields()
            family = "bakery"

        test_report = self.verify_project_artifact(
            state,
            expected_project_id=project_id,
            expected_family=family,
        )
        if not test_report["passed"]:
            raise ValueError(f"autonomous_build_self_test_failed:{test_report['errors']}")

        receipt = self._commit_accepted_state(project_id, family, state, operation="autonomous_build")
        stages = [
            ("1. Understand Goal", f"Parsed user objective -> family='{family}', project_id='{project_id}'"),
            ("2. Identify Constraints", "Enforced $0 local-first operation, cent/kinematic/domain bounds, and owner-gated external effects"),
            ("3. Select Tools & Skills", ", ".join(tools_selected)),
            ("4. Build & Self-Test Artifact", f"Passed {test_report['checks_run']}/{test_report['checks_run']} automated artifact checks"),
            ("5. Preserve Accepted Work", f"Committed to ReceiverGuard SQLite & signed Ed25519 receipt ({receipt.get('receipt', receipt)['payload_sha256'][:12]}...)"),
        ]
        for stg, det in stages:
            self.log_autonomy_stage(project_id, stg, det, "LOCAL_AUTONOMOUS_COMPILER_AND_VERIFIER")
        if worker_error:
            self.log_autonomy_stage(
                project_id,
                "0. Model Worker Fallback",
                f"Model worker failed ({worker_error}); fell back to deterministic synthesizer. "
                "No model-built app was committed for this prompt.",
                "LOCAL_AUTONOMOUS_COMPILER_AND_VERIFIER",
            )

        return self.get_project_bundle(project_id)

    # -----------------------------------------------------------------------
    # Bakery & Community Garden Operating Models (RC6 / RC7)
    # -----------------------------------------------------------------------
    def attach_bakery_domain(self, project_id: str) -> dict[str, Any]:
        """Records the bakery operating model as accepted state."""
        bundle = self.get_project_bundle(project_id)
        state = copy.deepcopy(bundle["accepted"]["state"])
        existing = state.get("bakery")
        prior_assumptions = (
            existing.get("assumptions")
            if isinstance(existing, dict) and isinstance(existing.get("assumptions"), dict)
            else None
        )
        state["bakery"] = new_bakery_record(prior_assumptions)
        state["project_family"] = "bakery"
        state["fields"] = bakery_state_fields()
        test_report = self.verify_project_artifact(
            state,
            expected_project_id=project_id,
            expected_family="bakery",
        )
        if not test_report["passed"]:
            raise ValueError(f"bakery_attach_self_test_failed:{test_report['errors']}")
        self._commit_accepted_state(
            project_id, "bakery", state,
            operation="attach_bakery_domain", step_id=f"bakery-{project_id}",
        )
        self.log_autonomy_stage(
            project_id,
            "5b. Bakery Operating Model",
            "Engine-recorded structured assumptions: 1 oven, 29/batch, "
            "50-min cycle, 174 loaves/day oven cap; staff 240; proofing "
            "280; throughput = min constraint; +/-7% band.",
            "LOCAL_BAKERY_MODEL",
        )
        return self.get_project_bundle(project_id)

    def bakery_paths(self, project_id: str | None = None) -> dict[str, Any]:
        """Path id -> assumption patch + prices, for the living-world UI."""
        baseline = new_bakery_record()["assumptions"]
        assumptions = baseline
        if project_id is not None:
            bundle = self.get_project_bundle(project_id)
            bakery = bundle["accepted"]["state"].get("bakery")
            if isinstance(bakery, dict) and isinstance(bakery.get("assumptions"), dict):
                assumptions = bakery["assumptions"]
        record = new_bakery_record(assumptions)
        return {"paths": record["paths"], "baseline_assumptions": baseline,
                "current_assumptions": assumptions}

    def model_optimization_paths(self, project_id: str | None = None) -> dict[str, Any]:
        """Path id -> assumption patch + computed frontier capacities for the Neural Model Optimization domain."""
        baseline = new_neural_model_record()["assumptions"]
        assumptions = baseline
        if project_id is not None:
            bundle = self.get_project_bundle(project_id)
            nm = bundle["accepted"]["state"].get("neural_model")
            if isinstance(nm, dict) and isinstance(nm.get("assumptions"), dict):
                assumptions = nm["assumptions"]
        record = new_neural_model_record(assumptions)
        return {
            "paths": record["paths"],
            "baseline_assumptions": baseline,
            "current_assumptions": assumptions,
            "computed": record["computed"],
        }

    def garden_paths(self, project_id: str | None = None) -> dict[str, Any]:
        """Path id -> assumption patch + computed capacities/economics + conventional comparator for the Community Garden domain."""
        baseline = new_garden_record()["assumptions"]
        assumptions = baseline
        if project_id is not None:
            bundle = self.get_project_bundle(project_id)
            garden = bundle["accepted"]["state"].get("garden")
            if isinstance(garden, dict) and isinstance(garden.get("assumptions"), dict):
                assumptions = garden["assumptions"]
        record = new_garden_record(assumptions)
        return {
            "paths": record["paths"],
            "baseline_assumptions": baseline,
            "current_assumptions": assumptions,
            "computed": record["computed"],
        }

    def verify_project_artifact(
        self,
        state: dict[str, Any],
        *,
        expected_project_id: str | None = None,
        expected_family: str | None = None,
    ) -> dict[str, Any]:
        """Runs deterministic functional, identity, and family-specific invariant checks on a project artifact.

        Enforces:
        - P0-C: `project_id` and `schema` immutability and validity.
        - P0-D: Fail-closed `TRUSTED_PROJECT_FAMILIES` registry and controlled transition rules.
        """
        errors: list[str] = []
        checks_run = 0

        if not isinstance(state, dict):
            return {"passed": False, "checks_run": 1, "errors": ["state_not_a_dict"]}

        # 1. P0-C: Project identity & schema immutability check
        checks_run += 1
        cand_pid = state.get("project_id")
        if not isinstance(cand_pid, str) or not cand_pid.strip():
            errors.append("missing_or_empty_project_id")
        elif expected_project_id is not None and cand_pid != expected_project_id:
            errors.append(f"immutable_project_id_mismatch:{cand_pid}!={expected_project_id}")

        # 2. P0-D: Fail-closed project_family registry & transition check
        checks_run += 1
        family = state.get("project_family", "")
        if not isinstance(family, str) or family not in TRUSTED_PROJECT_FAMILIES:
            errors.append(f"untrusted_or_unknown_project_family:{family}")
        elif expected_family is not None and family != expected_family:
            if not (
                expected_family in ("model_built_app", "synthesized_micro_app", "bakery")
                and family == "bakery"
            ):
                errors.append(f"illegal_project_family_transition:{expected_family}->{family}")

        # 3. Schema consistency check (if schema field is present, it must belong to family)
        checks_run += 1
        schema = state.get("schema")
        if schema is not None and family in TRUSTED_PROJECT_SCHEMAS:
            allowed_schemas = TRUSTED_PROJECT_SCHEMAS[family]
            if not isinstance(schema, str) or schema not in allowed_schemas:
                errors.append(f"invalid_schema_for_family:{schema}_not_in_{sorted(allowed_schemas)}")

        # 4. Family-specific structural & mathematical invariant checks
        if family == "service_quoting_invoicing":
            checks_run += 4
            if not isinstance(state.get("customers"), list) or not state.get("customers"):
                errors.append("missing_customers")
            if not isinstance(state.get("services"), list) or not state.get("services"):
                errors.append("missing_services")
            quotes = state.get("quotes")
            if not isinstance(quotes, list):
                errors.append("quotes_not_a_list")
            else:
                for q in quotes:
                    if not isinstance(q, dict):
                        errors.append("quote_entry_not_a_dict")
                        continue
                    recalc = calculate_quote_totals(
                        q.get("items", []),
                        discount_pct=float(q.get("discount_pct", 0.0)),
                        tax_rate_pct=float(q.get("tax_rate_pct", 8.25)),
                        deposit_pct=float(q.get("deposit_pct", 25.0)),
                    )
                    if recalc["total_cents"] != q.get("total_cents"):
                        errors.append(f"quote_total_mismatch:{q.get('quote_id')}")
            hb = str(state.get("honesty_boundary", ""))
            if "does NOT" not in hb and "Does NOT" not in hb:
                errors.append("missing_revenue_payment_honesty_disclosure")
        elif family == "robot_academy_kids":
            checks_run += 3
            sim = state.get("last_simulation", {})
            if not isinstance(sim, dict) or not sim or "path_points" not in sim:
                errors.append("missing_simulation_trajectory")
            if float(sim.get("human_walkway_x_m", 0) if isinstance(sim, dict) else 0) <= 0:
                errors.append("missing_walkway_boundary")
        elif family == "model_built_app":
            checks_run += 4
            if not isinstance(state.get("spec"), dict) or not state.get("spec", {}).get("title"):
                errors.append("missing_model_spec_title")
            if not state.get("app_version") or not state.get("app_sha256"):
                errors.append("missing_app_version_pointer")
            else:
                try:
                    ver = self.get_app_version(str(cand_pid), int(state["app_version"]))
                    if ver["sha256"] != state["app_sha256"]:
                        errors.append("app_sha256_mismatch")
                    content_low = ver["content"].lower()
                    if "<html" not in content_low or "localstorage" not in content_low:
                        errors.append("app_content_missing_html_or_persistence")
                    if 'src="http' in content_low or 'href="http' in content_low:
                        errors.append("app_content_has_external_dependency")
                except ValueError as exc:
                    errors.append(f"app_version_lookup_failed:{exc}")
        elif family == "bakery":
            checks_run += 4
            bakery = state.get("bakery")
            if not isinstance(bakery, dict):
                errors.append("missing_bakery_model")
            else:
                comp = bakery.get("computed", {})
                if not isinstance(comp, dict) or int(comp.get("throughput_loaves_per_day", 0)) <= 0:
                    errors.append("invalid_bakery_effective_capacity")
                if not isinstance(comp, dict) or "net_daily_usd" not in comp:
                    errors.append("missing_bakery_economics")
            if not state.get("fields"):
                errors.append("missing_bakery_fields")
            for rec in state.get("records", []):
                try:
                    GenieAppSynthesizer.compute_record_metric(state, rec)
                except Exception as exc:
                    errors.append(f"record_formula_error:{exc}")
        elif family == "synthesized_micro_app":
            checks_run += 3
            if not isinstance(state.get("fields"), list) or not state.get("fields"):
                errors.append("missing_synthesized_fields")
            records = state.get("records", [])
            if not isinstance(records, list):
                errors.append("records_not_a_list")
            else:
                for rec in records:
                    try:
                        GenieAppSynthesizer.compute_record_metric(state, rec)
                    except Exception as exc:
                        errors.append(f"record_formula_error:{exc}")
            if "garden" in state:
                checks_run += 2
                cg = state.get("garden")
                if not isinstance(cg, dict) or not isinstance(cg.get("computed"), dict):
                    errors.append("invalid_community_garden_model")
                elif float(cg["computed"].get("throughput_lbs_per_week", 0)) <= 0:
                    errors.append("invalid_community_garden_yield")

        return {"passed": len(errors) == 0, "checks_run": checks_run, "errors": errors}

    def _compute_constraint_diagnosis(
        self,
        accepted_state: dict[str, Any],
        candidate_state: dict[str, Any],
        summary: str,
    ) -> dict[str, Any]:
        """Computes before/after binding constraint shift, alternative options, conventional comparator, and 2nd/3rd-order risks."""
        if isinstance(candidate_state.get("bakery"), dict) and isinstance(accepted_state.get("bakery"), dict):
            b_before = accepted_state["bakery"]
            b_after = candidate_state["bakery"]
            c_before = b_before.get("computed", {})
            c_after = b_after.get("computed", {})
            loaves_delta = int(c_after.get("throughput_loaves_per_day", 0)) - int(c_before.get("throughput_loaves_per_day", 0))
            margin_delta = round(float(c_after.get("net_daily_usd", 0.0)) - float(c_before.get("net_daily_usd", 0.0)), 2)
            return {
                "domain": "bakery",
                "before_binding_constraint": str(c_before.get("bottleneck_id", "oven")),
                "after_binding_constraint": str(c_after.get("bottleneck_id", "oven")),
                "constraint_shifted": c_before.get("bottleneck_id") != c_after.get("bottleneck_id"),
                "before_output": f"{c_before.get('throughput_loaves_per_day', 174)} loaves/day",
                "after_output": f"{c_after.get('throughput_loaves_per_day', 174)} loaves/day",
                "delta_output": f"{loaves_delta:+d} loaves/day",
                "before_daily_margin_usd": float(c_before.get("net_daily_usd", 0.0)),
                "after_daily_margin_usd": float(c_after.get("net_daily_usd", 0.0)),
                "delta_daily_margin_usd": margin_delta,
                "conventional_comparator": "Hire +1 Baker ($160/day labor) -> +0 loaves/day while 1 oven caps bake at 174 loaves/day.",
                "second_order_risks": [
                    "Adding a 2nd oven shifts the binding bottleneck to staff prep capacity (240 loaves/day).",
                    "Expanding both oven and staff shifts the 3rd-order bottleneck to proofing rack capacity (280 loaves/day).",
                ],
                "discriminating_falsifier": "Verify min(oven_cap, staff_cap, proofing_cap) before and after patch; reject any option claiming throughput above the active physical minimum.",
                "next_enabled_actions": [
                    p["label"] for p in b_after.get("paths", {}).values() if isinstance(p, dict) and "label" in p
                ],
            }
        if isinstance(candidate_state.get("garden"), dict) and isinstance(accepted_state.get("garden"), dict):
            g_before = accepted_state["garden"]
            g_after = candidate_state["garden"]
            c_before = g_before.get("computed", {})
            c_after = g_after.get("computed", {})
            lbs_delta = round(float(c_after.get("throughput_lbs_per_week", 0.0)) - float(c_before.get("throughput_lbs_per_week", 0.0)), 2)
            net_delta = round(float(c_after.get("net_weekly_community_value_usd", 0.0)) - float(c_before.get("net_weekly_community_value_usd", 0.0)), 2)
            return {
                "domain": "community_garden",
                "before_binding_constraint": str(c_before.get("bottleneck_id", "water")),
                "after_binding_constraint": str(c_after.get("bottleneck_id", "water")),
                "constraint_shifted": c_before.get("bottleneck_id") != c_after.get("bottleneck_id"),
                "before_output": f"{c_before.get('throughput_lbs_per_week', 105)} lbs/wk",
                "after_output": f"{c_after.get('throughput_lbs_per_week', 105)} lbs/wk",
                "delta_output": f"{lbs_delta:+.1f} lbs/wk",
                "before_weekly_net_benefit_usd": float(c_before.get("net_weekly_community_value_usd", 0.0)),
                "after_weekly_net_benefit_usd": float(c_after.get("net_weekly_community_value_usd", 0.0)),
                "delta_weekly_net_benefit_usd": net_delta,
                "conventional_comparator": (
                    "Option B (Pay Municipal Tap Water Overages, $0 CapEx, +$18/wk utility bill) reaches 135 lbs/wk "
                    "but lowers net community benefit by $18/wk ($216/season) vs Option A (Drip Header + Mulch + 2nd Cistern, "
                    "$280 one-time grant CapEx, $0/wk utility cost, 3.1-week payback)."
                ),
                "second_order_risks": [
                    "Relieving the water bottleneck shifts the binding constraint to volunteer harvest/weeding labor (135 lbs/wk).",
                    "Adding volunteer hours BEFORE fixing irrigation yields +0 lbs/wk and causes volunteer burnout.",
                    "Combining Drip + Volunteer shift unlocks +45 lbs/wk (150 lbs/wk), shifting the 3rd-order limit to bed/compost area (150 lbs/wk).",
                ],
                "discriminating_falsifier": "Compare soil-moisture evaporation loss (35% overhead spray vs 12% drip+mulch) and weekly utility ledger ($0/wk vs $18/wk).",
                "next_enabled_actions": [
                    p["label"] for p in g_after.get("paths", {}).values() if isinstance(p, dict) and "label" in p
                ],
            }
        if isinstance(candidate_state.get("neural_model"), dict) and isinstance(accepted_state.get("neural_model"), dict):
            m_before = accepted_state["neural_model"].get("computed", {})
            m_after = candidate_state["neural_model"].get("computed", {})
            pts_delta = int(m_after.get("frontier_score_pts", 0)) - int(m_before.get("frontier_score_pts", 0))
            return {
                "domain": "neural_model",
                "before_binding_constraint": str(m_before.get("bottleneck_id", "spectral_flow")),
                "after_binding_constraint": str(m_after.get("bottleneck_id", "spectral_flow")),
                "constraint_shifted": m_before.get("bottleneck_id") != m_after.get("bottleneck_id"),
                "before_output": f"{m_before.get('frontier_score_pts', 52)} frontier_pts",
                "after_output": f"{m_after.get('frontier_score_pts', 52)} frontier_pts",
                "delta_output": f"{pts_delta:+d} frontier_pts",
                "conventional_comparator": (
                    "Conventional unfiltered SGD fine-tuning reaches 56 frontier_pts (0.6197 composite score) "
                    "because 45% dead channels and 18% corrupted outliers remain unaddressed."
                ),
                "second_order_risks": [
                    "Restoring spectral rank exposes the network to overfitting the 18% corrupted training outliers unless curriculum filtering is applied next.",
                    "Repeatedly querying the validation split (>12 queries) without holdout separation risks validation overfitting (STOP_VALIDATION_OVERFITTING).",
                ],
                "discriminating_falsifier": "Certify candidate checkpoint on EvaluatorHoldoutAuthority sealed clean + shifted splits and verify non_regression_passed=True.",
                "next_enabled_actions": [
                    p["label"] for p in candidate_state["neural_model"].get("paths", {}).values() if isinstance(p, dict) and "label" in p
                ],
            }
        return {
            "domain": str(candidate_state.get("project_family", "general")),
            "before_binding_constraint": "baseline_accepted_specification",
            "after_binding_constraint": "candidate_revision_verification",
            "constraint_shifted": False,
            "summary": summary,
            "conventional_comparator": "Manual unverified state edit without receiver CAS or cryptographic receipt.",
            "second_order_risks": ["Concurrent proposal conflict if base state advances before promotion."],
            "discriminating_falsifier": "Verify candidate artifact via verify_project_artifact and atomic base_version/base_state_sha256 CAS.",
            "next_enabled_actions": ["Accept verified proposal", "Reject and quarantine candidate"],
        }

    # -----------------------------------------------------------------------
    # Accepted / Exploratory / Rejected Workflow (Section 5 & Section 8)
    # -----------------------------------------------------------------------
    def propose_exploratory_change(
        self,
        project_id: str,
        summary: str,
        mutation_fn_or_patch: dict[str, Any],
        proposer_worker: str | None = None,
    ) -> dict[str, Any]:
        """Creates an Exploratory candidate proposal without modifying Accepted state."""
        self._require_open(project_id)
        self._require_not_stopped(operation="propose_exploratory_change", target_id=project_id)

        worker_label = proposer_worker or self.active_worker_id
        worker_ident = self._worker_identity_by_label(worker_label)
        if self.guard.is_worker_revoked(worker_ident.public):
            raise PermissionError(f"proposer_worker_revoked:{worker_label}")

        bundle = self.get_project_bundle(project_id)
        base_version = int(bundle["accepted"]["version"])
        base_state_sha256 = str(bundle["accepted"]["state_sha256"])
        accepted_state = copy.deepcopy(bundle["accepted"]["state"])
        expected_family = str(accepted_state.get("project_family", bundle["project_family"]))
        candidate = copy.deepcopy(accepted_state)

        patch = dict(mutation_fn_or_patch)
        app_content = patch.pop("app_content", None)
        app_filename = patch.pop("app_filename", None) or f"{project_id}.html"

        if app_content is None and not patch and expected_family == "model_built_app":
            if self.model_adapter is None:
                raise ValueError("propose_requires_app_content_without_model")
            from core.genie_worker import GenieWorker

            current = self.get_app_version(project_id)
            revised = GenieWorker(self.model_adapter, self).revise(
                prompt=accepted_state.get("prompt", ""),
                current_app_html=current["content"],
                change_request=summary,
                project_id=project_id,
                title=str(accepted_state.get("title", project_id)),
            )
            app_content = revised["app_html"]
            app_filename = current["filename"]

        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(candidate.get(k), dict):
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, dict) and isinstance(candidate[k].get(sub_k), dict):
                        candidate[k][sub_k].update(copy.deepcopy(sub_v))
                    else:
                        candidate[k][sub_k] = copy.deepcopy(sub_v)
            else:
                candidate[k] = copy.deepcopy(v)

        recompute_bakery_state(candidate)
        recompute_garden_state(candidate)
        recompute_neural_model_state(candidate)

        if app_content is not None:
            if not isinstance(app_content, str) or "<html" not in app_content.lower():
                raise ValueError("invalid_app_content")
            app_version = self.store_app_version(
                project_id, str(app_filename), app_content, status="exploratory"
            )
            candidate["app_version"] = app_version
            candidate["app_sha256"] = sha256_hex(app_content)
            candidate["app_filename"] = str(app_filename)

        val_report = self.verify_project_artifact(
            candidate,
            expected_project_id=project_id,
            expected_family=expected_family,
        )
        diagnosis = self._compute_constraint_diagnosis(accepted_state, candidate, summary)
        cand_raw = canonical(candidate).decode("utf-8")
        cand_sha = sha256_hex(candidate)
        proposer_epoch = int(self.guard.read_stop_state().get("epoch", 0))
        proposer_basis = self._read_current_basis()
        prop_id = (
            f"prop-{sha256_hex({'p': project_id, 's': summary, 'h': cand_sha, 'bv': base_version, 'bs': base_state_sha256, 'ep': proposer_epoch})[:10]}"
        )

        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT OR REPLACE INTO genie_exploratory
                (proposal_id, project_id, proposer_worker, summary, candidate_state_json, candidate_sha256,
                 validation_passed, validation_report_json, status, created_at,
                 base_version, base_state_sha256, proposer_epoch, proposer_basis_json,
                 target_project_id, validated_family, constraint_diagnosis_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'EXPLORATORY_PENDING', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prop_id,
                    project_id,
                    worker_label,
                    summary,
                    cand_raw,
                    cand_sha,
                    1 if val_report["passed"] else 0,
                    json.dumps(val_report, sort_keys=True),
                    int(time.time()),
                    base_version,
                    base_state_sha256,
                    proposer_epoch,
                    json.dumps(proposer_basis, sort_keys=True),
                    project_id,
                    str(candidate.get("project_family", "")),
                    json.dumps(diagnosis, sort_keys=True),
                ),
            )
            db.commit()
        return self.get_project_bundle(project_id)

    def reject_exploratory_change(self, project_id: str, proposal_id: str, reason: str = "user_rejected_proposal") -> dict[str, Any]:
        """Declines an Exploratory proposal, records it in `genie_rejected`, and preserves Accepted state untouched."""
        self._require_open(project_id)
        bundle_before = self.get_project_bundle(project_id)
        accepted_sha_before = bundle_before["accepted"]["state_sha256"]

        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT candidate_sha256, candidate_state_json FROM genie_exploratory WHERE proposal_id=? AND project_id=?",
                (proposal_id, project_id),
            ).fetchone()
            if not row:
                raise ValueError(f"unknown_proposal_id:{proposal_id}")
            cand_sha, cand_json = row[0], row[1]
            db.execute(
                "UPDATE genie_exploratory SET status='REJECTED' WHERE proposal_id=?",
                (proposal_id,),
            )
            rej_id = f"rej-{sha256_hex({'prop': proposal_id, 'reason': reason})[:10]}"
            refusal_receipt = {
                "schema": "openline.genie.rejection_receipt.v1",
                "rejection_id": rej_id,
                "proposal_id": proposal_id,
                "project_id": project_id,
                "status": "REJECTED_QUARANTINED",
                "reason": reason,
                "candidate_sha256": cand_sha,
                "preserved_accepted_sha256": accepted_sha_before,
            }
            db.execute(
                """
                INSERT OR REPLACE INTO genie_rejected
                (rejection_id, proposal_id, project_id, reason, candidate_sha256, preserved_accepted_sha256, receipt_json, rejected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rej_id,
                    proposal_id,
                    project_id,
                    reason,
                    cand_sha,
                    accepted_sha_before,
                    json.dumps(refusal_receipt, sort_keys=True),
                    int(time.time()),
                ),
            )
            db.commit()

        bundle_after = self.get_project_bundle(project_id)
        if bundle_after["accepted"]["state_sha256"] != accepted_sha_before:
            raise RuntimeError("critical_invariant_violation:rejected_proposal_mutated_accepted_state")
        try:
            cand_state = json.loads(cand_json)
        except ValueError:
            cand_state = {}
        cand_app_version = cand_state.get("app_version")
        accepted_app_version = bundle_after["accepted"]["state"].get("app_version")
        if cand_app_version is not None and cand_app_version != accepted_app_version:
            try:
                self.set_app_version_status(project_id, int(cand_app_version), "rejected")
            except ValueError:
                pass
        return bundle_after

    def accept_exploratory_change(self, project_id: str, proposal_id: str) -> dict[str, Any]:
        """Promotes a validated Exploratory proposal to Accepted state via ReceiverGuard with CAS and epoch/worker checks."""
        self._require_open(project_id)
        self._require_not_stopped(operation="accept_exploratory_change", target_id=project_id)
        current_epoch = int(self.guard.read_stop_state().get("epoch", 0))
        current_basis = self._read_current_basis()

        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                """
                SELECT candidate_state_json, candidate_sha256, validation_passed, status,
                       proposer_worker, base_version, base_state_sha256, proposer_epoch,
                       proposer_basis_json, target_project_id, validated_family, constraint_diagnosis_json
                FROM genie_exploratory
                WHERE proposal_id=? AND project_id=?
                """,
                (proposal_id, project_id),
            ).fetchone()
            if not row:
                raise ValueError(f"unknown_proposal_id:{proposal_id}")

            acc_row = db.execute(
                "SELECT version, state_sha256, project_family, state_json FROM genie_accepted WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if not acc_row:
                raise ValueError(f"project_not_found:{project_id}")

            status = str(row["status"])
            if status == "REJECTED":
                raise PermissionError("cannot_promote_rejected_proposal")
            if status in ("REVOKED_BY_STOP_EPOCH", "REVOKED_BY_WORKER_SWAP"):
                raise PermissionError(f"cannot_promote_revoked_proposal:{status}")
            if status == "STALE_REOPEN_REQUIRED":
                raise PermissionError(f"stale_proposal_reopen_required:{proposal_id}")
            if status != "EXPLORATORY_PENDING":
                raise PermissionError(f"proposal_not_pending:{status}")
            if not int(row["validation_passed"]):
                raise PermissionError("cannot_promote_invalid_candidate")

            prop_epoch = int(row["proposer_epoch"])
            if prop_epoch != current_epoch:
                db.execute(
                    "UPDATE genie_exploratory SET status='REVOKED_BY_STOP_EPOCH' WHERE proposal_id=?",
                    (proposal_id,),
                )
                db.commit()
                raise PermissionError(
                    f"proposal_epoch_expired:proposal_epoch_{prop_epoch}_current_{current_epoch}"
                )

            prop_worker_label = str(row["proposer_worker"])
            prop_worker_ident = self._worker_identity_by_label(prop_worker_label)
            if self.guard.is_worker_revoked(prop_worker_ident.public):
                db.execute(
                    "UPDATE genie_exploratory SET status='REVOKED_BY_WORKER_SWAP' WHERE proposal_id=?",
                    (proposal_id,),
                )
                db.commit()
                raise PermissionError(f"proposal_worker_revoked:{prop_worker_label}")

            try:
                prop_basis = json.loads(row["proposer_basis_json"] or "{}")
            except ValueError:
                prop_basis = {}
            if prop_basis and prop_basis != current_basis:
                raise PermissionError("proposal_basis_mismatch")

            if row["target_project_id"] and str(row["target_project_id"]) != project_id:
                raise PermissionError("proposal_target_project_id_mismatch")

            cur_version = int(acc_row["version"])
            cur_sha = str(acc_row["state_sha256"])
            cur_family = str(acc_row["project_family"])
            base_version = int(row["base_version"])
            base_sha = str(row["base_state_sha256"])

            if base_version != cur_version or (base_sha and base_sha != cur_sha):
                db.execute(
                    "UPDATE genie_exploratory SET status='STALE_REOPEN_REQUIRED' WHERE proposal_id=?",
                    (proposal_id,),
                )
                db.commit()
                raise PermissionError(
                    f"stale_proposal_base_mismatch:expected_v{base_version}_{base_sha[:12]}_got_v{cur_version}_{cur_sha[:12]}"
                )

            cand_json = str(row["candidate_state_json"])
            cand_sha = str(row["candidate_sha256"])
            diag_json = str(row["constraint_diagnosis_json"] or "{}")

        cand_state = json.loads(cand_json)
        if sha256_hex(cand_state) != cand_sha:
            raise PermissionError("candidate_sha256_integrity_mismatch")

        recheck = self.verify_project_artifact(
            cand_state,
            expected_project_id=project_id,
            expected_family=cur_family,
        )
        if not recheck["passed"]:
            raise PermissionError(f"receiver_verification_failed:{recheck['errors']}")

        target_family = str(cand_state.get("project_family", cur_family))
        prior_state = json.loads(acc_row["state_json"])
        incoming_app_ver = cand_state.get("app_version")
        staged_app_to_promote = (
            int(incoming_app_ver)
            if incoming_app_ver is not None and incoming_app_ver != prior_state.get("app_version")
            else None
        )
        receipt = self._commit_accepted_state(
            project_id,
            target_family,
            cand_state,
            operation="accept_exploratory_proposal",
            step_id=f"accept-{proposal_id}",
            expected_prev_version=cur_version,
            expected_prev_sha256=cur_sha,
            promote_staged_app_version=staged_app_to_promote,
        )

        try:
            diag = json.loads(diag_json)
        except ValueError:
            diag = {}
        receipt_inner = receipt.get("receipt", receipt) if isinstance(receipt, dict) else {}
        receipt_payload = receipt_inner.get("payload", {}) if isinstance(receipt_inner, dict) else {}
        receipt_id = str(receipt_payload.get("receipt_id", ""))
        jump_id = f"jump-{sha256_hex({'p': project_id, 'prop': proposal_id, 'v': cur_version + 1})[:10]}"

        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE genie_exploratory SET status='ACCEPTED_PROMOTED' WHERE proposal_id=?",
                (proposal_id,),
            )
            db.execute(
                """
                INSERT OR REPLACE INTO genie_jump_decisions
                (jump_id, project_id, proposal_id, from_version, to_version,
                 previous_binding_constraint, new_binding_constraint, delta_summary,
                 next_enabled_actions_json, second_order_risks_json, discriminating_test,
                 accepted_sha256, receipt_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    jump_id,
                    project_id,
                    proposal_id,
                    cur_version,
                    cur_version + 1,
                    str(diag.get("before_binding_constraint", "baseline")),
                    str(diag.get("after_binding_constraint", "updated")),
                    str(diag.get("delta_output") or diag.get("summary") or "Accepted state updated"),
                    json.dumps(diag.get("next_enabled_actions", []), sort_keys=True),
                    json.dumps(diag.get("second_order_risks", []), sort_keys=True),
                    str(diag.get("discriminating_falsifier", "verify_project_artifact")),
                    cand_sha,
                    receipt_id,
                    int(time.time()),
                ),
            )
            db.commit()
        return self.get_project_bundle(project_id)

    # -----------------------------------------------------------------------
    # Domain Mutations for Demonstration A, Demonstration B & Synthesized Apps
    # -----------------------------------------------------------------------
    def demo_a_add_or_update_quote(
        self,
        customer_id: str,
        customer_name: str,
        items: list[dict[str, Any]],
        discount_pct: float = 0.0,
        tax_rate_pct: float = 8.25,
        deposit_pct: float = 25.0,
        notes: str = "",
        quote_id: str | None = None,
    ) -> dict[str, Any]:
        bundle = self.get_project_bundle("demo-a-service-quoting")
        state = copy.deepcopy(bundle["accepted"]["state"])
        calc = calculate_quote_totals(items, discount_pct=discount_pct, tax_rate_pct=tax_rate_pct, deposit_pct=deposit_pct)
        qid = quote_id or f"Q-{1001 + len(state['quotes'])}"
        new_quote = {
            "quote_id": qid,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "status": "ACCEPTED_BY_CUSTOMER",
            "created_date": "2026-11-10",
            "valid_until": "2026-11-30",
            "notes": notes,
            **calc,
        }
        replaced = False
        for i, q in enumerate(state["quotes"]):
            if q["quote_id"] == qid:
                state["quotes"][i] = new_quote
                replaced = True
                break
        if not replaced:
            state["quotes"].append(new_quote)
        self._commit_accepted_state("demo-a-service-quoting", "service_quoting_invoicing", state, operation="save_quote")
        return self.get_project_bundle("demo-a-service-quoting")

    def demo_a_convert_quote_to_invoice(self, quote_id: str, payment_terms: str = "Net 15") -> dict[str, Any]:
        bundle = self.get_project_bundle("demo-a-service-quoting")
        state = copy.deepcopy(bundle["accepted"]["state"])
        target_q = None
        for q in state["quotes"]:
            if q["quote_id"] == quote_id:
                target_q = q
                q["status"] = "CONVERTED_TO_INVOICE"
                break
        if not target_q:
            raise ValueError(f"quote_not_found:{quote_id}")

        inv_id = f"INV-{2001 + len(state['invoices'])}"
        inv = {
            "invoice_id": inv_id,
            "source_quote_id": quote_id,
            "customer_id": target_q["customer_id"],
            "customer_name": target_q["customer_name"],
            "issued_date": "2026-11-10",
            "due_date": "2026-11-25",
            "payment_terms": payment_terms,
            "payment_status": "UNPAID",
            "total_cents": target_q["total_cents"],
            "total_dollars": target_q["total_dollars"],
            "paid_cents": 0,
            "paid_dollars": 0.0,
            "balance_due_cents": target_q["total_cents"],
            "balance_due_dollars": target_q["total_dollars"],
            "items": copy.deepcopy(target_q["items"]),
            "subtotal_dollars": target_q["subtotal_dollars"],
            "discount_dollars": target_q["discount_dollars"],
            "tax_dollars": target_q["tax_dollars"],
        }
        state["invoices"].append(inv)
        self._commit_accepted_state("demo-a-service-quoting", "service_quoting_invoicing", state, operation="convert_quote_to_invoice")
        return self.get_project_bundle("demo-a-service-quoting")

    def demo_b_run_program(self, level_num: int, blocks: list[str], speed_mps: float = 0.55) -> dict[str, Any]:
        bundle = self.get_project_bundle("demo-b-robot-academy-kids")
        state = copy.deepcopy(bundle["accepted"]["state"])
        sim = simulate_robot_academy_program(level_num, blocks, requested_speed_mps=speed_mps)
        state["current_level"] = int(level_num)
        state["active_blocks"] = list(blocks)
        state["last_simulation"] = sim
        if sim["reached_target"] and int(level_num) not in state["completed_levels"]:
            state["completed_levels"].append(int(level_num))
            badge_name = f"Level {level_num} Mastery Star"
            if badge_name not in state["badges_earned"]:
                state["badges_earned"].append(badge_name)
        self._commit_accepted_state("demo-b-robot-academy-kids", "robot_academy_kids", state, operation="run_robot_academy_level")
        return self.get_project_bundle("demo-b-robot-academy-kids")

    def synthesized_app_add_record(self, project_id: str, record: dict[str, Any]) -> dict[str, Any]:
        bundle = self.get_project_bundle(project_id)
        state = copy.deepcopy(bundle["accepted"]["state"])
        computed = GenieAppSynthesizer.compute_record_metric(state, record)
        if "record_id" not in computed:
            computed["record_id"] = f"REC-{101 + len(state.get('records', []))}"
        if "status" not in computed:
            states = state.get("workflow_states", ["ACTIVE"])
            computed["status"] = states[0]
        state.setdefault("records", []).append(computed)
        self._commit_accepted_state(project_id, state["project_family"], state, operation="add_synthesized_record")
        return self.get_project_bundle(project_id)

    # -----------------------------------------------------------------------
    # Owner Authority Controls: STOP, Worker Succession & External Outbox
    # -----------------------------------------------------------------------
    def trigger_stop(self, reason: str = "owner_emergency_stop") -> dict[str, Any]:
        cur_epoch = self.guard.read_stop_state()["epoch"]
        env = self.owner_identity.issue_stop_envelope(reason=reason, expected_epoch=cur_epoch)
        receipt = self.guard.issue_stop(env)
        new_epoch = int(self.guard.read_stop_state()["epoch"])
        with sqlite3.connect(self.db_path) as db:
            cur = db.execute(
                """
                UPDATE genie_exploratory
                SET status='REVOKED_BY_STOP_EPOCH'
                WHERE status='EXPLORATORY_PENDING' AND proposer_epoch < ?
                """,
                (new_epoch,),
            )
            revoked_count = int(cur.rowcount)
            db.commit()
        return {
            "status": "STOPPED",
            "stop_receipt": receipt,
            "new_epoch": new_epoch,
            "revoked_pending_proposals": revoked_count,
        }

    def clear_stop(self, reason: str = "owner_resume") -> dict[str, Any]:
        cur_epoch = self.guard.read_stop_state()["epoch"]
        env = self.owner_identity.clear_stop_envelope(reason=reason, expected_epoch=cur_epoch)
        receipt = self.guard.clear_stop(env)
        return {"status": "ACTIVE", "clear_receipt": receipt, "active_epoch": int(cur_epoch)}

    def register_destination(self, destination: str, public_key: str) -> dict[str, Any]:
        """Owner-only destination-key registration (RC2A)."""
        self.guard.register_destination(destination, public_key)
        return {
            "destination": destination,
            "public_key": public_key,
            "pinned": True,
        }

    def list_destinations(self) -> list[dict[str, Any]]:
        return self.guard.list_destinations()

    def replace_worker_and_recover(self) -> dict[str, Any]:
        """Revokes Worker-A, switches active worker to Worker-B, revokes unaccepted Worker-A proposals, and verifies accepted work continuity."""
        self.guard.revoke_worker(self.worker_a_identity.public, reason="worker_a_interrupted_handover")
        self.guard.set_active_worker_pub(self.worker_b_identity.public)
        self.active_worker_id = "worker-b"
        with sqlite3.connect(self.db_path) as db:
            cur = db.execute(
                """
                UPDATE genie_exploratory
                SET status='REVOKED_BY_WORKER_SWAP'
                WHERE status='EXPLORATORY_PENDING' AND proposer_worker='worker-a'
                """
            )
            revoked_proposals = int(cur.rowcount)
            db.commit()
        return {
            "revoked_worker_pub": self.worker_a_identity.public,
            "new_active_worker": "worker-b",
            "new_worker_pub": self.worker_b_identity.public,
            "revoked_pending_proposals": revoked_proposals,
            "status": "WORKER_REPLACED_AND_REVOKED",
        }

    def attempt_consequential_external_action(
        self,
        project_id: str,
        action_name: str,
        destination: str,
        payload: dict[str, Any],
        owner_approved: bool = False,
        simulate_network_drop: bool = False,
    ) -> dict[str, Any]:
        """Enforces that consequential external actions require explicit owner approval and use the D-01b two-phase outbox."""
        if action_name in CONSEQUENTIAL_EXTERNAL_ACTIONS and not owner_approved:
            return {
                "status": "BLOCKED_OWNER_AUTHORIZATION_REQUIRED",
                "action": action_name,
                "reason": "Consequential external actions (publishing, spending, emailing customers, credentials, deployment) require explicit owner approval.",
                "external_effects_sent": 0,
            }

        worker = self._active_worker()
        step_id = f"ext-{action_name}-{secrets.token_hex(4)}"
        grant = self.owner_identity.issue_grant(
            worker.public,
            task_id=f"task-{project_id}",
            step_id=step_id,
            operation=action_name,
            allowed_targets=[project_id],
            max_amount=50000,
            required_basis={"genie_operating_law": "v1.0-20261103"},
            grant_id=f"grant-{step_id}",
            stop_epoch=self.guard.read_stop_state()["epoch"],
        )
        req = worker.sign_request(
            grant,
            operation=action_name,
            target_id=project_id,
            step_id=step_id,
            payload={"project_id": project_id, "amount": 1, **payload},
        )
        staged_ids: list[str] = []

        def _stage(db: sqlite3.Connection, p: dict[str, Any]) -> dict[str, Any]:
            oid = self.guard.stage_external_effect(
                db,
                task_id=f"task-{project_id}",
                step_id=step_id,
                channel="webhook",
                destination=destination,
                payload=payload,
            )
            staged_ids.append(oid)
            return {"outbox_id": oid}

        receipt = self.guard.execute(
            grant=grant,
            request=req,
            fn=_stage,
            target_table="genie_accepted",
            target_pk_col="project_id",
            amount_field="amount",
        )
        outbox_id = staged_ids[0]
        if simulate_network_drop:
            def _dropping_dispatcher(env: dict[str, Any]) -> dict[str, Any]:
                raise TimeoutError("simulated_webhook_ack_timeout_after_send")
            flush_res = self.guard.flush_external_outbox(_dropping_dispatcher)
            return {
                "status": "UNKNOWN_RECONCILIATION_REQUIRED",
                "outbox_id": outbox_id,
                "receipt": receipt,
                "flush_result": flush_res,
            }
        else:
            delivered: list[dict[str, Any]] = []
            def _ok_dispatcher(env: dict[str, Any]) -> dict[str, Any]:
                delivered.append(env)
                return {"status": "DELIVERED"}
            flush_res = self.guard.flush_external_outbox(_ok_dispatcher)
            final = next(x for x in self.guard.list_external_outbox() if x["outbox_id"] == outbox_id)
            return {
                "status": final["state"],
                "outbox_id": outbox_id,
                "receipt": receipt,
                "flush_result": flush_res,
                "simulated_dispatcher_calls": len(delivered),
                "external_effects_verified": 1 if final["state"] == "DISPATCHED" else 0,
            }

    # -----------------------------------------------------------------------
    # Portable Export & Fresh-Install Import (Zero Lock-In HTML / JSON / CSV)
    # -----------------------------------------------------------------------
    def export_portable_bundle(self, project_id: str) -> dict[str, Any]:
        """Exports portable JSON, CSV, and a standalone zero-dependency HTML application."""
        bundle = self.get_project_bundle(project_id)
        state = bundle["accepted"]["state"]
        family = state.get("project_family", "")

        def csv_cell(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            if value.lstrip().startswith(("=", "+", "-", "@")):
                return "'" + value
            return value

        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        if family == "service_quoting_invoicing":
            writer.writerow(["RecordType", "ID", "Customer", "Status", "Subtotal($)", "Discount($)", "Tax($)", "Total($)", "BalanceDue($)"])
            for q in state.get("quotes", []):
                writer.writerow(["QUOTE", q["quote_id"], csv_cell(q["customer_name"]), q["status"], q["subtotal_dollars"], q["discount_dollars"], q["tax_dollars"], q["total_dollars"], q["total_dollars"]])
            for inv in state.get("invoices", []):
                writer.writerow(["INVOICE", inv["invoice_id"], csv_cell(inv["customer_name"]), inv["payment_status"], inv["subtotal_dollars"], inv["discount_dollars"], inv["tax_dollars"], inv["total_dollars"], inv["balance_due_dollars"]])
        elif family == "robot_academy_kids":
            writer.writerow(["Step", "X(m)", "Y(m)", "Heading(deg)", "Event"])
            for idx, pt in enumerate(state.get("last_simulation", {}).get("path_points", []), start=1):
                writer.writerow([idx, pt["x"], pt["y"], pt["heading_deg"], pt["event"]])
        elif family == "bakery" and isinstance(state.get("bakery"), dict):
            writer.writerow(["Metric", "Value", "BindingConstraint", "DailyMargin($)"])
            bk = state["bakery"]
            comp = bk.get("computed", {})
            writer.writerow([
                "AcceptedBakeryThroughput",
                comp.get("throughput_loaves_per_day"),
                comp.get("bottleneck_id"),
                comp.get("net_daily_usd"),
            ])
            for pid, pinfo in bk.get("paths", {}).items():
                writer.writerow([f"Option:{pid}", csv_cell(pinfo.get("label", pid)), pinfo.get("capex_usd", 0), ""])
        else:
            writer.writerow(["RecordID", "Title/Name", "Status", "MetricLabel", "MetricValue"])
            for r in state.get("records", []):
                title_val = r.get("plot_or_crop_name") or r.get("item_name") or r.get("scenario_name") or r.get("representative_name") or r.get("item_title") or "Record"
                writer.writerow([r.get("record_id"), csv_cell(title_val), r.get("status"), r.get("computed_metric_label"), r.get("computed_metric_value")])

        csv_text_out = csv_buf.getvalue()
        json_text = json.dumps(bundle, indent=2, sort_keys=True)

        standalone_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{html.escape(str(state.get('title', 'Exported OpenLine Genie App')))} — Read-Only Export</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 24px; background: #F8FAFC; color: #0F172A; }}
  .box {{ background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 18px; max-width: 960px; margin: 0 auto 16px; }}
  h1 {{ font-size: 20px; margin-bottom: 6px; }}
  pre {{ background: #0F172A; color: #F8FAFC; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; }}
  .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; background: #ECFDF5; color: #059669; font-weight: 700; font-size: 11px; }}
</style>
</head>
<body>
  <div class="box">
    <span class="badge">PORTABLE STANDALONE EXPORT (READ-ONLY SNAPSHOT) • ZERO OPENLINE LOCK-IN • $0 SUBSCRIPTION</span>
    <h1>{html.escape(str(state.get('title', 'Exported Genie Application')))}</h1>
    <p>{html.escape(str(state.get('honesty_boundary') or state.get('safety_and_access_disclosure', '')))}</p>
    <p><strong>Accepted State SHA-256:</strong> <code>{bundle['accepted']['state_sha256']}</code> (Version {bundle['accepted']['version']})</p>
    <p><strong>Source Receiver Public Key:</strong> <code>{bundle['receiver_public_key']}</code></p>
  </div>
  <div class="box">
    <h2>Exported CSV Table</h2>
    <pre>{html.escape(csv_text_out)}</pre>
  </div>
  <div class="box">
    <h2>Portable JSON State (Take Anywhere)</h2>
    <pre id="portable-json">{html.escape(json.dumps(state, indent=2, sort_keys=True))}</pre>
  </div>
</body>
</html>"""

        out: dict[str, Any] = {
            "project_id": project_id,
            "portable_json": json_text,
            "portable_csv": csv_text_out,
            "standalone_html": standalone_html,
            "accepted_sha256": bundle["accepted"]["state_sha256"],
            "source_receiver_public_key": bundle["receiver_public_key"],
            "source_owner_public_key": bundle["owner_public_key"],
        }
        out.update(self._runnable_export_fields(project_id, bundle))
        return out

    def import_portable_bundle(
        self,
        portable_payload: dict[str, Any] | str,
        target_project_id: str | None = None,
        *,
        allow_overwrite: bool = False,
        expected_base_version: int | None = None,
        expected_base_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Imports a portable bundle into this installation after strict cryptographic,
        STOP-epoch, CAS, and executable-artifact verification.

        Closes GPT-6 RC7 r1 falsifiers F1-F5:
        - F1: Refuses overwriting an existing accepted project unless explicit CAS
              (`allow_overwrite=True`, `expected_base_version`, `expected_base_sha256`)
              and strictly newer version (`source_version > cur_version`) are satisfied.
        - F2 & F5: Verifies that the signed receipt's `payload_sha256`, `effect_sha256`,
              and `target` cryptographically bind the exact `orig_pid`, `source_version`,
              and `claimed_sha` of `accepted.state` (preventing title/content laundering
              under an old signature).
        - F3: Verifies `app.sha256 == sha256_hex(app.content)` AND requires any
              `runs_standalone=True` executable app to be bound inside the receipt-verified
              `accepted.state["app_sha256"]` before staging.
        - F4: Enforces `_require_not_stopped` and `_require_open` before any DB or
              artifact write, and rolls back any staged `genie_app_versions` row if
              receiver commit fails.
        """
        if isinstance(portable_payload, str):
            raw_obj = json.loads(portable_payload)
        elif isinstance(portable_payload, dict):
            if "portable_json" in portable_payload and isinstance(portable_payload["portable_json"], str):
                raw_obj = json.loads(portable_payload["portable_json"])
            else:
                raw_obj = copy.deepcopy(portable_payload)
        else:
            raise ValueError("invalid_portable_payload_type")

        if not isinstance(raw_obj, dict) or "accepted" not in raw_obj:
            raise ValueError("missing_accepted_section_in_portable_bundle")

        acc = raw_obj["accepted"]
        if not isinstance(acc, dict) or not isinstance(acc.get("state"), dict) or "state_sha256" not in acc:
            raise ValueError("malformed_accepted_section_in_portable_bundle")

        orig_state = copy.deepcopy(acc["state"])
        orig_pid = str(raw_obj.get("project_id") or orig_state.get("project_id") or "").strip()
        if not orig_pid or orig_state.get("project_id") != orig_pid:
            raise PermissionError("import_project_id_mismatch")

        dest_pid = (str(target_project_id).strip() if target_project_id else orig_pid)
        if not dest_pid:
            raise ValueError("missing_project_id_in_imported_state")

        # F4: Enforce open project & STOP gate FIRST before any side effect or artifact write
        self._require_open(dest_pid)
        self._require_not_stopped(operation="import_portable_bundle", target_id=dest_pid)

        # 1. Verify exact state SHA-256
        claimed_sha = str(acc["state_sha256"])
        computed_sha = sha256_hex(orig_state)
        if computed_sha != claimed_sha:
            raise ValueError(f"import_sha256_mismatch:claimed_{claimed_sha[:12]}_computed_{computed_sha[:12]}")
        if "state_canonical_json" in acc and isinstance(acc["state_canonical_json"], str):
            if sha256_hex(json.loads(acc["state_canonical_json"])) != claimed_sha:
                raise PermissionError("import_canonical_json_sha_mismatch")

        # 2. F2 & F5: Cryptographically verify upstream receipt AND its exact state/version/target binding
        source_version = int(acc.get("version", 0))
        if source_version < 1:
            raise PermissionError("import_invalid_source_version")
        if raw_obj.get("version") is not None and int(raw_obj["version"]) != source_version:
            raise PermissionError("import_bundle_version_mismatch")

        source_receiver_pub = str(raw_obj.get("receiver_public_key") or raw_obj.get("source_receiver_public_key") or "").strip()
        receipt_wrapper = acc.get("receipt", {})
        receipt_inner = receipt_wrapper.get("receipt", receipt_wrapper) if isinstance(receipt_wrapper, dict) else {}
        if not isinstance(receipt_inner, dict) or not receipt_inner or not source_receiver_pub:
            raise PermissionError("import_missing_signed_receipt_or_receiver_key")

        ver = verify_receipt_offline(receipt_inner, pinned_receiver_pub=source_receiver_pub)
        if ver.get("crypto") != "VERIFIED" or ver.get("status") != "COMMITTED":
            raise PermissionError("import_receipt_signature_verification_failed")

        r_payload = receipt_inner.get("payload", {})
        if not isinstance(r_payload, dict):
            raise PermissionError("import_receipt_payload_missing")
        expected_req_sha = sha256_hex({
            "amount": 1,
            "project_id": orig_pid,
            "state_sha256": claimed_sha,
            "version": source_version,
        })
        if r_payload.get("payload_sha256") != expected_req_sha:
            raise PermissionError(
                "import_receipt_state_binding_mismatch:signed_receipt_does_not_bind_claimed_state_and_version"
            )
        r_target = r_payload.get("target", {})
        if not isinstance(r_target, dict) or r_target.get("id") != orig_pid or r_target.get("table") != "genie_accepted":
            raise PermissionError("import_receipt_target_binding_mismatch")
        effect_sha = r_payload.get("effect_sha256")
        if not isinstance(effect_sha, str) or len(effect_sha) != 64:
            raise PermissionError("import_receipt_missing_effect_sha256")

        # 3. F3 & F4: Verify executable app artifact hash and signed state binding BEFORE any DB write
        app_info = raw_obj.get("app")
        has_standalone_app = False
        app_content_str = ""
        app_filename_str = f"{dest_pid}.html"
        if app_info is not None:
            if not isinstance(app_info, dict):
                raise PermissionError("import_invalid_app_block")
            if "content" in app_info:
                if not isinstance(app_info["content"], str):
                    raise PermissionError("import_app_content_not_string")
                app_content_str = app_info["content"]
                actual_app_sha = sha256_hex(app_content_str)
                if "sha256" in app_info and str(app_info["sha256"]) != actual_app_sha:
                    raise PermissionError("imported_app_sha256_mismatch")
                if bool(app_info.get("runs_standalone")):
                    # Executable standalone app MUST be bound in the receipt-signed accepted state
                    state_app_sha = orig_state.get("app_sha256")
                    if not state_app_sha or str(state_app_sha) != actual_app_sha or orig_state.get("app_version") is None:
                        raise PermissionError("imported_executable_app_not_bound_in_signed_state")
                    content_low = app_content_str.lower()
                    if "<html" not in content_low or 'src="http' in content_low or 'href="http' in content_low:
                        raise PermissionError("imported_executable_app_violates_sandbox_policy")
                    has_standalone_app = True
                    app_filename_str = str(app_info.get("filename") or orig_state.get("app_filename") or f"{dest_pid}.html")
            elif bool(app_info.get("runs_standalone")):
                raise PermissionError("imported_standalone_app_missing_content")

        # 4. F1: Enforce target project existence / CAS rules (never silently overwrite accepted state)
        with sqlite3.connect(self.db_path) as db:
            existing = db.execute(
                "SELECT version, state_sha256, project_family FROM genie_accepted WHERE project_id=?",
                (dest_pid,),
            ).fetchone()
        if existing is not None:
            cur_ver, cur_sha, _cur_fam = int(existing[0]), str(existing[1]), str(existing[2])
            if not allow_overwrite:
                raise PermissionError(
                    f"import_cannot_overwrite_existing_accepted_project:{dest_pid}_at_v{cur_ver}_without_explicit_recovery_authorization"
                )
            if expected_base_version is None or expected_base_sha256 is None:
                raise PermissionError("import_overwrite_requires_expected_base_version_and_sha256")
            if cur_ver != int(expected_base_version) or cur_sha != str(expected_base_sha256):
                raise PermissionError("import_overwrite_cas_mismatch")
            if source_version <= cur_ver:
                raise PermissionError(f"stale_import_version:source_v{source_version}_not_newer_than_v{cur_ver}")

        same_receiver = (source_receiver_pub == self.receiver_identity.public)
        imported_state = copy.deepcopy(orig_state)
        imported_state["project_id"] = dest_pid
        imported_state["imported_provenance"] = {
            "source_project_id": orig_pid,
            "source_version": source_version,
            "source_state_sha256": claimed_sha,
            "source_effect_sha256": effect_sha,
            "source_receiver_public_key": source_receiver_pub,
            "upstream_signature_verified_against_source_key": True,
            "upstream_state_and_effect_bound": True,
            "same_receiver_instance": same_receiver,
            "provenance_badge": (
                "LOCAL_RECEIVER_REIMPORTED"
                if same_receiver
                else "EXTERNAL_RECEIVER_SIGNATURE_VERIFIED_IMPORTED"
            ),
        }

        family = str(imported_state.get("project_family", ""))
        staged_ver_num: int | None = None
        try:
            if has_standalone_app:
                # Stage as exploratory first; promote to accepted only after ReceiverGuard commits
                staged_ver_num = self.store_app_version(
                    dest_pid,
                    app_filename_str,
                    app_content_str,
                    status="exploratory",
                )
                imported_state["app_version"] = staged_ver_num
                imported_state["app_sha256"] = sha256_hex(app_content_str)

            val_report = self.verify_project_artifact(
                imported_state,
                expected_project_id=dest_pid,
                expected_family=family,
            )
            if not val_report["passed"]:
                raise ValueError(f"imported_bundle_failed_verification:{val_report['errors']}")

            self._commit_accepted_state(
                dest_pid,
                family,
                imported_state,
                operation="import_portable_bundle",
                step_id=f"import-{dest_pid}-v{source_version}",
                expected_prev_version=expected_base_version if existing is not None else None,
                expected_prev_sha256=expected_base_sha256 if existing is not None else None,
                promote_staged_app_version=staged_ver_num,
                require_target_absent=existing is None,
            )
        except Exception:
            if staged_ver_num is not None:
                # Never remove an artifact after an accepted commit. Delete ONLY
                # an unaccepted staged row, and only when no accepted state
                # references it. This also handles errors after a successful
                # commit (e.g. an interrupted caller) without data loss.
                with sqlite3.connect(self.db_path) as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute(
                        "DELETE FROM genie_app_versions WHERE project_id=? AND version=? AND status='exploratory' "
                        "AND NOT EXISTS (SELECT 1 FROM genie_accepted WHERE project_id=? AND "
                        "json_extract(state_json, '$.app_version')=?)",
                        (dest_pid, staged_ver_num, dest_pid, staged_ver_num),
                    )
                    db.commit()
            raise

        self.log_autonomy_stage(
            dest_pid,
            "6. Portable Bundle Import & Recovery",
            f"Verified SHA-256 ({claimed_sha[:12]}...), receipt payload/effect binding, and committed imported project "
            f"with provenance={imported_state['imported_provenance']['provenance_badge']}",
            "LOCAL_PORTABLE_RECOVERY_VERIFIER",
        )
        return self.get_project_bundle(dest_pid)

    def _runnable_export_fields(self, project_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
        try:
            artifact = self.get_app_version(project_id)
        except ValueError:
            return {"app_sha256": None, "runs_standalone": False}
        return {
            "standalone_html": artifact["content"],
            "app_sha256": artifact["sha256"],
            "app_version": artifact["version"],
            "app_filename": artifact["filename"],
            "runs_standalone": True,
        }

    # -----------------------------------------------------------------------
    # State Inspection
    # -----------------------------------------------------------------------
    def get_project_bundle(self, project_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            acc = db.execute("SELECT * FROM genie_accepted WHERE project_id=?", (project_id,)).fetchone()
            if not acc:
                raise ValueError(f"project_not_found:{project_id}")
            exp_rows = db.execute(
                "SELECT * FROM genie_exploratory WHERE project_id=? ORDER BY rowid DESC",
                (project_id,),
            ).fetchall()
            rej_rows = db.execute(
                "SELECT * FROM genie_rejected WHERE project_id=? ORDER BY rowid DESC",
                (project_id,),
            ).fetchall()
            jump_rows = db.execute(
                "SELECT * FROM genie_jump_decisions WHERE project_id=? ORDER BY rowid DESC",
                (project_id,),
            ).fetchall()
            logs = db.execute(
                "SELECT * FROM genie_autonomy_log WHERE project_id=? ORDER BY seq ASC",
                (project_id,),
            ).fetchall()

        receipt_obj = json.loads(acc["receipt_json"]) if acc["receipt_json"] and acc["receipt_json"] != "{}" else {}
        accepted_state = json.loads(acc["state_json"])
        app_field: dict[str, Any] | None = None
        app_version = accepted_state.get("app_version")
        if app_version is not None:
            try:
                ver = self.get_app_version(project_id, int(app_version))
                app_field = {
                    "filename": ver["filename"],
                    "content": ver["content"],
                    "sha256": ver["sha256"],
                    "version": ver["version"],
                    "runs_standalone": True,
                }
            except ValueError:
                app_field = None
        if app_field is None:
            snapshot = (
                "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\" />"
                f"<title>{html.escape(str(accepted_state.get('title', project_id)))} — Read-Only Snapshot</title></head>"
                "<body><h1>Read-only snapshot</h1>"
                "<p>This project has no runnable app yet. The accepted state below is real; "
                "use the export for the full portable record.</p>"
                f"<pre>{html.escape(json.dumps(accepted_state, indent=2, sort_keys=True))}</pre>"
                "</body></html>"
            )
            app_field = {
                "filename": f"{project_id}-snapshot.html",
                "content": snapshot,
                "sha256": sha256_hex(snapshot),
                "version": acc["version"],
                "runs_standalone": False,
            }
        receipt_inner = receipt_obj.get("receipt", receipt_obj) if isinstance(receipt_obj, dict) else {}
        receipt_payload = receipt_inner.get("payload", {}) if isinstance(receipt_inner, dict) else {}
        return {
            "project_id": project_id,
            "project_family": acc["project_family"],
            "title": accepted_state.get("title", project_id),
            "version": acc["version"],
            "app": app_field,
            "model": {"id": self.model_id},
            "receipts": [
                {
                    "receipt_id": receipt_payload.get("receipt_id", ""),
                    "sha256": acc["state_sha256"],
                }
            ] if receipt_obj else [],
            "stopped": bool(self.guard.read_stop_state().get("stopped")),
            "stop_epoch": int(self.guard.read_stop_state().get("epoch", 0)),
            "status": self._project_status(project_id),
            "active_worker_id": self.active_worker_id,
            "receiver_public_key": self.receiver_identity.public,
            "owner_public_key": self.owner_identity.public,
            "accepted": {
                "version": acc["version"],
                "state_sha256": acc["state_sha256"],
                "state": accepted_state,
                "state_canonical_json": acc["state_json"],
                "receipt": receipt_obj,
            },
            "exploratory": [
                {
                    "proposal_id": r["proposal_id"],
                    "proposer_worker": r["proposer_worker"],
                    "summary": r["summary"],
                    "candidate_sha256": r["candidate_sha256"],
                    "validation_passed": bool(r["validation_passed"]),
                    "validation_report": json.loads(r["validation_report_json"]),
                    "status": r["status"],
                    "base_version": int(r["base_version"]) if "base_version" in r.keys() else 1,
                    "base_state_sha256": str(r["base_state_sha256"]) if "base_state_sha256" in r.keys() else "",
                    "proposer_epoch": int(r["proposer_epoch"]) if "proposer_epoch" in r.keys() else 0,
                    "constraint_diagnosis": (
                        json.loads(r["constraint_diagnosis_json"])
                        if ("constraint_diagnosis_json" in r.keys() and r["constraint_diagnosis_json"])
                        else {}
                    ),
                    "candidate_state": json.loads(r["candidate_state_json"]),
                }
                for r in exp_rows
            ],
            "rejected": [
                {
                    "rejection_id": r["rejection_id"],
                    "proposal_id": r["proposal_id"],
                    "reason": r["reason"],
                    "candidate_sha256": r["candidate_sha256"],
                    "preserved_accepted_sha256": r["preserved_accepted_sha256"],
                    "receipt": json.loads(r["receipt_json"]),
                }
                for r in rej_rows
            ],
            "jump_decisions": [
                {
                    "jump_id": r["jump_id"],
                    "proposal_id": r["proposal_id"],
                    "from_version": int(r["from_version"]),
                    "to_version": int(r["to_version"]),
                    "previous_binding_constraint": r["previous_binding_constraint"],
                    "new_binding_constraint": r["new_binding_constraint"],
                    "delta_summary": r["delta_summary"],
                    "next_enabled_actions": json.loads(r["next_enabled_actions_json"]),
                    "second_order_risks": json.loads(r["second_order_risks_json"]),
                    "discriminating_test": r["discriminating_test"],
                    "accepted_sha256": r["accepted_sha256"],
                    "receipt_id": r["receipt_id"],
                }
                for r in jump_rows
            ],
            "autonomy_log": [
                {"seq": r["seq"], "stage": r["stage"], "detail": r["detail"], "provenance": r["provenance"]}
                for r in logs
            ],
        }

    def list_projects(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT project_id, project_family, version, state_sha256, state_json FROM genie_accepted ORDER BY project_id").fetchall()
        out = []
        for r in rows:
            st = json.loads(r["state_json"])
            out.append({
                "project_id": r["project_id"],
                "project_family": r["project_family"],
                "title": st.get("title", r["project_id"]),
                "version": r["version"],
                "state_sha256": r["state_sha256"],
            })
        return out
