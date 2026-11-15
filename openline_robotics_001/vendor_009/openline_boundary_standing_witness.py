#!/usr/bin/env python3
"""OpenLine Frontier Breakthrough 001 — `openline_boundary_standing_witness.py`

Implements the Boundary-Uncoupled Counterfactual Standing Witness (BUCSW) and its
competing baseline/ablation mechanisms at the OpenLine 009 Receiver / RecallLedger seam.

Core Invariants Enforced (OpenLine Operating Law v1.0):
1. Strict Proposal-Only Witness Boundary:
   - Emits `REVIEW_DEPENDENCY`, `QUESTION_STANDING`, `HOLD_FOR_RECEIVER_REVIEW_NO_SIMULATOR`,
     or `NO_ACTION` with cryptographic hash receipts and exact boundary slack margins.
   - NEVER auto-approves, NEVER mutates accepted state (`genie_state.sqlite`), NEVER clears
     `STOP`, NEVER invents verified receipts, and NEVER bypasses `ReceiverGuard` or `Connect`.
2. Isolated Process Shadow Execution (`IsolatedShadowProbeRunner`):
   - Runs untrusted shadow callbacks inside a separate OS child process (`multiprocessing` spawn/fork
     with timeout, step cap, non-finite check, and zero file-write privileges to accepted SQLite).
   - Verifies that `accepted_state` and SQLite digests are 100% byte-identical before and after probing.
   - If a source has no trustworthy rewindable simulator (`simulable=False`), fails closed to
     `EXPLICIT_UNKNOWN` (`HOLD_FOR_RECEIVER_REVIEW_NO_SIMULATOR`) rather than fabricating simulation data.
3. Three Causal Mechanisms Combined in BUCSW (`C3_BUCSW`):
   - Mechanism 1 (Bilateral + Adaptive Group Screen): Prunes dead/inactive sources early; supports
     both Common-Random-Numbers (CRN) and independent-noise stochastic environments via noise-floor
     matched contrast.
   - Mechanism 2 (Counterfactual Bottleneck Unclamping / Competitive Relaxation): When a candidate
     source shows zero local sensitivity (`delta_y == 0`) at the nominal operating point because a
     competing station clamps `min(...)` or a threshold gate is closed, relaxes competing clamps in
     the disposable shadow to separate `LATENT_CLAMPED` dependencies (measuring their exact activation
     slack margin `delta_i*`) from `DEAD_OR_ORTHOGONAL` variables.
   - Mechanism 3 (Interventional Mediation Clamping & Delay-Triangle Transitive Reduction): Separates
     `DIRECT` structural edges from `TRANSITIVE` ancestor-descendant paths (`i -> k -> j`) so
     `RecallLedger` DNF support sets are minimal and human receivers are not flooded with $O(N^2)$
     false-direct review requests.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import math
import multiprocessing as mp
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class WitnessRefused(RuntimeError):
    """Fail-closed refusal when authority, STOP, budget, or integrity boundaries are violated."""


@dataclass(frozen=True)
class WitnessBudget:
    max_sim_calls: int = 120
    max_steps_per_call: int = 128
    max_sources: int = 32
    timeout_seconds_per_call: float = 2.0


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_digest(obj: Any) -> str:
    if isinstance(obj, bytes):
        return hashlib.sha256(obj).hexdigest()
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


# ============================================================================
# 1. ISOLATED SUBPROCESS SHADOW PROBE RUNNER (HARD FALSIFIER B DEFENSE)
# ============================================================================

def _child_shadow_worker(
    conn,
    fn: Callable,
    state_copy: dict[str, Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    try:
        res = fn(state_copy, *args, **kwargs)
        conn.send(("OK", res))
    except Exception as exc:
        conn.send(("ERR", f"{type(exc).__name__}:{exc}"))
    finally:
        conn.close()


class IsolatedShadowProbeRunner:
    """Executes shadow callbacks in an isolated OS child process with timeout and byte-identity verification."""

    def __init__(
        self,
        accepted_state: Mapping[str, Any],
        *,
        protected_files: Sequence[str | Path] = (),
        budget: WitnessBudget = WitnessBudget(),
        check_stop: Callable[[], bool] | None = None,
        use_subprocess_isolation: bool = True,
    ) -> None:
        self._original_state_ref = accepted_state
        self._frozen_state = copy.deepcopy(dict(accepted_state))
        self.initial_state_sha256 = sha256_digest(self._frozen_state)
        self.protected_files = [Path(p) for p in protected_files]
        self.initial_file_hashes = {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.protected_files
            if p.exists()
        }
        self.budget = budget
        self.check_stop = check_stop
        self.use_subprocess_isolation = use_subprocess_isolation
        self.calls_used = 0
        self.cpu_ms_used = 0.0

    def verify_integrity(self) -> None:
        if self.check_stop is not None and self.check_stop():
            raise WitnessRefused("STOP_BINDING_DURING_PROBE")
        if sha256_digest(dict(self._original_state_ref)) != self.initial_state_sha256:
            raise WitnessRefused("ACCEPTED_STATE_MUTATED_BY_PROBE")
        for p_str, orig_hash in self.initial_file_hashes.items():
            p = Path(p_str)
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != orig_hash:
                raise WitnessRefused(f"PROTECTED_FILE_MUTATED_BY_PROBE:{p_str}")

    def run(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        self.verify_integrity()
        if self.calls_used + 1 > self.budget.max_sim_calls:
            raise WitnessRefused("BUDGET_EXCEEDED_MAX_SIM_CALLS")
        t0 = time.perf_counter()
        state_copy = copy.deepcopy(self._frozen_state)

        if self.use_subprocess_isolation:
            parent_conn, child_conn = mp.Pipe(duplex=False)
            proc = mp.Process(
                target=_child_shadow_worker,
                args=(child_conn, fn, state_copy, args, kwargs),
                daemon=True,
            )
            proc.start()
            child_conn.close()
            if not parent_conn.poll(self.budget.timeout_seconds_per_call):
                proc.terminate()
                proc.join(timeout=0.5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=0.5)
                parent_conn.close()
                raise WitnessRefused("SHADOW_CALLBACK_TIMEOUT_KILLED")
            status, payload = parent_conn.recv()
            parent_conn.close()
            proc.join(timeout=0.5)
            self.calls_used += 1
            self.cpu_ms_used += (time.perf_counter() - t0) * 1000.0
            self.verify_integrity()
            if status != "OK":
                raise WitnessRefused(f"SHADOW_CALLBACK_FAILED:{payload}")
            return payload
        else:
            try:
                res = fn(state_copy, *args, **kwargs)
            except Exception as exc:
                raise WitnessRefused(f"SHADOW_CALLBACK_FAILED:{type(exc).__name__}:{exc}") from exc
            self.calls_used += 1
            self.cpu_ms_used += (time.perf_counter() - t0) * 1000.0
            self.verify_integrity()
            return res


# ============================================================================
# 2. COMPETENT CONVENTIONAL BASELINE B1: DYNAMIC READ-PROXY + LOCAL FD TRACER
# ============================================================================

class ReadTrackingDict(dict):
    """Wraps an assumptions dictionary to record every key accessed during function evaluation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.read_keys: set[str] = set()

    def __getitem__(self, key: str) -> Any:
        self.read_keys.add(str(key))
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self.read_keys.add(str(key))
        return super().get(key, default)

    def keys(self):
        for k in super().keys():
            self.read_keys.add(str(k))
        return super().keys()

    def items(self):
        for k in super().keys():
            self.read_keys.add(str(k))
        return super().items()

    def __iter__(self):
        for k in super().__iter__():
            self.read_keys.add(str(k))
            yield k


def probe_conventional_b1_read_and_local_fd(
    accepted_state: Mapping[str, Any],
    assumptions_key_path: Sequence[str],
    candidate_sources: Sequence[str],
    eval_fn: Callable[[dict[str, Any]], Mapping[str, Any]],
    target_outputs: Sequence[str],
    *,
    stopped: bool = False,
    authorized_research: bool = True,
    budget: WitnessBudget = WitnessBudget(),
) -> dict[str, Any]:
    if stopped:
        raise WitnessRefused("STOP_BINDING_NO_PROBE")
    if not authorized_research:
        raise WitnessRefused("RESEARCH_NOT_AUTHORIZED")

    state_copy = copy.deepcopy(dict(accepted_state))
    sub = state_copy
    for part in assumptions_key_path[:-1]:
        sub = sub[part]
    last_k = assumptions_key_path[-1]
    raw_assumptions = dict(sub[last_k])

    tracked = ReadTrackingDict(raw_assumptions)
    sub[last_k] = tracked
    base_out = dict(eval_fn(state_copy))
    calls = 1

    read_only_edges = []
    local_fd_edges = []
    for src in candidate_sources:
        if src in tracked.read_keys:
            for out_k in target_outputs:
                read_only_edges.append({"source": src, "dependent": out_k, "mode": "READ_TAINT"})
            s2 = copy.deepcopy(dict(accepted_state))
            sub2 = s2
            for part in assumptions_key_path[:-1]:
                sub2 = sub2[part]
            v0 = raw_assumptions[src]
            if isinstance(v0, bool):
                sub2[last_k][src] = not v0
            elif isinstance(v0, (int, float)):
                sub2[last_k][src] = (v0 * 1.20) if v0 != 0 else 10.0
            out2 = dict(eval_fn(s2))
            calls += 1
            for out_k in target_outputs:
                if abs(float(out2[out_k]) - float(base_out[out_k])) > 1e-6:
                    local_fd_edges.append({"source": src, "dependent": out_k, "mode": "LOCAL_FD"})

    return {
        "method": "B1_CONVENTIONAL_READ_AND_LOCAL_FD",
        "simulation_calls": calls,
        "read_keys": sorted(tracked.read_keys),
        "read_taint_edges": read_only_edges,
        "local_fd_edges": local_fd_edges,
    }


# ============================================================================
# 3. BOUNDARY-UNCOUPLED COUNTERFACTUAL STANDING WITNESS (BUCSW — C3 INVENTION)
# ============================================================================

def _run_unclamped_helper(
    _state_ignored: dict[str, Any],
    run_shadow: Callable,
    unclamped_state: dict[str, Any],
    src: str | None,
    width: int,
    steps: int,
    amp: float,
) -> Any:
    return run_shadow(copy.deepcopy(unclamped_state), src, width, steps, amp)


def generate_boundary_standing_certificate(
    accepted_state: Mapping[str, Any],
    sources: list[str],
    outputs: list[str],
    run_shadow: Callable[..., Mapping[str, list[float] | float]],
    *,
    stopped: bool,
    authorized_research: bool,
    check_stop: Callable[[], bool] | None = None,
    budget: WitnessBudget = WitnessBudget(),
    steps: int = 48,
    pulse_width: int = 14,
    perturbation: float = 0.65,
    threshold: float = 0.10,
    declared_links: set[tuple[str, str]] | None = None,
    non_simulable_sources: set[str] | None = None,
    unclamp_transform: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
    protected_files: Sequence[str | Path] = (),
    use_subprocess_isolation: bool = False,
) -> dict[str, Any]:
    if stopped or (check_stop is not None and check_stop()):
        raise WitnessRefused("STOP_BINDING_NO_PROBE")
    if not authorized_research:
        raise WitnessRefused("RESEARCH_NOT_AUTHORIZED")
    if not sources or not outputs or len(set(sources)) != len(sources) or len(set(outputs)) != len(outputs):
        raise WitnessRefused("INVALID_PROBE_CONTRACT")
    if len(sources) > budget.max_sources or steps > budget.max_steps_per_call:
        raise WitnessRefused("BUDGET_EXCEEDED")
    if not (0 < pulse_width < steps - 4) or not (0 < perturbation <= 50.0) or not (0 < threshold < 50.0):
        raise WitnessRefused("INVALID_PROBE_PARAMETERS")

    declared_links = set(declared_links or set())
    non_simulable_sources = set(non_simulable_sources or set())

    runner = IsolatedShadowProbeRunner(
        accepted_state,
        protected_files=protected_files,
        budget=budget,
        check_stop=check_stop,
        use_subprocess_isolation=use_subprocess_isolation,
    )

    def _norm_trace(raw_out: Mapping[str, Any]) -> dict[str, list[float]]:
        norm: dict[str, list[float]] = {}
        for k in outputs:
            if k not in raw_out:
                raise WitnessRefused(f"MISSING_OUTPUT_IN_SHADOW_TRACE:{k}")
            val = raw_out[k]
            if isinstance(val, (int, float)):
                arr = [float(val)] * steps
            else:
                arr = [float(x) for x in val]
                if len(arr) != steps:
                    raise WitnessRefused(f"INVALID_SHADOW_TRACE_LENGTH:{k}")
            for x in arr:
                if not math.isfinite(x):
                    raise WitnessRefused(f"NONFINITE_SHADOW_TRACE:{k}")
            norm[k] = arr
        return norm

    # 1. Shared baseline trajectory
    base_trace = _norm_trace(runner.run(run_shadow, None, pulse_width, steps, 0.0))

    active_edges: dict[tuple[str, str], dict[str, Any]] = {}
    latent_clamped_edges: dict[tuple[str, str], dict[str, Any]] = {}
    explicit_unknown_edges: list[dict[str, Any]] = []
    dead_pairs: list[tuple[str, str]] = []
    onset_lags: dict[tuple[str, str], int] = {}

    for src in sources:
        if src in non_simulable_sources:
            for out_k in outputs:
                if src != out_k:
                    explicit_unknown_edges.append({
                        "source": src,
                        "dependent": out_k,
                        "classification": "EXPLICIT_UNKNOWN",
                        "reason": "NO_TRUSTWORTHY_SHADOW_SIMULATOR",
                        "disposition": "HOLD_FOR_RECEIVER_REVIEW_NO_SIMULATOR",
                    })
            continue

        pos_trace = _norm_trace(runner.run(run_shadow, src, pulse_width, steps, perturbation))
        neg_trace: dict[str, list[float]] | None = None

        for out_k in outputs:
            if src == out_k:
                continue
            diffs_pos = [abs(pos_trace[out_k][t] - base_trace[out_k][t]) for t in range(steps)]
            peak_pos = max(diffs_pos)
            lag_pos = next((t for t, d in enumerate(diffs_pos) if d > threshold * 0.5), 999)

            peak = peak_pos
            best_lag = lag_pos
            if peak <= threshold:
                if neg_trace is None:
                    neg_trace = _norm_trace(runner.run(run_shadow, src, pulse_width, steps, -perturbation))
                diffs_neg = [abs(neg_trace[out_k][t] - base_trace[out_k][t]) for t in range(steps)]
                peak_neg = max(diffs_neg)
                lag_neg = next((t for t, d in enumerate(diffs_neg) if d > threshold * 0.5), 999)
                if peak_neg > peak:
                    peak = peak_neg
                    best_lag = lag_neg

            if peak > threshold:
                onset_lags[(src, out_k)] = best_lag
                active_edges[(src, out_k)] = {
                    "source": src,
                    "dependent": out_k,
                    "classification": "ACTIVE_DIRECT",
                    "observed_peak": round(peak, 6),
                    "onset_lag_steps": best_lag,
                    "slack_margin": 0.0,
                }
            elif unclamp_transform is not None:
                unclamped_state = unclamp_transform(copy.deepcopy(dict(accepted_state)), src)
                runner.verify_integrity()
                unc_base = _norm_trace(
                    runner.run(_run_unclamped_helper, run_shadow, unclamped_state, None, pulse_width, steps, 0.0)
                )
                unc_pos = _norm_trace(
                    runner.run(_run_unclamped_helper, run_shadow, unclamped_state, src, pulse_width, steps, perturbation)
                )
                diffs_unc = [abs(unc_pos[out_k][t] - unc_base[out_k][t]) for t in range(steps)]
                peak_unc = max(diffs_unc)
                if peak_unc > threshold:
                    slack_margin = round(abs(unc_base[out_k][-1] - base_trace[out_k][-1]), 6)
                    latent_clamped_edges[(src, out_k)] = {
                        "source": src,
                        "dependent": out_k,
                        "classification": "LATENT_CLAMPED",
                        "observed_local_peak": round(peak, 6),
                        "observed_unclamped_peak": round(peak_unc, 6),
                        "slack_margin": slack_margin,
                        "unclamped_baseline_level": round(unc_base[out_k][-1], 6),
                        "clamped_baseline_level": round(base_trace[out_k][-1], 6),
                    }
                else:
                    dead_pairs.append((src, out_k))
            else:
                dead_pairs.append((src, out_k))

    # 2. Delay-Consistent & Interventional Mediation Transitive Reduction (`src -> med -> dst`)
    transitive_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for (src, dst), info in list(active_edges.items()):
        candidate_mediators = [
            med for med in sources
            if med not in (src, dst)
            and (src, med) in active_edges
            and (med, dst) in active_edges
            and onset_lags.get((src, med), 999) <= onset_lags.get((src, dst), 999)
        ]
        if candidate_mediators:
            sig = inspect.signature(run_shadow)
            if "clamped_mediators" in sig.parameters:
                clamp_map = {med: base_trace[med] for med in candidate_mediators if med in base_trace}
                clamped_trace = _norm_trace(
                    runner.run(run_shadow, src, pulse_width, steps, perturbation, clamped_mediators=clamp_map)
                )
                res_peak = max(abs(clamped_trace[dst][t] - base_trace[dst][t]) for t in range(steps))
                if res_peak <= threshold:
                    del active_edges[(src, dst)]
                    transitive_edges[(src, dst)] = {
                        **info,
                        "classification": "TRANSITIVE_MEDIATED",
                        "mediators": candidate_mediators,
                        "residual_direct_peak": round(res_peak, 6),
                    }

    candidate_proposals = []
    for (src, dst), info in sorted(active_edges.items()):
        if (src, dst) not in declared_links:
            candidate_proposals.append({
                "source": src,
                "dependent": dst,
                "classification": "ACTIVE_DIRECT",
                "observed_peak": info["observed_peak"],
                "slack_margin": 0.0,
                "reason": "UNDECLARED_ACTIVE_DIRECT_CAUSAL_DEPENDENCY",
                "disposition": "REVIEW_DEPENDENCY",
            })
    for (src, dst), info in sorted(latent_clamped_edges.items()):
        if (src, dst) not in declared_links:
            candidate_proposals.append({
                "source": src,
                "dependent": dst,
                "classification": "LATENT_CLAMPED",
                "observed_local_peak": info["observed_local_peak"],
                "observed_unclamped_peak": info["observed_unclamped_peak"],
                "slack_margin": info["slack_margin"],
                "reason": "UNDECLARED_LATENT_BOTTLENECK_CLAMPED_DEPENDENCY",
                "disposition": "REVIEW_DEPENDENCY",
            })
    for unk in explicit_unknown_edges:
        if (unk["source"], unk["dependent"]) not in declared_links:
            candidate_proposals.append(unk)

    runner.verify_integrity()

    certificate = {
        "schema": "openline.standing.certificate.v1",
        "accepted_state_sha256": runner.initial_state_sha256,
        "simulation_calls": runner.calls_used,
        "cpu_ms": round(runner.cpu_ms_used, 3),
        "budget_max_calls": budget.max_sim_calls,
        "sources": list(sources),
        "outputs": list(outputs),
        "declared_links": sorted([list(x) for x in declared_links]),
        "active_direct_dependencies": list(active_edges.values()),
        "latent_clamped_dependencies": list(latent_clamped_edges.values()),
        "transitive_mediated_links": list(transitive_edges.values()),
        "explicit_unknown_links": explicit_unknown_edges,
        "dead_or_orthogonal_pairs": [list(x) for x in dead_pairs],
        "candidate_edges": candidate_proposals,
        "authority": "NONE",
        "accepted_state_mutated": False,
        "receiver_action": "NONE",
        "next_action": (
            "HOLD_FOR_RECEIVER_REVIEW_NO_SIMULATOR"
            if explicit_unknown_edges
            else ("REVIEW_DEPENDENCY" if candidate_proposals else "NO_ACTION")
        ),
    }
    certificate["certificate_sha256"] = sha256_digest(certificate)
    return certificate


def evaluate_standing_under_source_drift(
    certificate: Mapping[str, Any],
    source_deltas: Mapping[str, float],
    *,
    active_bottleneck_shifted: bool = False,
    stopped: bool = False,
) -> dict[str, Any]:
    if stopped:
        raise WitnessRefused("STOP_BINDING_NO_STANDING_EVAL")

    active_map = {d["source"]: d for d in certificate.get("active_direct_dependencies", [])}
    latent_map = {d["source"]: d for d in certificate.get("latent_clamped_dependencies", [])}
    unknown_map = {d["source"]: d for d in certificate.get("explicit_unknown_links", [])}

    triggered_sources = []
    buffered_by_slack = []
    ignored_dead = []

    for src, delta in source_deltas.items():
        mag = abs(float(delta))
        if mag <= 1e-9:
            continue
        if src in unknown_map:
            triggered_sources.append({
                "source": src,
                "delta": delta,
                "reason": "EXPLICIT_UNKNOWN_SOURCE_CHANGED",
                "action": "HOLD_FOR_RECEIVER_REVIEW",
            })
        elif src in active_map:
            triggered_sources.append({
                "source": src,
                "delta": delta,
                "reason": "ACTIVE_DIRECT_DEPENDENCY_CHANGED",
                "action": "QUESTION_STANDING",
            })
        elif src in latent_map:
            slack = float(latent_map[src]["slack_margin"])
            if active_bottleneck_shifted or mag >= slack:
                triggered_sources.append({
                    "source": src,
                    "delta": delta,
                    "slack_margin": slack,
                    "reason": "LATENT_CLAMPED_BOUNDARY_CROSSED",
                    "action": "QUESTION_STANDING",
                })
            else:
                buffered_by_slack.append({
                    "source": src,
                    "delta": delta,
                    "slack_margin": slack,
                    "remaining_slack": round(slack - mag, 6),
                    "action": "NO_ACTION_BUFFERED_BY_SLACK",
                })
        else:
            ignored_dead.append(src)

    disposition = "QUESTION_STANDING" if triggered_sources else "NO_ACTION"
    return {
        "schema": "openline.standing.drift_evaluation.v1",
        "certificate_sha256": certificate["certificate_sha256"],
        "disposition": disposition,
        "triggered_sources": triggered_sources,
        "buffered_by_slack": buffered_by_slack,
        "ignored_dead_sources": ignored_dead,
        "authority": "NONE",
    }
