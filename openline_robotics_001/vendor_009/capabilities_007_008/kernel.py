"""OpenLine 008 Capability-Applicability and Execution Kernel (`src_008/kernel.py`).

Extends the audited GPT-6 Reflex CP1 kernel (`recovered_reflex/src_007/kernel.py`) with:
  1. Strict Zero-Oracle / Zero-Label-Leakage Gate (`REFUSE_LABEL_LEAKAGE` if any protected
     evaluation key appears anywhere in `task` or `facts`).
  2. Cryptographic SHA-256 source-integrity verification before and after capability selection,
     plus hash-pinned module caching so verified capabilities retain in-memory compiled envelopes
     without re-importing unchanged source files on every call.
  3. Execution receipts (`execution_receipt`) recording capability ID, source SHA-256,
     input SHA-256, output SHA-256, and elapsed microseconds.
  4. Support for OpenLine 008 compressed capabilities:
     - `compressed-trajectory-stabilizer` (Generation 1: Experiment 1)
     - `coupled-portfolio-allocator` (Generation 2: Experiment 2)
     - `distilled-artifact-gate` (Generation 3: Experiment 2 & 3)
"""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parent
DISPOSITIONS = {"EXECUTED", "INVESTIGATE", "REFUSE", "STOP", "DENY"}
FORBIDDEN_ORACLE_KEYS = {
    "expected",
    "gold_action",
    "gold_lang",
    "true_cause",
    "incident_next",
    "protected_answer",
    "ground_truth",
    "true_label",
    "hidden_ground_truth",
}

_PINNED_MOD_CACHE: dict[tuple[str, str], Any] = {}


class ContractError(ValueError):
    pass


def _mod(name: str, path: Path, expected_sha256: str):
    key = (str(path.resolve()), expected_sha256)
    if key in _PINNED_MOD_CACHE:
        return _PINNED_MOD_CACHE[key]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    _PINNED_MOD_CACHE[key] = m
    return m


def _contains_forbidden_oracle_key(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_ORACLE_KEYS:
                return str(k)
            sub = _contains_forbidden_oracle_key(v)
            if sub:
                return sub
    elif isinstance(obj, list):
        for item in obj:
            sub = _contains_forbidden_oracle_key(item)
            if sub:
                return sub
    return None


def load_registry(registry_path: Path | None = None) -> dict[str, Any]:
    rpath = registry_path or (ROOT / "registry.json")
    reg = json.loads(rpath.read_text())
    for cap in reg["capabilities"]:
        p = (ROOT / cap["relative_source"]).resolve()
        if not p.is_relative_to(ROOT.resolve()) or not p.is_file() or sha256(p.read_bytes()).hexdigest() != cap["source_sha256"]:
            raise ContractError("source_integrity:" + cap["id"])
        if not set(cap["required_facts"]).issubset(cap["accepted_facts"]):
            raise ContractError("invalid_contract:" + cap["id"])
    return reg


def _is_finite_num(x: Any) -> bool:
    return type(x) in (float, int) and math.isfinite(x)


def structural_witness(cap: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, str]:
    required = set(cap["required_facts"])
    if not required.issubset(facts):
        return False, "missing:" + ",".join(sorted(required - set(facts)))
    kind = cap["id"]
    if kind == "energy-charge":
        if not isinstance(facts.get("tariffs"), list) or not facts["tariffs"]:
            return False, "missing_tariffs"
        if not all(isinstance(t, dict) and {"start", "end", "usd_kwh"} <= set(t) for t in facts["tariffs"]):
            return False, "malformed_tariffs"
        if not (_is_finite_num(facts["need_grid_kwh"]) and _is_finite_num(facts["charge_power_kw"])):
            return False, "malformed_power"
    elif kind == "garden-capacity":
        if not isinstance(facts.get("assumptions"), dict):
            return False, "assumptions_not_mapping"
        allowed = set(cap["accepted_facts_inside"])
        if not set(facts["assumptions"]) <= allowed:
            return False, "unsupported_garden_field"
    elif kind == "bounded-diagnosis":
        if not isinstance(facts["probes"], list) or not isinstance(facts["prices"], list) or not isinstance(facts["patterns"], list):
            return False, "malformed_diagnostic_panel"
        if not facts["probes"] or len(facts["probes"]) != len(facts["prices"]) or any(not _is_finite_num(v) or v <= 0 for v in facts["prices"]):
            return False, "invalid_probe_costs"
        if len(set(facts["probes"])) != len(facts["probes"]):
            return False, "duplicate_probes"
        if not all(isinstance(p, (list, tuple)) and len(p) == 2 and len(p[0]) == len(facts["probes"]) and type(p[1]) is int and p[1] > 0 for p in facts["patterns"]):
            return False, "bad_pattern"
        if not isinstance(facts["history"], list):
            return False, "bad_history"
    elif kind == "multi-step-upgrade-planner":
        if not isinstance(facts.get("assumptions"), dict):
            return False, "assumptions_not_mapping"
        if not (_is_finite_num(facts.get("target_throughput")) and facts["target_throughput"] > 0):
            return False, "invalid_target_throughput"
        if not (_is_finite_num(facts.get("max_capex_usd")) and facts["max_capex_usd"] >= 0):
            return False, "invalid_max_capex_usd"
        if "max_periodic_cost_delta_usd" in facts and (not _is_finite_num(facts["max_periodic_cost_delta_usd"]) or facts["max_periodic_cost_delta_usd"] < 0):
            return False, "invalid_max_periodic_cost_delta_usd"
    elif kind == "vkd-one-step-garden":
        if not isinstance(facts.get("assumptions"), dict):
            return False, "assumptions_not_mapping"
        if not all(_is_finite_num(facts.get(k)) for k in ("target_throughput", "max_capex_usd", "max_periodic_cost_delta_usd")):
            return False, "invalid_bounds"
    elif kind == "reflex-shadow-study":
        if "streams" in facts and not isinstance(facts["streams"], list):
            return False, "streams_not_list"
    elif kind == "compressed-trajectory-stabilizer":
        if not isinstance(facts.get("trajectory_assumptions"), list) or len(facts["trajectory_assumptions"]) < 2:
            return False, "invalid_trajectory_assumptions"
        if not (_is_finite_num(facts.get("target_throughput")) and facts["target_throughput"] > 0):
            return False, "invalid_target_throughput"
        if not (_is_finite_num(facts.get("max_capex_usd")) and facts["max_capex_usd"] >= 0):
            return False, "invalid_max_capex_usd"
        if not (_is_finite_num(facts.get("max_cumulative_opex_delta_usd")) and facts["max_cumulative_opex_delta_usd"] >= 0):
            return False, "invalid_max_cumulative_opex_delta_usd"
    elif kind == "coupled-portfolio-allocator":
        if not isinstance(facts.get("facilities"), list) or not facts["facilities"]:
            return False, "invalid_facilities"
        if not isinstance(facts.get("energy_request"), dict):
            return False, "invalid_energy_request"
        if not (_is_finite_num(facts.get("shared_capex_budget_usd")) and facts["shared_capex_budget_usd"] >= 0):
            return False, "invalid_shared_capex_budget"
        if not (_is_finite_num(facts.get("shared_daily_ops_budget_usd")) and facts["shared_daily_ops_budget_usd"] >= 0):
            return False, "invalid_shared_daily_ops_budget"
    elif kind == "distilled-artifact-gate":
        if not isinstance(facts.get("artifact_text"), str) or not facts["artifact_text"]:
            return False, "invalid_artifact_text"
    else:
        return False, "unknown_capability"
    return True, "schema_witness"


def run_capability(cap: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    """Always execute actual pinned implementations, never a precomputed answer."""
    p = (ROOT / cap["relative_source"]).resolve()
    actual_sha = sha256(p.read_bytes()).hexdigest()
    if not p.is_relative_to(ROOT.resolve()) or actual_sha != cap["source_sha256"]:
        raise ContractError("source_changed_after_selection")
    mod = _mod(cap["id"].replace("-", "_"), p, actual_sha)
    if cap["id"] == "energy-charge":
        tariffs = [
            mod.TariffSlot(datetime.fromisoformat(t["start"]), datetime.fromisoformat(t["end"]), float(t["usd_kwh"]))
            for t in facts["tariffs"]
        ]
        p_res = mod.plan_charge(
            datetime.fromisoformat(facts["now"]),
            datetime.fromisoformat(facts["deadline"]),
            facts["need_grid_kwh"],
            facts["charge_power_kw"],
            tariffs,
            usable_fraction=facts.get("usable_fraction", 0.85),
            hard_price_cap=facts.get("hard_price_cap"),
        )
        return asdict(p_res)
    if cap["id"] == "garden-capacity":
        return mod.compute_garden(facts["assumptions"])
    if cap["id"] == "bounded-diagnosis":
        return mod.recommend("conventional", facts["probes"], facts["prices"], facts["patterns"], facts["history"])
    if cap["id"] == "multi-step-upgrade-planner":
        return mod.plan_multi_step_upgrade(facts)
    if cap["id"] == "vkd-one-step-garden":
        return mod.run(facts)
    if cap["id"] == "reflex-shadow-study":
        return mod.run(facts)
    if cap["id"] == "compressed-trajectory-stabilizer":
        return mod.stabilize_trajectory(facts)
    if cap["id"] == "coupled-portfolio-allocator":
        return mod.allocate_coupled_portfolio(facts)
    if cap["id"] == "distilled-artifact-gate":
        return mod.triage_and_stabilize(facts)
    raise ContractError("unknown_executor")


def execute(task: dict[str, Any], registry_path: Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    if not isinstance(task, dict):
        return {"disposition": "DENY", "reason": "invalid_task"}
    limits = task.get("constraints", {})
    if not isinstance(limits, dict):
        return {"disposition": "DENY", "reason": "invalid_constraints"}
    if limits.get("owner_stop") is True:
        return {"disposition": "STOP", "reason": "owner_stop", "executed": []}
    if limits.get("requires_external_effect") is True:
        return {"disposition": "DENY", "reason": "owner_effect_not_authorized", "executed": []}
    facts = task.get("facts")
    outputs = task.get("required_outputs")
    if not isinstance(facts, dict) or not isinstance(outputs, list) or not outputs or len(outputs) != len(set(outputs)) or any(not isinstance(x, str) for x in outputs):
        return {"disposition": "INVESTIGATE", "reason": "missing_explicit_requirements", "executed": []}

    if limits.get("strict_zero_oracle", False):
        leaked = _contains_forbidden_oracle_key(task)
        if leaked:
            return {"disposition": "REFUSE", "reason": f"REFUSE_LABEL_LEAKAGE:{leaked}", "executed": []}

    caps = registry["capabilities"]
    witnesses = {c["id"]: structural_witness(c, facts) for c in caps}
    eligible = [c for c in caps if witnesses[c["id"]][0] and c["status"] == "SCOPED_TESTED_LOCAL"]
    uncovered = set(outputs)
    chosen = []
    while uncovered:
        offers = [(len(uncovered & set(c["provides"])), c) for c in eligible if c not in chosen]
        offers = [(coverage, c) for coverage, c in offers if coverage]
        if not offers:
            break
        coverage, selected = min(offers, key=lambda x: (x[1]["relative_cost_units"] / x[0], -x[0], x[1]["id"]))
        chosen.append(selected)
        uncovered -= set(selected["provides"])
    if uncovered:
        return {
            "disposition": "INVESTIGATE",
            "reason": "uncovered_requirements",
            "missing": sorted(uncovered),
            "witnesses": witnesses,
            "executed": [],
        }
    budget = limits.get("max_relative_cost_units", 100)
    if not _is_finite_num(budget) or budget < 0:
        return {"disposition": "DENY", "reason": "invalid_budget", "executed": []}
    cost = sum(c["relative_cost_units"] for c in chosen)
    if cost > budget:
        return {"disposition": "REFUSE", "reason": "budget_exceeded", "needed_relative_cost_units": cost, "executed": []}
    results = []
    for cap in chosen:
        t0 = time.perf_counter_ns()
        try:
            value = run_capability(cap, facts)
            elapsed_us = round((time.perf_counter_ns() - t0) / 1000.0, 2)
            inp_sha = sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()
            out_sha = sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
            item_dict = {
                "capability": cap["id"],
                "source_sha256": cap["source_sha256"],
                "result": value,
            }
            if limits.get("strict_zero_oracle", False) or limits.get("include_receipts", False):
                item_dict["receipt"] = {
                    "capability_id": cap["id"],
                    "source_sha256": cap["source_sha256"],
                    "input_sha256": inp_sha,
                    "output_sha256": out_sha,
                    "elapsed_us": elapsed_us,
                }
            results.append(item_dict)
        except (ValueError, KeyError, TypeError, OverflowError, ContractError) as exc:
            return {
                "disposition": "INVESTIGATE",
                "reason": "executor_preconditions_failed",
                "error_type": type(exc).__name__,
                "executed": [],
                "no_owner_effects": True,
            }
    return {
        "disposition": "EXECUTED",
        "executed": results,
        "relative_cost_units": cost,
        "no_owner_effects": True,
        "note": "Local simulated results; no automatic owner-authorized effects",
    }
