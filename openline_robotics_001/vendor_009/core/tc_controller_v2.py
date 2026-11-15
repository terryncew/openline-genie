#!/usr/bin/env python3
"""
OpenLine Writing Studio — Terrynce Curve Controller (TC Controller 2.0)
Repairs the 4 identified defects in legacy TC_controller.py and repurposes
Explorer/Id, Mediator/Ego, Context/Superego into:
  - Explorer (divergent ideas, unexpected connections, metaphors)
  - Editor   (coherence, precision, compression, pacing, audience fit)
  - Verifier (evidence integrity, factual grounding, accepted-work preservation)
Also implements SimpleDirectController as a competent baseline comparator.
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
import math
import time
from typing import Dict, List, Optional, Tuple


class ControllerValidationError(ValueError):
    """Raised when TCControllerV2 receives invalid, NaN, Inf, or out-of-range inputs."""


DIAL_SPECS: Dict[str, Tuple[float, float, float]] = {
    "intensity": (0.0, 100.0, 58.0),
    "compression": (0.0, 100.0, 62.0),
    "humor": (0.0, 100.0, 28.0),
    "metaphorDensity": (0.0, 100.0, 32.0),
    "formality": (0.0, 100.0, 60.0),
    "narrativeDistance": (0.0, 100.0, 48.0),
    "rhythmVariation": (0.0, 100.0, 68.0),
    "analyticalDepth": (0.0, 100.0, 74.0),
    "creativeDivergence": (0.0, 100.0, 42.0),
    # Non-negotiable factual integrity floor: evidenceStrictness >= 20.0
    "evidenceStrictness": (20.0, 100.0, 88.0),
}


class LegacyDefectiveTCController:
    """
    Reproduces the 4 historical defects in the original TC_controller.py:
      1. Weight floors violated after sum-normalization (clamping before dividing).
      2. Failure list never prunes expired timestamps outside the window.
      3. Non-monotonic timestamp subtraction causes ZeroDivisionError or negative slew.
      4. Missing input validation accepts NaN/negative values and auto-smoothing overrides manual changes.
    """

    def __init__(self, floors: Tuple[float, float, float] = (0.10, 0.15, 0.20)):
        self.floors = floors
        self.weights = [0.33, 0.34, 0.33]
        self.failures: List[float] = []
        self.last_ts: Optional[float] = None
        self.fail_safe: bool = False

    def step_defective(
        self,
        raw_targets: Tuple[float, float, float],
        timestamp: float,
        failed: bool = False,
    ) -> Dict[str, object]:
        clamped = [max(self.floors[i], raw_targets[i]) for i in range(3)]
        total = sum(clamped) or 1.0
        normed = [c / total for c in clamped]
        dt = 1.0 if self.last_ts is None else (timestamp - self.last_ts)
        self.last_ts = timestamp
        alpha = 0.25 * dt
        if failed:
            self.failures.append(timestamp)
        if len(self.failures) >= 3:
            self.fail_safe = True
        self.weights = [
            self.weights[i] + alpha * (normed[i] - self.weights[i]) for i in range(3)
        ]
        return {
            "weights": list(self.weights),
            "fail_safe": self.fail_safe,
            "failure_count": len(self.failures),
            "dt": dt,
        }


def project_simplex_with_floors(
    raw_weights: Tuple[float, float, float],
    floors: Tuple[float, float, float] = (0.08, 0.12, 0.20),
) -> Tuple[float, float, float]:
    """
    Projects 3 weights onto the probability simplex {w : sum(w) == 1.0, w_i >= floor_i}.
    Guarantees that no weight ever drops below its floor AFTER normalization.
    """
    if len(raw_weights) != 3 or len(floors) != 3:
        raise ControllerValidationError("Exactly 3 weights and 3 floors are required.")
    for val in (*raw_weights, *floors):
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            raise ControllerValidationError(f"Non-finite or invalid weight/floor value: {val!r}")
    floor_sum = sum(floors)
    if floor_sum >= 1.0 - 1e-6:
        raise ControllerValidationError(f"Sum of weight floors ({floor_sum:.4f}) must be < 1.0")

    remaining_mass = 1.0 - floor_sum
    surpluses = [max(0.0, float(raw_weights[i]) - float(floors[i])) for i in range(3)]
    surplus_sum = sum(surpluses)
    if surplus_sum <= 1e-12:
        allocated = [floors[i] + remaining_mass / 3.0 for i in range(3)]
    else:
        allocated = [
            floors[i] + remaining_mass * (surpluses[i] / surplus_sum)
            for i in range(3)
        ]
    w0 = max(floors[0], round(allocated[0], 6))
    w1 = max(floors[1], round(allocated[1], 6))
    w2 = max(floors[2], round(1.0 - w0 - w1, 6))
    if w2 < floors[2]:
        deficit = floors[2] - w2
        w2 = floors[2]
        if w0 - floors[0] >= w1 - floors[1]:
            w0 = max(floors[0], round(w0 - deficit, 6))
        else:
            w1 = max(floors[1], round(w1 - deficit, 6))
    return (w0, w1, w2)


class SimpleDirectController:
    """
    Competent simpler baseline controller (Section 5 requirement):
    Linear dial mapping without bounded simplex floors, failure-window recovery,
    or slew/entropy stability guards.
    """

    def __init__(self) -> None:
        self.dials: Dict[str, float] = {k: v[2] for k, v in DIAL_SPECS.items()}

    def compute_weights(self, dials: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        active = dict(self.dials)
        if dials:
            active.update(dials)
        e_raw = 0.01 * (0.45 * active["creativeDivergence"] + 0.30 * active["metaphorDensity"] + 0.25 * active["humor"])
        m_raw = 0.01 * (0.40 * active["compression"] + 0.35 * active["rhythmVariation"] + 0.25 * active["formality"])
        v_raw = 0.01 * (0.65 * active["evidenceStrictness"] + 0.35 * active["analyticalDepth"])
        total = (e_raw + m_raw + v_raw) or 1.0
        return {
            "explorer": round(e_raw / total, 4),
            "editor": round(m_raw / total, 4),
            "verifier": round(v_raw / total, 4),
        }


@dataclass
class TCControllerV2:
    floors: Tuple[float, float, float] = (0.08, 0.12, 0.20)
    slew_limit_per_step: float = 0.18
    ema_alpha: float = 0.45
    failure_window_seconds: float = 60.0
    failure_threshold: int = 3
    step_budget: int = 200

    weights: Tuple[float, float, float] = field(default=(0.24, 0.38, 0.38))
    dials: Dict[str, float] = field(default_factory=lambda: {k: v[2] for k, v in DIAL_SPECS.items()})
    active_mode: str = "Reported"
    manual_lock: bool = False
    fail_safe_active: bool = False
    last_timestamp: Optional[float] = None
    steps_taken: int = 0
    _failure_timestamps: deque = field(default_factory=deque)
    saved_profiles: Dict[str, Dict[str, object]] = field(default_factory=dict)

    MODE_PRESETS: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            "Reported": {
                "intensity": 56.0, "compression": 68.0, "humor": 14.0, "metaphorDensity": 18.0,
                "formality": 68.0, "narrativeDistance": 62.0, "rhythmVariation": 64.0,
                "analyticalDepth": 82.0, "creativeDivergence": 24.0, "evidenceStrictness": 95.0,
            },
            "Essay": {
                "intensity": 62.0, "compression": 64.0, "humor": 38.0, "metaphorDensity": 36.0,
                "formality": 52.0, "narrativeDistance": 42.0, "rhythmVariation": 76.0,
                "analyticalDepth": 78.0, "creativeDivergence": 48.0, "evidenceStrictness": 86.0,
            },
            "Literary": {
                "intensity": 72.0, "compression": 58.0, "humor": 24.0, "metaphorDensity": 64.0,
                "formality": 46.0, "narrativeDistance": 28.0, "rhythmVariation": 88.0,
                "analyticalDepth": 62.0, "creativeDivergence": 74.0, "evidenceStrictness": 76.0,
            },
            "Satire": {
                "intensity": 74.0, "compression": 76.0, "humor": 88.0, "metaphorDensity": 52.0,
                "formality": 44.0, "narrativeDistance": 54.0, "rhythmVariation": 82.0,
                "analyticalDepth": 70.0, "creativeDivergence": 78.0, "evidenceStrictness": 82.0,
            },
            "Courage": {
                "intensity": 84.0, "compression": 72.0, "humor": 18.0, "metaphorDensity": 28.0,
                "formality": 62.0, "narrativeDistance": 36.0, "rhythmVariation": 74.0,
                "analyticalDepth": 84.0, "creativeDivergence": 36.0, "evidenceStrictness": 94.0,
            },
            "Political": {
                "intensity": 78.0, "compression": 70.0, "humor": 26.0, "metaphorDensity": 30.0,
                "formality": 64.0, "narrativeDistance": 50.0, "rhythmVariation": 72.0,
                "analyticalDepth": 86.0, "creativeDivergence": 34.0, "evidenceStrictness": 94.0,
            },
            "Threads": {
                "intensity": 76.0, "compression": 88.0, "humor": 46.0, "metaphorDensity": 26.0,
                "formality": 38.0, "narrativeDistance": 34.0, "rhythmVariation": 78.0,
                "analyticalDepth": 68.0, "creativeDivergence": 44.0, "evidenceStrictness": 88.0,
            },
            "Film / Script": {
                "intensity": 74.0, "compression": 74.0, "humor": 34.0, "metaphorDensity": 32.0,
                "formality": 30.0, "narrativeDistance": 22.0, "rhythmVariation": 84.0,
                "analyticalDepth": 54.0, "creativeDivergence": 68.0, "evidenceStrictness": 72.0,
            },
            "Research": {
                "intensity": 48.0, "compression": 62.0, "humor": 10.0, "metaphorDensity": 16.0,
                "formality": 76.0, "narrativeDistance": 70.0, "rhythmVariation": 58.0,
                "analyticalDepth": 94.0, "creativeDivergence": 28.0, "evidenceStrictness": 98.0,
            },
            "Discovery": {
                "intensity": 68.0, "compression": 54.0, "humor": 32.0, "metaphorDensity": 68.0,
                "formality": 48.0, "narrativeDistance": 44.0, "rhythmVariation": 76.0,
                "analyticalDepth": 84.0, "creativeDivergence": 86.0, "evidenceStrictness": 80.0,
            },
        }
    )

    def validate_timestamp(self, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if timestamp is None:
            ts = time.monotonic()
        else:
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                raise ControllerValidationError(f"Invalid timestamp: {timestamp!r}")
            if timestamp < 0:
                raise ControllerValidationError(f"Negative timestamp not allowed: {timestamp}")
            ts = float(timestamp)

        if self.last_timestamp is None:
            dt = 1.0
            monotonic_ts = ts
        else:
            if ts < self.last_timestamp:
                dt = 1e-6
                monotonic_ts = self.last_timestamp + 1e-6
            else:
                dt = max(1e-6, ts - self.last_timestamp)
                monotonic_ts = ts
        self.last_timestamp = monotonic_ts
        return monotonic_ts, dt

    def validate_and_apply_dials(self, dial_updates: Dict[str, float], strict: bool = True) -> Dict[str, float]:
        if not isinstance(dial_updates, dict):
            raise ControllerValidationError("dial_updates must be a dict.")
        cleaned: Dict[str, float] = {}
        for k, raw_val in dial_updates.items():
            if k not in DIAL_SPECS:
                if strict:
                    raise ControllerValidationError(f"Unknown dial: {k!r}")
                continue
            if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)) or not math.isfinite(raw_val):
                raise ControllerValidationError(f"Dial {k!r} must be a finite number, got {raw_val!r}")
            low, high, _ = DIAL_SPECS[k]
            val = float(raw_val)
            if k == "evidenceStrictness" and val < low:
                val = low
            elif strict and (val < 0.0 or val > 100.0):
                raise ControllerValidationError(f"Dial {k!r}={val} out of bounds [0, 100]")
            else:
                val = max(low, min(high, val))
            cleaned[k] = round(val, 2)
        self.dials.update(cleaned)
        return dict(self.dials)

    def _prune_failures(self, current_ts: float) -> int:
        cutoff = current_ts - self.failure_window_seconds
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()
        self.fail_safe_active = len(self._failure_timestamps) >= self.failure_threshold
        return len(self._failure_timestamps)

    def _targets_from_dials(self) -> Tuple[float, float, float]:
        d = self.dials
        explorer_score = (
            0.38 * (d["creativeDivergence"] / 100.0)
            + 0.28 * (d["metaphorDensity"] / 100.0)
            + 0.18 * (d["humor"] / 100.0)
            + 0.16 * (d["intensity"] / 100.0)
        )
        editor_score = (
            0.36 * (d["compression"] / 100.0)
            + 0.30 * (d["rhythmVariation"] / 100.0)
            + 0.18 * (d["formality"] / 100.0)
            + 0.16 * (1.0 - abs(d["narrativeDistance"] - 50.0) / 100.0)
        )
        verifier_score = (
            0.64 * (d["evidenceStrictness"] / 100.0)
            + 0.36 * (d["analyticalDepth"] / 100.0)
        )
        return project_simplex_with_floors((explorer_score, editor_score, verifier_score), self.floors)

    def step(
        self,
        dial_updates: Optional[Dict[str, float]] = None,
        mode: Optional[str] = None,
        manual: bool = False,
        timestamp: Optional[float] = None,
        failed: bool = False,
    ) -> Dict[str, object]:
        ts, dt = self.validate_timestamp(timestamp)
        if failed:
            self._failure_timestamps.append(ts)
        window_failures = self._prune_failures(ts)

        if mode is not None:
            if mode not in self.MODE_PRESETS and mode not in self.saved_profiles:
                raise ControllerValidationError(f"Unknown mode or profile: {mode!r}")
            self.active_mode = mode
            preset = (
                self.MODE_PRESETS[mode]
                if mode in self.MODE_PRESETS
                else self.saved_profiles[mode]["dials"]
            )
            self.validate_and_apply_dials(preset, strict=False)

        if dial_updates is not None:
            self.validate_and_apply_dials(dial_updates, strict=True)

        target_w = self._targets_from_dials()

        if self.fail_safe_active:
            # Immediate fail-safe shift to Verifier >= 0.52 without waiting for EMA slew lag
            self.weights = project_simplex_with_floors((0.08, 0.32, 0.60), self.floors)
        elif manual:
            self.manual_lock = True
            self.weights = target_w
        elif not self.manual_lock:
            stepped = []
            for i in range(3):
                ema_val = self.weights[i] + self.ema_alpha * (target_w[i] - self.weights[i])
                delta = ema_val - self.weights[i]
                if abs(delta) > self.slew_limit_per_step:
                    delta = math.copysign(self.slew_limit_per_step, delta)
                stepped.append(self.weights[i] + delta)
            self.weights = project_simplex_with_floors((stepped[0], stepped[1], stepped[2]), self.floors)

        self.steps_taken += 1
        return {
            "mode": self.active_mode,
            "manualLock": self.manual_lock,
            "failSafeActive": self.fail_safe_active,
            "windowFailures": window_failures,
            "dt": round(dt, 6),
            "stepsTaken": self.steps_taken,
            "stepBudgetRemaining": max(0, self.step_budget - self.steps_taken),
            "weights": self.get_weight_dict(),
            "dials": dict(self.dials),
        }

    def get_weight_dict(self) -> Dict[str, float]:
        return {
            "explorer": round(self.weights[0], 4),
            "editor": round(self.weights[1], 4),
            "verifier": round(self.weights[2], 4),
        }

    def save_profile(self, name: str, description: str = "") -> Dict[str, object]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ControllerValidationError("Profile name cannot be empty.")
        profile = {
            "name": clean_name,
            "description": description,
            "baseMode": self.active_mode,
            "dials": dict(self.dials),
            "weights": self.get_weight_dict(),
        }
        self.saved_profiles[clean_name] = profile
        return profile

    def load_profile(self, name: str) -> Dict[str, object]:
        if name not in self.saved_profiles:
            raise ControllerValidationError(f"Saved profile not found: {name!r}")
        prof = self.saved_profiles[name]
        return self.step(dial_updates=prof["dials"], mode=name, manual=True)
