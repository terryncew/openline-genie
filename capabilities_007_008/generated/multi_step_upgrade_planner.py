"""Auto-synthesized Candidate v2 (Repaired for Transitive Dependency Closure):
Exact Bounded Dijkstra Frontier Multi-Step Upgrade Planner (`generated/multi_step_upgrade_planner.py`).
"""
from __future__ import annotations

import ast
import copy
import heapq
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kernel


def _discover_and_load(rel_path: str):
    p = (ROOT / rel_path).resolve()
    if not p.is_relative_to(ROOT.resolve()) or not p.is_file():
        raise ValueError("unauthorized_or_missing_domain_module")
    closure = kernel.resolve_dependency_closure([rel_path], base_dir=ROOT)
    kernel.sync_local_python_modules(closure, base_dir=ROOT)
    raw_bytes = kernel.check_dependency_permission_and_read(p, ROOT)
    tree = ast.parse(raw_bytes.decode("utf-8"))
    baseline_fn = compute_fn = patches_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            b_src = ast.unparse(node)
            if len(node.args.args) == 0 and "deepcopy(" in b_src and "ASSUMPTIONS" in b_src:
                baseline_fn = node.name
            elif len(node.args.args) >= 1 and "capacities" in b_src and "bottleneck_id" in b_src and "min(" in b_src:
                compute_fn = node.name
            elif len(node.args.args) == 1 and isinstance(node.body[-1], ast.Return) and isinstance(node.body[-1].value, ast.Dict):
                if "capex_usd" not in b_src and "computed" not in b_src:
                    patches_fn = node.name
    if not (baseline_fn and compute_fn and patches_fn):
        raise ValueError("missing_domain_primitives")
    spec = importlib.util.spec_from_file_location(f"domain_mod_{p.stem}_{closure['dependency_closure_sha256'][:12]}", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, baseline_fn), getattr(mod, compute_fn), getattr(mod, patches_fn)


def _extract_metrics(comp: dict[str, Any]) -> tuple[int, float, float]:
    tp_key = next(k for k in comp if k.startswith("throughput_") and not k.startswith("throughput_band"))
    cost_key = next(k for k in comp if k.endswith("_cost_usd") or k.endswith("_cost_usd_per_day"))
    return int(comp[tp_key]), float(comp["capex_usd"]), float(comp[cost_key])


def _state_key(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def plan_multi_step_upgrade(facts: dict[str, Any]) -> dict[str, Any]:
    rel_mod = facts.get("domain_module", "upstream/community_garden.py")
    base_fn, comp_fn, patch_fn = _discover_and_load(rel_mod)
    init_state = base_fn()
    init_state.update(facts.get("assumptions", {}))
    target = int(facts["target_throughput"])
    max_capex = float(facts["max_capex_usd"])
    max_opex_delta = float(facts.get("max_periodic_cost_delta_usd", 1e9))
    max_steps = int(facts.get("max_steps", 4))
    if target <= 0 or max_capex < 0 or max_opex_delta < 0 or not (1 <= max_steps <= 6):
        raise ValueError("invalid_upgrade_planning_bounds")

    init_comp = comp_fn(init_state)
    init_tp, init_capex, init_opex = _extract_metrics(init_comp)

    pq: list[tuple[float, float, int, int, list[str], dict[str, Any], dict[str, Any]]] = [
        (0.0, 0.0, 0, -init_tp, [], init_state, init_comp)
    ]
    visited: dict[str, tuple[float, float, int]] = {_state_key(init_state): (0.0, 0.0, 0)}

    best_fallback = (0.0, 0.0, 0, init_tp, [], init_comp)

    while pq:
        d_capex, d_opex, steps, neg_tp, seq, cur_state, cur_comp = heapq.heappop(pq)
        cur_tp = -neg_tp
        if cur_tp > best_fallback[3] or (cur_tp == best_fallback[3] and (d_capex, d_opex, steps) < best_fallback[:3]):
            best_fallback = (d_capex, d_opex, steps, cur_tp, seq, cur_comp)

        if cur_tp >= target:
            return {
                "upgrade_sequence": seq,
                "unlocked_throughput": cur_tp,
                "total_capex_usd": round(d_capex, 2),
                "periodic_cost_delta_usd": round(d_opex, 2),
                "feasible_upgrade": True,
                "final_bottleneck": cur_comp["bottleneck_id"],
            }

        if steps >= max_steps:
            continue

        for pid, patch in sorted(patch_fn(cur_state).items()):
            nxt_state = copy.deepcopy(cur_state)
            nxt_state.update(patch)
            if nxt_state == cur_state:
                continue
            nxt_comp = comp_fn(nxt_state)
            nxt_tp, nxt_capex, nxt_opex = _extract_metrics(nxt_comp)
            nxt_d_capex = round(nxt_capex - init_capex, 4)
            nxt_d_opex = round(nxt_opex - init_opex, 4)
            if nxt_d_capex > max_capex + 1e-9 or nxt_d_opex > max_opex_delta + 1e-9:
                continue
            sk = _state_key(nxt_state)
            cost_tuple = (nxt_d_capex, nxt_d_opex, steps + 1)
            if sk not in visited or cost_tuple < visited[sk]:
                visited[sk] = cost_tuple
                heapq.heappush(pq, (nxt_d_capex, nxt_d_opex, steps + 1, -nxt_tp, seq + [pid], nxt_state, nxt_comp))

    return {
        "upgrade_sequence": [],
        "unlocked_throughput": init_tp,
        "total_capex_usd": 0.0,
        "periodic_cost_delta_usd": 0.0,
        "feasible_upgrade": False,
        "final_bottleneck": init_comp["bottleneck_id"],
    }
