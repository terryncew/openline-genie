"""Generation 1 (G1) Repaired Compressed Capability: `compressed_trajectory_stabilizer.py`.

Provenance & Repair Disclosure:
  - Authored by Argon engineering lead (`AUTHORED_BY_ARGON_ENGINEER`).
  - Repaired for OpenLine 008 Compression Integrity & Ultimate Dogfood:
      1. **Transitive Dependency-Closure Cache Keys**:
         `_DOMAIN_MOD_CACHE` and `_ENVELOPE_CACHE` are keyed by the cryptographic SHA-256 closure
         (`domain_closure_sha256`) of `rel_path` and all local modules it transitively imports,
         plus `baseline_assumptions_sha256`. Any modification to `rel_path` or a nested imported
         helper module immediately invalidates the stale cache entry, triggers Decision Recall
         `REOPEN` standing on prior decisions, and reloads the updated module graph from verified bytes.
      2. **Cache-Poisoning & Baseline-Tamper Defense**:
         Every cached envelope stores `envelope_integrity_sha256` and every cached domain adapter
         stores `baseline_assumptions_sha256`. In-memory or on-disk cache tampering is detected
         before reuse, evicted, and either fails closed (`fail_on_cache_poison=True`) or rebuilds
         cleanly from verified source bytes.
      3. **Multi-Resource Critical-Epoch Coverage & Unique-State Soundness**:
         Augments `(t_breach, t_worst, t_end)` with per-resource bottleneck minima across all
         breached capacity axes (0 extra baseline evaluations) and verifies any remaining unique
         trajectory state before committing a feasible decision.
      4. **Pre/Post-Execution TOCTOU Concurrency & Atomic Persistence Guard**:
         Verifies dependency closure equality before and after execution and writes any persistent
         envelope cache files via atomic temp-file + `os.replace`.
"""
from __future__ import annotations

import ast
import copy
import heapq
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kernel

# Keyed by (rel_path, domain_closure_sha256) -> (base_fn, comp_fn, patch_fn, baseline_sha256, dep_hashes)
_DOMAIN_MOD_CACHE: dict[tuple[str, str], tuple[Any, Any, Any, str, dict[str, str]]] = {}
# Keyed by (rel_mod, max_steps, domain_closure_sha256, ref_assumptions_sha256) -> (packages, evals, envelope_integrity_sha256)
_ENVELOPE_CACHE: dict[tuple[str, int, str, str], tuple[list[dict[str, Any]], int, str]] = {}
# Tracks last seen closure SHA per rel_path to log invalidation events
_LAST_CLOSURE_BY_MODULE: dict[str, str] = {}
# Audit log of detected & evicted cache poisoning attempts
_CACHE_POISON_EVENTS: list[dict[str, Any]] = []


def invalidate_caches(rel_path: str | None = None) -> None:
    """Explicitly clear domain and envelope caches (globally or for a specific module)."""
    if rel_path is None:
        _DOMAIN_MOD_CACHE.clear()
        _ENVELOPE_CACHE.clear()
        _LAST_CLOSURE_BY_MODULE.clear()
        return
    for k in list(_DOMAIN_MOD_CACHE.keys()):
        if k[0] == rel_path:
            _DOMAIN_MOD_CACHE.pop(k, None)
    for k in list(_ENVELOPE_CACHE.keys()):
        if k[0] == rel_path:
            _ENVELOPE_CACHE.pop(k, None)
    _LAST_CLOSURE_BY_MODULE.pop(rel_path, None)


def _discover_and_load_with_closure(
    rel_path: str,
    use_cache: bool = True,
    *,
    fail_on_cache_poison: bool = False,
) -> tuple[Any, Any, Any, str, str, dict[str, str]]:
    """Resolve transitive dependency closure of `rel_path`, reload changed local imports, and load primitives."""
    p = (ROOT / rel_path).resolve()
    if not p.is_relative_to(ROOT.resolve()) or not p.is_file():
        raise ValueError("unauthorized_or_missing_domain_module")

    closure = kernel.resolve_dependency_closure([rel_path], base_dir=ROOT)
    closure_sha = closure["dependency_closure_sha256"]
    dep_hashes = closure["dependency_hashes"]

    prev_sha = _LAST_CLOSURE_BY_MODULE.get(rel_path)
    if prev_sha is not None and prev_sha != closure_sha:
        kernel.record_dependency_invalidation(rel_path, prev_sha, closure_sha)
    _LAST_CLOSURE_BY_MODULE[rel_path] = closure_sha

    kernel.sync_local_python_modules(closure, base_dir=ROOT)

    cache_key = (rel_path, closure_sha)
    if use_cache and cache_key in _DOMAIN_MOD_CACHE:
        base_fn, comp_fn, patch_fn, expected_base_sha, cached_deps = _DOMAIN_MOD_CACHE[cache_key]
        try:
            live_base_sha = kernel.canonical_sha256(base_fn())
        except Exception:
            live_base_sha = ""
        if live_base_sha == expected_base_sha:
            return base_fn, comp_fn, patch_fn, closure_sha, expected_base_sha, cached_deps
        _DOMAIN_MOD_CACHE.pop(cache_key, None)
        _CACHE_POISON_EVENTS.append({
            "type": "domain_mod_cache_baseline_tamper",
            "module": rel_path,
            "closure_sha256": closure_sha,
        })
        if fail_on_cache_poison:
            raise kernel.ContractError(f"domain_mod_cache_poisoned:{rel_path}")

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

    mod_name = f"domain_mod_{p.stem}_{closure_sha[:12]}"
    mod = kernel.exec_module_from_verified_bytes(mod_name, p, raw_bytes)

    b_fn = getattr(mod, baseline_fn)
    c_fn = getattr(mod, compute_fn)
    p_fn = getattr(mod, patches_fn)
    base_sha = kernel.canonical_sha256(b_fn())

    if use_cache:
        _DOMAIN_MOD_CACHE[cache_key] = (b_fn, c_fn, p_fn, base_sha, dep_hashes)
    return b_fn, c_fn, p_fn, closure_sha, base_sha, dep_hashes


def _discover_and_load(rel_path: str, use_cache: bool = True):
    """Backward-compatible 3-tuple loader bound to transitive dependency closure."""
    b_fn, c_fn, p_fn, _, _, _ = _discover_and_load_with_closure(rel_path, use_cache=use_cache)
    return b_fn, c_fn, p_fn


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
    *,
    fail_on_cache_poison: bool = False,
    persist_cache_dir: Path | None = None,
    interrupt_after_evals: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Compile and cache the evidence-bound upgrade package envelope for `rel_mod`."""
    base_fn, comp_fn, patch_fn, closure_sha, base_sha, dep_hashes = _discover_and_load_with_closure(
        rel_mod,
        use_cache=use_cache,
        fail_on_cache_poison=fail_on_cache_poison,
    )
    init_state = base_fn()
    if reference_assumptions:
        init_state.update(reference_assumptions)
    ref_sha = kernel.canonical_sha256(init_state) if reference_assumptions else base_sha

    sig_key = (rel_mod, max_steps, closure_sha, ref_sha)
    if use_cache and sig_key in _ENVELOPE_CACHE:
        cached_pkgs, cached_evals, expected_env_sha = _ENVELOPE_CACHE[sig_key]
        actual_env_sha = kernel.canonical_sha256(cached_pkgs)
        if actual_env_sha == expected_env_sha:
            return copy.deepcopy(cached_pkgs), 0
        _ENVELOPE_CACHE.pop(sig_key, None)
        _CACHE_POISON_EVENTS.append({
            "type": "envelope_cache_tamper",
            "module": rel_mod,
            "closure_sha256": closure_sha,
            "expected_envelope_sha256": expected_env_sha,
            "actual_envelope_sha256": actual_env_sha,
        })
        if fail_on_cache_poison:
            raise kernel.ContractError(f"envelope_cache_poisoned:{rel_mod}")

    disk_cache_file: Path | None = None
    if use_cache and persist_cache_dir is not None:
        persist_cache_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = rel_mod.replace("/", "__").replace(".", "_")
        disk_cache_file = persist_cache_dir / f"env_{safe_stem}_s{max_steps}_{closure_sha[:16]}_{ref_sha[:16]}.json"
        if disk_cache_file.is_file():
            try:
                payload = json.loads(disk_cache_file.read_text(encoding="utf-8"))
                if (
                    payload.get("domain_closure_sha256") == closure_sha
                    and payload.get("ref_assumptions_sha256") == ref_sha
                    and payload.get("max_steps") == max_steps
                    and kernel.canonical_sha256(payload.get("packages")) == payload.get("envelope_integrity_sha256")
                ):
                    pkgs = payload["packages"]
                    env_sha = payload["envelope_integrity_sha256"]
                    _ENVELOPE_CACHE[sig_key] = (copy.deepcopy(pkgs), int(payload.get("build_evals", 0)), env_sha)
                    return copy.deepcopy(pkgs), 0
                else:
                    disk_cache_file.unlink(missing_ok=True)
                    _CACHE_POISON_EVENTS.append({
                        "type": "disk_envelope_cache_tamper",
                        "module": rel_mod,
                        "file": str(disk_cache_file),
                    })
                    if fail_on_cache_poison:
                        raise kernel.ContractError(f"disk_envelope_cache_poisoned:{rel_mod}")
            except kernel.ContractError:
                raise
            except Exception:
                disk_cache_file.unlink(missing_ok=True)

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
            if interrupt_after_evals is not None and evals >= interrupt_after_evals:
                raise RuntimeError("simulated_interrupted_execution_during_envelope_build")
            nxt_comp = comp_fn(nxt_state)
            evals += 1
            _, nxt_capex, nxt_opex = _extract_metrics(nxt_comp)
            nd_cap = round(nxt_capex - init_capex, 4)
            nd_op = round(nxt_opex - init_opex, 4)
            heapq.heappush(frontier, (nd_cap, nd_op, steps_used + 1, seq + [pid], nxt_state))

    packages_by_state.sort(key=lambda x: (x["capex_delta"], x["opex_delta"], len(x["sequence"]), x["sequence"]))

    post_closure = kernel.resolve_dependency_closure([rel_mod], base_dir=ROOT)
    if post_closure["dependency_closure_sha256"] != closure_sha:
        invalidate_caches(rel_mod)
        raise kernel.ContractError("concurrent_dependency_mutation_toctou")

    env_integrity_sha = kernel.canonical_sha256(packages_by_state)
    if use_cache:
        _ENVELOPE_CACHE[sig_key] = (copy.deepcopy(packages_by_state), evals, env_integrity_sha)
        if disk_cache_file is not None:
            tmp_fd, tmp_name = tempfile.mkstemp(dir=str(persist_cache_dir), prefix=".tmp_env_", suffix=".json")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "domain_module": rel_mod,
                            "max_steps": max_steps,
                            "domain_closure_sha256": closure_sha,
                            "dependency_hashes": dep_hashes,
                            "ref_assumptions_sha256": ref_sha,
                            "envelope_integrity_sha256": env_integrity_sha,
                            "build_evals": evals,
                            "packages": packages_by_state,
                        },
                        f,
                        indent=2,
                        sort_keys=True,
                    )
                os.replace(tmp_name, disk_cache_file)
            except Exception:
                Path(tmp_name).unlink(missing_ok=True)
                raise

    return copy.deepcopy(packages_by_state), evals


def stabilize_trajectory(facts: dict[str, Any]) -> dict[str, Any]:
    """Stabilize a multi-step dynamic trajectory using evidence-bound compressed envelope + conditional escalation."""
    rel_mod = facts.get("domain_module", "upstream/community_garden.py")
    use_cache = bool(facts.get("use_envelope_cache", facts.get("use_cache", True)))
    fail_on_poison = bool(facts.get("fail_on_cache_poison", False))
    persist_dir_str = facts.get("persist_cache_dir")
    persist_dir = Path(persist_dir_str) if persist_dir_str else None
    interrupt_after = facts.get("interrupt_after_evals")

    pre_closure = kernel.resolve_dependency_closure([rel_mod], facts, base_dir=ROOT)
    pre_closure_sha = pre_closure["dependency_closure_sha256"]

    base_fn, comp_fn, patch_fn, _, _, _ = _discover_and_load_with_closure(
        rel_mod,
        use_cache=use_cache,
        fail_on_cache_poison=fail_on_poison,
    )
    traj_assumptions: list[dict[str, Any]] = facts["trajectory_assumptions"]
    target = int(facts["target_throughput"])
    max_capex = float(facts["max_capex_usd"])
    max_cum_opex = float(facts["max_cumulative_opex_delta_usd"])
    max_steps = int(facts.get("max_steps", 3))

    horizon = len(traj_assumptions)
    domain_evals = 0

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

    if callable(facts.get("_on_mid_execution")):
        facts["_on_mid_execution"]()

    breach_steps = [t for t, tp in enumerate(base_tps) if tp < target]
    if not breach_steps:
        post_closure = kernel.resolve_dependency_closure([rel_mod], facts, base_dir=ROOT)
        if post_closure["dependency_closure_sha256"] != pre_closure_sha:
            invalidate_caches(rel_mod)
            raise kernel.ContractError("concurrent_dependency_mutation_toctou")
        return {
            "feasible_stabilization": True,
            "interventions": [],
            "min_stabilized_throughput": min(base_tps),
            "total_capex_usd": 0.0,
            "cumulative_opex_delta_usd": 0.0,
            "escalated_to_staged_solver": False,
            "domain_evaluations": domain_evals,
            "domain_closure_sha256": pre_closure_sha,
        }

    t_breach = breach_steps[0]
    t_end = horizon - 1
    t_worst = min(
        range(t_breach, horizon),
        key=lambda t: (base_tps[t], sum(base_comps[t].get("capacities", {}).values())),
    )

    resource_worst_epochs: set[int] = {t_breach, t_worst, t_end}
    all_cap_keys = set()
    for t in range(t_breach, horizon):
        for rk, rv in base_comps[t].get("capacities", {}).items():
            if int(rv) < target:
                all_cap_keys.add(rk)
    for rk in all_cap_keys:
        t_rk = min(
            range(t_breach, horizon),
            key=lambda t: (int(base_comps[t].get("capacities", {}).get(rk, 10**9)), base_tps[t]),
        )
        resource_worst_epochs.add(t_rk)

    for tc_check in sorted(resource_worst_epochs):
        caps_w = base_comps[tc_check].get("capacities", {})
        for fixed_key in ("demand", "shop", "wash_station", "schedule", "wish", "scenario"):
            if fixed_key in caps_w and int(caps_w[fixed_key]) < target:
                post_closure = kernel.resolve_dependency_closure([rel_mod], facts, base_dir=ROOT)
                if post_closure["dependency_closure_sha256"] != pre_closure_sha:
                    invalidate_caches(rel_mod)
                    raise kernel.ContractError("concurrent_dependency_mutation_toctou")
                return {
                    "feasible_stabilization": False,
                    "interventions": [],
                    "min_stabilized_throughput": min(base_tps),
                    "total_capex_usd": 0.0,
                    "cumulative_opex_delta_usd": 0.0,
                    "escalated_to_staged_solver": False,
                    "domain_evaluations": domain_evals,
                    "domain_closure_sha256": pre_closure_sha,
                }

    packages, env_evals = extract_pareto_upgrade_envelope(
        rel_mod,
        max_steps=max_steps,
        use_cache=use_cache,
        fail_on_cache_poison=fail_on_poison,
        persist_cache_dir=persist_dir,
        interrupt_after_evals=interrupt_after,
    )
    domain_evals += env_evals

    rem_steps_1 = horizon - t_breach
    single_stage_cost_rejected = False
    critical_epochs = sorted(resource_worst_epochs)

    unique_post_breach_epochs: list[int] = []
    seen_state_reprs: set[str] = {repr(sorted(base_states[tc].items())) for tc in critical_epochs}
    for t in range(t_breach, horizon):
        sr = repr(sorted(base_states[t].items()))
        if sr not in seen_state_reprs:
            seen_state_reprs.add(sr)
            unique_post_breach_epochs.append(t)

    for pkg in packages:
        if not pkg["sequence"]:
            continue
        if pkg["capex_delta"] > max_capex + 1e-9:
            continue
        ok_crit = True
        crit_tps: list[int] = []
        verified_capex = pkg["capex_delta"]
        verified_opex_rate = pkg["opex_delta"]
        for tc in critical_epochs:
            st_c = apply_patch_sequence(base_states[tc], pkg["sequence"], patch_fn)
            c_c = comp_fn(st_c)
            domain_evals += 1
            tp_c, cap_c, op_c = _extract_metrics(c_c)
            _, base_cap_c, base_op_c = _extract_metrics(base_comps[tc])
            verified_capex = max(verified_capex, round(cap_c - base_cap_c, 2))
            verified_opex_rate = max(verified_opex_rate, round(op_c - base_op_c, 4))
            if tp_c < target or verified_capex > max_capex + 1e-9:
                ok_crit = False
                break
            crit_tps.append(tp_c)
        if not ok_crit:
            continue

        cum_opex = round(verified_opex_rate * rem_steps_1, 4)
        if cum_opex <= max_cum_opex + 1e-9:
            ok_extra = True
            for te in unique_post_breach_epochs:
                st_e = apply_patch_sequence(base_states[te], pkg["sequence"], patch_fn)
                c_e = comp_fn(st_e)
                domain_evals += 1
                tp_e, _, _ = _extract_metrics(c_e)
                if tp_e < target:
                    ok_extra = False
                    break
                crit_tps.append(tp_e)
            if not ok_extra:
                continue

            post_closure = kernel.resolve_dependency_closure([rel_mod], facts, base_dir=ROOT)
            if post_closure["dependency_closure_sha256"] != pre_closure_sha:
                invalidate_caches(rel_mod)
                raise kernel.ContractError("concurrent_dependency_mutation_toctou")

            min_tp = min([min(base_tps[:t_breach])] + crit_tps) if t_breach > 0 else min(crit_tps)
            return {
                "feasible_stabilization": True,
                "interventions": [{"step": t_breach, "upgrade_sequence": pkg["sequence"]}],
                "min_stabilized_throughput": int(min_tp),
                "total_capex_usd": verified_capex,
                "cumulative_opex_delta_usd": round(cum_opex, 2),
                "escalated_to_staged_solver": False,
                "domain_evaluations": domain_evals,
                "domain_closure_sha256": pre_closure_sha,
            }
        else:
            single_stage_cost_rejected = True

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
            min_tp_stage1 = tp_b
            for t in range(t_breach + 1, horizon):
                st_t = apply_patch_sequence(base_states[t], pkg1["sequence"], patch_fn)
                c_t = comp_fn(st_t)
                domain_evals += 1
                tp_t, _, _ = _extract_metrics(c_t)
                if tp_t < target:
                    t2 = t
                    break
                min_tp_stage1 = min(min_tp_stage1, tp_t)
            if t2 is None:
                continue

            stage2_check_epochs: list[int] = []
            seen_s2: set[str] = set()
            for cand_t in [t_worst if t_worst >= t2 else t2] + list(range(t2, horizon)):
                sr = repr(sorted(base_states[cand_t].items()))
                if sr not in seen_s2:
                    seen_s2.add(sr)
                    stage2_check_epochs.append(cand_t)

            for pkg2 in packages:
                if len(pkg1["sequence"]) + len(pkg2["sequence"]) > max_steps or not pkg2["sequence"]:
                    continue
                comb_seq = pkg1["sequence"] + pkg2["sequence"]
                ok_s2 = True
                s2_tps: list[int] = []
                tot_capex = 0.0
                tot_opex_rate2 = 0.0
                for ts2 in stage2_check_epochs:
                    st_w = apply_patch_sequence(base_states[ts2], comb_seq, patch_fn)
                    c_w = comp_fn(st_w)
                    domain_evals += 1
                    tp_w, cap_w, op_w = _extract_metrics(c_w)
                    if tp_w < target:
                        ok_s2 = False
                        break
                    _, base_cap_w, base_op_w = _extract_metrics(base_comps[ts2])
                    tot_capex = max(tot_capex, round(cap_w - base_cap_w, 2))
                    tot_opex_rate2 = max(tot_opex_rate2, round(op_w - base_op_w, 4))
                    s2_tps.append(tp_w)
                if not ok_s2 or tot_capex > max_capex + 1e-9:
                    continue
                cum_opex = round(pkg1["opex_delta"] * (t2 - t_breach) + tot_opex_rate2 * (horizon - t2), 2)
                if cum_opex <= max_cum_opex + 1e-9:
                    min_tp = min(
                        [min(base_tps[:t_breach])] + [min_tp_stage1] + s2_tps
                        if t_breach > 0
                        else [min_tp_stage1] + s2_tps
                    )
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
                                "domain_closure_sha256": pre_closure_sha,
                            },
                        )
        if best_staged is not None:
            post_closure = kernel.resolve_dependency_closure([rel_mod], facts, base_dir=ROOT)
            if post_closure["dependency_closure_sha256"] != pre_closure_sha:
                invalidate_caches(rel_mod)
                raise kernel.ContractError("concurrent_dependency_mutation_toctou")
            res = best_staged[1]
            res["domain_evaluations"] = domain_evals
            return res

    post_closure = kernel.resolve_dependency_closure([rel_mod], facts, base_dir=ROOT)
    if post_closure["dependency_closure_sha256"] != pre_closure_sha:
        invalidate_caches(rel_mod)
        raise kernel.ContractError("concurrent_dependency_mutation_toctou")

    return {
        "feasible_stabilization": False,
        "interventions": [],
        "min_stabilized_throughput": min(base_tps),
        "total_capex_usd": 0.0,
        "cumulative_opex_delta_usd": 0.0,
        "escalated_to_staged_solver": single_stage_cost_rejected,
        "domain_evaluations": domain_evals,
        "domain_closure_sha256": pre_closure_sha,
    }
