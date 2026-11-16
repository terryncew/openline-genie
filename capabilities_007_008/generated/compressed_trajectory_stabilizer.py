"""Generation 1 (G1) Compressed Capability: `compressed_trajectory_stabilizer.py`.

Provenance disclosure:
  - Authored by Argon engineering lead during OpenLine 008 Experiment 1 (`AUTHORED_BY_ARGON_ENGINEER`).
  - Compresses the full joint space-time dynamic programming / branch-and-bound trajectory solver
    (`solve_trajectory_strong_afresh`) into a two-tier reusable mechanism:
      1. **Cached 1D Pareto Bottleneck-Envelope Compiler (`extract_pareto_upgrade_envelope`)**:
         Exploits monotonicity and additive CapEx/OpEx structure of OpenLine domain models
         (`upstream/community_garden.py`, `upstream/bakery.py`) to pre-index the non-dominated
         upgrade packages once per domain module (`~22` domain evaluations, cached across uses).
      2. **Critical-Epoch Decomposition + Conditional Escalation (`stabilize_trajectory`)**:
         Identifies the critical epochs `(t_breach, t_worst, t_end)` along the trajectory.
         Solves single-stage stabilization in `O(|F*|)` (`~24` total domain calls including baseline
         trajectory scan) and escalates to the staged 2-epoch search (`(t_1: u_1, t_2: u_2)`)
         ONLY when cumulative remaining-horizon OpEx constraints reject all single-stage packages (`escalated=True`).
"""
from __future__ import annotations
import ast
import copy
import heapq
import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

_DOMAIN_MOD_CACHE: dict[str, tuple[Any, Any, Any]] = {}
_ENVELOPE_CACHE: dict[tuple[str, int], tuple[list[dict[str, Any]], int]] = {}


def _discover_and_load(rel_path: str, use_cache: bool = True):
    if use_cache and rel_path in _DOMAIN_MOD_CACHE:
        return _DOMAIN_MOD_CACHE[rel_path]
    p = (ROOT / rel_path).resolve()
    if not p.is_relative_to(ROOT.resolve()) or not p.is_file():
        raise ValueError("unauthorized_or_missing_domain_module")
    tree = ast.parse(p.read_text())
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
    spec = importlib.util.spec_from_file_location("domain_mod_" + p.stem, p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = (getattr(mod, baseline_fn), getattr(mod, compute_fn), getattr(mod, patches_fn))
    if use_cache:
        _DOMAIN_MOD_CACHE[rel_path] = res
    return res


def _extract_metrics(comp: dict[str, Any]) -> tuple[int, float, float]:
    tp_key = next(k for k in comp if k.startswith("throughput_") and not k.startswith("throughput_band"))
    cost_key = next(k for k in comp if k.endswith("_cost_usd") or k.endswith("_cost_usd_per_day"))
    return int(comp[tp_key]), float(comp["capex_usd"]), float(comp[cost_key])


def apply_patch_sequence(state: dict[str, Any], seq: list[str], patch_fn) -> dict[str, Any]:
    cur = copy.deepcopy(state)
    for pid in seq:
        patches = patch_fn(cur)
        if pid in patches:
            cur.update(patches[pid])
    return cur


def extract_pareto_upgrade_envelope(
    rel_mod: str,
    reference_assumptions: dict[str, Any] | None = None,
    max_steps: int = 3,
    use_cache: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    """Compile the non-dominated upgrade package envelope for `rel_mod`."""
    sig_key = (rel_mod, max_steps)
    if use_cache and sig_key in _ENVELOPE_CACHE:
        return _ENVELOPE_CACHE[sig_key][0], 0

    base_fn, comp_fn, patch_fn = _discover_and_load(rel_mod, use_cache=use_cache)
    init_state = base_fn()
    evals = 0
    init_comp = comp_fn(init_state)
    evals += 1
    _, init_capex, init_opex = _extract_metrics(init_comp)

    frontier: list[tuple[float, float, int, list[str], dict[str, Any]]] = [(0.0, 0.0, 0, [], init_state)]
    visited: dict[str, tuple[float, float, int]] = {}
    packages_by_state: list[dict[str, Any]] = []

    while frontier:
        d_cap, d_op, steps_used, seq, cur_state = heapq.heappop(frontier)
        state_key = repr(sorted(cur_state.items()))
        if state_key in visited:
            prev_cap, prev_op, prev_len = visited[state_key]
            if prev_cap <= d_cap + 1e-9 and prev_op <= d_op + 1e-9 and prev_len <= steps_used:
                continue
        visited[state_key] = (d_cap, d_op, steps_used)
        packages_by_state.append({
            "sequence": seq,
            "capex_delta": round(d_cap, 2),
            "opex_delta": round(d_op, 2),
        })
        if steps_used >= max_steps:
            continue
        for pid, patch in sorted(patch_fn(cur_state).items()):
            nxt_state = copy.deepcopy(cur_state)
            nxt_state.update(patch)
            if nxt_state == cur_state:
                continue
            nxt_comp = comp_fn(nxt_state)
            evals += 1
            _, nxt_capex, nxt_opex = _extract_metrics(nxt_comp)
            nd_cap = round(nxt_capex - init_capex, 4)
            nd_op = round(nxt_opex - init_opex, 4)
            heapq.heappush(frontier, (nd_cap, nd_op, steps_used + 1, seq + [pid], nxt_state))

    packages_by_state.sort(key=lambda x: (x["capex_delta"], x["opex_delta"], len(x["sequence"]), x["sequence"]))
    if use_cache:
        _ENVELOPE_CACHE[sig_key] = (packages_by_state, evals)
    return packages_by_state, evals


def stabilize_trajectory(facts: dict[str, Any]) -> dict[str, Any]:
    """Stabilize a multi-step dynamic trajectory using compressed envelope + conditional escalation."""
    rel_mod = facts.get("domain_module", "upstream/community_garden.py")
    use_cache = bool(facts.get("use_envelope_cache", True))
    base_fn, comp_fn, patch_fn = _discover_and_load(rel_mod, use_cache=use_cache)
    traj_assumptions: list[dict[str, Any]] = facts["trajectory_assumptions"]
    target = int(facts["target_throughput"])
    max_capex = float(facts["max_capex_usd"])
    max_cum_opex = float(facts["max_cumulative_opex_delta_usd"])
    max_steps = int(facts.get("max_steps", 3))

    horizon = len(traj_assumptions)
    domain_evals = 0

    # 1. Evaluate baseline trajectory to find first breach t_breach and critical trough epochs
    base_tps: list[int] = []
    base_states: list[dict[str, Any]] = []
    base_comps: list[dict[str, Any]] = []
    for step_a in traj_assumptions:
        st = base_fn()
        st.update(step_a)
        base_states.append(st)
        c = comp_fn(st)
        domain_evals += 1
        base_comps.append(c)
        tp, _, _ = _extract_metrics(c)
        base_tps.append(tp)

    breach_steps = [t for t, tp in enumerate(base_tps) if tp < target]
    if not breach_steps:
        return {
            "feasible_stabilization": True,
            "interventions": [],
            "min_stabilized_throughput": min(base_tps),
            "total_capex_usd": 0.0,
            "cumulative_opex_delta_usd": 0.0,
            "escalated_to_staged_solver": False,
            "domain_evaluations": domain_evals,
        }

    t_breach = breach_steps[0]
    t_end = horizon - 1
    # Select t_worst by smallest sum of capacities (breaking throughput ties toward deeper multi-resource shocks)
    t_worst = min(
        range(t_breach, horizon),
        key=lambda t: (base_tps[t], sum(base_comps[t].get("capacities", {}).values())),
    )

    # Fast ceiling pre-check on t_worst: if un-upgradeable ceiling (shop/demand/wash_station) < target, fail immediately in 0 extra evals!
    caps_w = base_comps[t_worst].get("capacities", {})
    for fixed_key in ("demand", "shop", "wash_station", "schedule", "wish", "scenario"):
        if fixed_key in caps_w and int(caps_w[fixed_key]) < target:
            return {
                "feasible_stabilization": False,
                "interventions": [],
                "min_stabilized_throughput": min(base_tps),
                "total_capex_usd": 0.0,
                "cumulative_opex_delta_usd": 0.0,
                "escalated_to_staged_solver": False,
                "domain_evaluations": domain_evals,
            }

    # 2. Tier 1: Query compressed upgrade envelope at critical epochs (t_worst, t_breach, t_end)
    packages, env_evals = extract_pareto_upgrade_envelope(rel_mod, max_steps=max_steps, use_cache=use_cache)
    domain_evals += env_evals

    rem_steps_1 = horizon - t_breach
    single_stage_cost_rejected = False
    critical_epochs = sorted({t_worst, t_breach, t_end})

    for pkg in packages:
        if not pkg["sequence"]:
            continue
        if pkg["capex_delta"] > max_capex + 1e-9:
            continue
        cum_opex = round(pkg["opex_delta"] * rem_steps_1, 4)
        ok_crit = True
        crit_tps = []
        for tc in critical_epochs:
            st_c = apply_patch_sequence(base_states[tc], pkg["sequence"], patch_fn)
            c_c = comp_fn(st_c)
            domain_evals += 1
            tp_c, _, _ = _extract_metrics(c_c)
            if tp_c < target:
                ok_crit = False
                break
            crit_tps.append(tp_c)
        if not ok_crit:
            continue

        if cum_opex <= max_cum_opex + 1e-9:
            min_tp = min([min(base_tps[:t_breach])] + crit_tps) if t_breach > 0 else min(crit_tps)
            return {
                "feasible_stabilization": True,
                "interventions": [{"step": t_breach, "upgrade_sequence": pkg["sequence"]}],
                "min_stabilized_throughput": int(min_tp),
                "total_capex_usd": pkg["capex_delta"],
                "cumulative_opex_delta_usd": round(cum_opex, 2),
                "escalated_to_staged_solver": False,
                "domain_evaluations": domain_evals,
            }
        else:
            single_stage_cost_rejected = True

    # 3. Tier 2: Conditional Escalation to Staged 2-Epoch Solver when single-stage OpEx exceeds cumulative budget
    if single_stage_cost_rejected:
        best_staged = None
        for pkg1 in packages:
            if not pkg1["sequence"] or pkg1["capex_delta"] > max_capex + 1e-9:
                continue
            st_b = apply_patch_sequence(base_states[t_breach], pkg1["sequence"], patch_fn)
            c_b = comp_fn(st_b)
            domain_evals += 1
            tp_b, _, _ = _extract_metrics(c_b)
            if tp_b < target:
                continue
            t2 = None
            for t in range(t_breach + 1, horizon):
                st_t = apply_patch_sequence(base_states[t], pkg1["sequence"], patch_fn)
                c_t = comp_fn(st_t)
                domain_evals += 1
                tp_t, _, _ = _extract_metrics(c_t)
                if tp_t < target:
                    t2 = t
                    break
            if t2 is None:
                continue
            for pkg2 in packages:
                if len(pkg1["sequence"]) + len(pkg2["sequence"]) > max_steps or not pkg2["sequence"]:
                    continue
                comb_seq = pkg1["sequence"] + pkg2["sequence"]
                st_w = apply_patch_sequence(base_states[t_worst], comb_seq, patch_fn)
                c_w = comp_fn(st_w)
                domain_evals += 1
                tp_w, cap_w, op_w = _extract_metrics(c_w)
                if tp_w < target:
                    continue
                _, base_cap_w, base_op_w = _extract_metrics(base_comps[t_worst])
                tot_capex = round(cap_w - base_cap_w, 2)
                tot_opex_rate2 = round(op_w - base_op_w, 4)
                if tot_capex > max_capex + 1e-9:
                    continue
                cum_opex = round(pkg1["opex_delta"] * (t2 - t_breach) + tot_opex_rate2 * (horizon - t2), 2)
                if cum_opex <= max_cum_opex + 1e-9:
                    min_tp = min(min(base_tps[:t_breach]) if t_breach > 0 else tp_b, tp_b, tp_w)
                    cand_key = (tot_capex, cum_opex, len(comb_seq))
                    if best_staged is None or cand_key < best_staged[0]:
                        best_staged = (
                            cand_key,
                            {
                                "feasible_stabilization": True,
                                "interventions": [
                                    {"step": t_breach, "upgrade_sequence": pkg1["sequence"]},
                                    {"step": t2, "upgrade_sequence": pkg2["sequence"]},
                                ],
                                "min_stabilized_throughput": int(min_tp),
                                "total_capex_usd": tot_capex,
                                "cumulative_opex_delta_usd": cum_opex,
                                "escalated_to_staged_solver": True,
                                "domain_evaluations": domain_evals,
                            },
                        )
        if best_staged is not None:
            res = best_staged[1]
            res["domain_evaluations"] = domain_evals
            return res

    return {
        "feasible_stabilization": False,
        "interventions": [],
        "min_stabilized_throughput": min(base_tps),
        "total_capex_usd": 0.0,
        "cumulative_opex_delta_usd": 0.0,
        "escalated_to_staged_solver": single_stage_cost_rejected,
        "domain_evaluations": domain_evals,
    }
