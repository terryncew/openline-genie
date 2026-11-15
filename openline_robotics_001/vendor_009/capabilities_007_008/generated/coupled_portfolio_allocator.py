"""Generation 2 (G2) Compressed Capability: `coupled_portfolio_allocator.py`.

Provenance disclosure:
  - Authored by Argon engineering lead during OpenLine 008 Experiment 2 (`AUTHORED_BY_ARGON_ENGINEER`).
  - Directly reuses Generation 1 (`compressed_trajectory_stabilizer.py`) to achieve cross-task transfer:
    Instead of searching the joint Cartesian product of multi-step trajectories across facilities from scratch,
    G2 calls G1's `extract_pareto_upgrade_envelope` and critical-epoch decomposition to reduce each facility i
    to its small set of feasible trajectory-stabilizing options `{(interventions, capex, cum_opex, min_tp)}`,
    combines them with `upstream/energy_planning.py` (`plan_charge`), and solves the coupled multi-facility
    + microgrid knapsack under `shared_capex_budget_usd` and `shared_daily_ops_budget_usd`.
"""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generated.compressed_trajectory_stabilizer import (
    _discover_and_load,
    _extract_metrics,
    apply_patch_sequence,
    extract_pareto_upgrade_envelope,
)
from upstream import energy_planning


def _enumerate_facility_stabilization_options(
    fac: dict[str, Any],
    max_capex_ceiling: float,
    max_cum_opex_ceiling: float,
    use_g1_compression: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    """Use G1's Pareto envelope + critical-epoch check to extract non-dominated feasible options for one facility."""
    rel_mod = fac["domain_module"]
    traj = fac["trajectory_assumptions"]
    target = int(fac["target_throughput"])
    horizon = len(traj)

    base_fn, comp_fn, patch_fn = _discover_and_load(rel_mod, use_cache=use_g1_compression)
    domain_evals = 0

    base_tps: list[int] = []
    base_states: list[dict[str, Any]] = []
    base_comps: list[dict[str, Any]] = []
    for step_a in traj:
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
        return ([{
            "facility_id": fac.get("facility_id", rel_mod),
            "interventions": [],
            "capex_usd": 0.0,
            "cumulative_opex_usd": 0.0,
            "min_throughput": min(base_tps),
        }], domain_evals)

    t_breach = breach_steps[0]
    t_end = horizon - 1
    t_worst = min(
        range(t_breach, horizon),
        key=lambda t: (base_tps[t], sum(base_comps[t].get("capacities", {}).values())),
    )

    caps_w = base_comps[t_worst].get("capacities", {})
    for fixed_key in ("demand", "shop", "wash_station", "schedule", "wish", "scenario"):
        if fixed_key in caps_w and int(caps_w[fixed_key]) < target:
            return ([], domain_evals)

    packages, env_evals = extract_pareto_upgrade_envelope(rel_mod, max_steps=3, use_cache=use_g1_compression)
    domain_evals += env_evals

    if not use_g1_compression:
        for pkg in packages:
            for t in range(horizon):
                _ = comp_fn(apply_patch_sequence(base_states[t], pkg["sequence"], patch_fn))
                domain_evals += 1

    rem_steps = horizon - t_breach
    critical_epochs = sorted({t_worst, t_breach, t_end})
    valid_options: list[dict[str, Any]] = []

    for pkg in packages:
        if not pkg["sequence"]:
            continue
        if pkg["capex_delta"] > max_capex_ceiling + 1e-9:
            continue
        cum_opex = round(pkg["opex_delta"] * rem_steps, 2)
        if cum_opex <= max_cum_opex_ceiling + 1e-9:
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
            if ok_crit:
                min_tp = min([min(base_tps[:t_breach])] + crit_tps) if t_breach > 0 else min(crit_tps)
                valid_options.append({
                    "facility_id": fac.get("facility_id", rel_mod),
                    "interventions": [{"step": t_breach, "upgrade_sequence": pkg["sequence"]}],
                    "capex_usd": pkg["capex_delta"],
                    "cumulative_opex_usd": cum_opex,
                    "min_throughput": int(min_tp),
                })

    if t_end != t_breach:
        for pkg1 in packages:
            if not pkg1["sequence"] or pkg1["capex_delta"] > max_capex_ceiling + 1e-9:
                continue
            st_b = apply_patch_sequence(base_states[t_breach], pkg1["sequence"], patch_fn)
            tp_b, _, _ = _extract_metrics(comp_fn(st_b))
            domain_evals += 1
            if tp_b < target:
                continue
            st_e = apply_patch_sequence(base_states[t_end], pkg1["sequence"], patch_fn)
            tp_e, _, _ = _extract_metrics(comp_fn(st_e))
            domain_evals += 1
            if tp_e >= target:
                continue
            t2 = t_end
            for t in range(t_breach + 1, horizon):
                tp_t, _, _ = _extract_metrics(comp_fn(apply_patch_sequence(base_states[t], pkg1["sequence"], patch_fn)))
                domain_evals += 1
                if tp_t < target:
                    t2 = t
                    break
            for pkg2 in packages:
                if not pkg2["sequence"] or len(pkg1["sequence"]) + len(pkg2["sequence"]) > 3:
                    continue
                comb_seq = pkg1["sequence"] + pkg2["sequence"]
                st_w = apply_patch_sequence(base_states[t_worst], comb_seq, patch_fn)
                tp_w, cap_w, op_w = _extract_metrics(comp_fn(st_w))
                domain_evals += 1
                if tp_w < target:
                    continue
                _, base_cap_w, base_op_w = _extract_metrics(base_comps[t_worst])
                tot_capex = round(cap_w - base_cap_w, 2)
                tot_opex_rate2 = round(op_w - base_op_w, 4)
                cum_opex = round(pkg1["opex_delta"] * (t2 - t_breach) + tot_opex_rate2 * (horizon - t2), 2)
                if tot_capex <= max_capex_ceiling + 1e-9 and cum_opex <= max_cum_opex_ceiling + 1e-9:
                    valid_options.append({
                        "facility_id": fac.get("facility_id", rel_mod),
                        "interventions": [
                            {"step": t_breach, "upgrade_sequence": pkg1["sequence"]},
                            {"step": t2, "upgrade_sequence": pkg2["sequence"]},
                        ],
                        "capex_usd": tot_capex,
                        "cumulative_opex_usd": cum_opex,
                        "min_throughput": int(min(tp_b, tp_w)),
                    })

    valid_options.sort(key=lambda x: (x["capex_usd"], x["cumulative_opex_usd"], len(x["interventions"])))
    pareto_opts: list[dict[str, Any]] = []
    min_opex_seen = float("inf")
    for opt in valid_options:
        if opt["cumulative_opex_usd"] < min_opex_seen - 1e-9:
            pareto_opts.append(opt)
            min_opex_seen = opt["cumulative_opex_usd"]
    return pareto_opts, domain_evals


def allocate_coupled_portfolio(facts: dict[str, Any]) -> dict[str, Any]:
    """Solve coupled multi-facility + EV microgrid allocation using G1's compressed envelope."""
    facilities: list[dict[str, Any]] = facts["facilities"]
    energy_req: dict[str, Any] = facts["energy_request"]
    shared_capex = float(facts["shared_capex_budget_usd"])
    shared_ops = float(facts["shared_daily_ops_budget_usd"])
    use_g1 = bool(facts.get("use_g1_compression", True))

    tariffs = [
        energy_planning.TariffSlot(
            datetime.fromisoformat(t["start"]),
            datetime.fromisoformat(t["end"]),
            float(t["usd_kwh"]),
        )
        for t in energy_req["tariffs"]
    ]
    charge_plan = asdict(
        energy_planning.plan_charge(
            datetime.fromisoformat(energy_req["now"]),
            datetime.fromisoformat(energy_req["deadline"]),
            float(energy_req["need_grid_kwh"]),
            float(energy_req["charge_power_kw"]),
            tariffs,
            usable_fraction=float(energy_req.get("usable_fraction", 0.85)),
            hard_price_cap=energy_req.get("hard_price_cap"),
        )
    )
    sched_slots = list(charge_plan.get("selected_slot_starts", ()))
    if not charge_plan["feasible_by_deadline"]:
        return {
            "portfolio_feasible": False,
            "facility_plans": [],
            "charge_schedule": [],
            "total_portfolio_capex_usd": 0.0,
            "total_portfolio_ops_usd": 0.0,
            "domain_evaluations": 1,
        }

    energy_cost = round(float(charge_plan["estimated_plan_cost"]), 2)
    remaining_ops_budget = round(shared_ops - energy_cost, 2)
    if remaining_ops_budget < -1e-9:
        return {
            "portfolio_feasible": False,
            "facility_plans": [],
            "charge_schedule": sched_slots,
            "total_portfolio_capex_usd": 0.0,
            "total_portfolio_ops_usd": energy_cost,
            "domain_evaluations": 1,
        }

    fac_curves: list[list[dict[str, Any]]] = []
    total_evals = 1
    for fac in facilities:
        opts, evs = _enumerate_facility_stabilization_options(
            fac,
            max_capex_ceiling=shared_capex,
            max_cum_opex_ceiling=remaining_ops_budget,
            use_g1_compression=use_g1,
        )
        total_evals += evs
        if not opts:
            return {
                "portfolio_feasible": False,
                "facility_plans": [],
                "charge_schedule": sched_slots,
                "total_portfolio_capex_usd": 0.0,
                "total_portfolio_ops_usd": energy_cost,
                "domain_evaluations": total_evals,
            }
        fac_curves.append(opts)

    best_combo = None

    def _search_knapsack(idx: int, chosen: list[dict[str, Any]], acc_cap: float, acc_op: float):
        nonlocal best_combo
        if acc_cap > shared_capex + 1e-9 or acc_op > remaining_ops_budget + 1e-9:
            return
        if idx == len(fac_curves):
            tot_ops = round(acc_op + energy_cost, 2)
            cand_key = (round(acc_cap, 2), tot_ops)
            if best_combo is None or cand_key < best_combo[0]:
                best_combo = (cand_key, list(chosen))
            return
        for opt in fac_curves[idx]:
            _search_knapsack(idx + 1, chosen + [opt], acc_cap + opt["capex_usd"], acc_op + opt["cumulative_opex_usd"])

    _search_knapsack(0, [], 0.0, 0.0)

    if best_combo is None:
        return {
            "portfolio_feasible": False,
            "facility_plans": [],
            "charge_schedule": sched_slots,
            "total_portfolio_capex_usd": 0.0,
            "total_portfolio_ops_usd": energy_cost,
            "domain_evaluations": total_evals,
        }

    (tot_cap, tot_ops), plans = best_combo
    return {
        "portfolio_feasible": True,
        "facility_plans": plans,
        "charge_schedule": sched_slots,
        "total_portfolio_capex_usd": tot_cap,
        "total_portfolio_ops_usd": tot_ops,
        "domain_evaluations": total_evals,
    }
