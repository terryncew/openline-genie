#!/usr/bin/env python3
"""Unit and Adversarial Falsifier Test Suite (`test_boundary_standing_witness.py`)
for `openline_boundary_standing_witness.py`.

Verifies 15/15 contract, isolation, authority-boundary, and causal-attribution invariants.
"""
from __future__ import annotations

import copy
import pathlib
import tempfile
import time
import unittest

from openline_boundary_standing_witness import (
    WitnessBudget,
    WitnessRefused,
    evaluate_standing_under_source_drift,
    generate_boundary_standing_certificate,
    probe_conventional_b1_read_and_local_fd,
)


def make_clamped_cascade_runner(
    state: dict,
    source: str | None,
    width: int,
    steps: int,
    amplitude: float,
    *,
    clamped_mediators: dict[str, list[float]] | None = None,
) -> dict[str, list[float]]:
    cfg = state.get("assumptions", {"oven": 0.45, "labor": 0.90, "marketing": 0.60})
    quality = 0.0
    out_tp: list[float] = []
    out_q: list[float] = []
    clamped_mediators = clamped_mediators or {}

    for t in range(steps):
        active_pulse = (6 <= t < 6 + width)
        oven = float(cfg["oven"]) + (amplitude if source == "oven" and active_pulse else 0.0)
        labor = float(cfg["labor"]) + (amplitude if source == "labor" and active_pulse else 0.0)
        _ = float(cfg["marketing"]) + (amplitude if source == "marketing" and active_pulse else 0.0)

        if "throughput" in clamped_mediators:
            tp = float(clamped_mediators["throughput"][t])
        else:
            tp = min(oven, labor) + (amplitude if source == "throughput" and active_pulse else 0.0)

        quality = 0.78 * quality + 0.22 * tp
        out_tp.append(tp)
        out_q.append(quality)

    return {"throughput": out_tp, "quality": out_q}


def unclamp_bakery_shadow(state: dict, target_source: str) -> dict:
    s = copy.deepcopy(state)
    s.setdefault("assumptions", {"oven": 0.45, "labor": 0.90, "marketing": 0.60})
    if target_source != "oven":
        s["assumptions"]["oven"] = 5.0
    if target_source != "labor":
        s["assumptions"]["labor"] = 5.0
    return s


class TestBoundaryStandingWitness(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {
            "project_id": "bakery-frontier-demo",
            "accepted_version": 4,
            "assumptions": {"oven": 0.45, "labor": 0.90, "marketing": 0.60},
        }
        self.frozen_before = copy.deepcopy(self.state)

    def test_01_detects_active_direct_dependency(self) -> None:
        cert = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            unclamp_transform=unclamp_bakery_shadow,
        )
        self.assertEqual(cert["authority"], "NONE")
        self.assertFalse(cert["accepted_state_mutated"])
        self.assertTrue(
            any(d["source"] == "oven" and d["dependent"] == "throughput" for d in cert["active_direct_dependencies"])
        )

    def test_02_discovers_latent_clamped_dependency_and_slack_margin(self) -> None:
        cert = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            perturbation=0.30,
            unclamp_transform=unclamp_bakery_shadow,
        )
        latent_tp = [
            d for d in cert["latent_clamped_dependencies"]
            if d["source"] == "labor" and d["dependent"] == "throughput"
        ]
        self.assertEqual(len(latent_tp), 1)
        self.assertAlmostEqual(latent_tp[0]["slack_margin"], 0.45, places=4)

    def test_03_separates_direct_from_transitive_mediated_edges(self) -> None:
        cert = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing", "throughput"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            unclamp_transform=unclamp_bakery_shadow,
        )
        self.assertTrue(
            any(d["source"] == "oven" and d["dependent"] == "throughput" for d in cert["active_direct_dependencies"])
        )
        self.assertTrue(
            any(d["source"] == "throughput" and d["dependent"] == "quality" for d in cert["active_direct_dependencies"])
        )
        self.assertTrue(
            any(d["source"] == "oven" and d["dependent"] == "quality" for d in cert["transitive_mediated_links"])
        )
        self.assertFalse(
            any(d["source"] == "oven" and d["dependent"] == "quality" for d in cert["active_direct_dependencies"])
        )

    def test_04_ignores_dead_marketing_variable(self) -> None:
        cert = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            unclamp_transform=unclamp_bakery_shadow,
        )
        self.assertFalse(any(p["source"] == "marketing" for p in cert["candidate_edges"]))
        self.assertIn(["marketing", "throughput"], cert["dead_or_orthogonal_pairs"])

    def test_05_preserves_accepted_state_byte_identical(self) -> None:
        generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            unclamp_transform=unclamp_bakery_shadow,
        )
        self.assertEqual(self.state, self.frozen_before)

    def test_06_denies_when_stopped_or_unauthorized(self) -> None:
        for stopped, auth in [(True, True), (False, False)]:
            with self.assertRaises(WitnessRefused):
                generate_boundary_standing_certificate(
                    self.state,
                    ["oven"],
                    ["throughput"],
                    make_clamped_cascade_runner,
                    stopped=stopped,
                    authorized_research=auth,
                )

    def test_07_enforces_simulation_call_budget(self) -> None:
        with self.assertRaisesRegex(WitnessRefused, "BUDGET_EXCEEDED"):
            generate_boundary_standing_certificate(
                self.state,
                ["oven", "labor", "marketing"],
                ["throughput"],
                make_clamped_cascade_runner,
                stopped=False,
                authorized_research=True,
                budget=WitnessBudget(max_sim_calls=2),
            )

    def test_08_refuses_nonfinite_shadow_traces(self) -> None:
        def nan_runner(*args, **kwargs):
            return {"throughput": [float("nan")] * 48}

        with self.assertRaisesRegex(WitnessRefused, "NONFINITE_SHADOW_TRACE"):
            generate_boundary_standing_certificate(
                self.state,
                ["oven"],
                ["throughput"],
                nan_runner,
                stopped=False,
                authorized_research=True,
            )

    def test_09_aborts_immediately_when_stop_arrives_mid_probe(self) -> None:
        counter = [0]

        def mid_stop() -> bool:
            counter[0] += 1
            return counter[0] >= 3

        with self.assertRaisesRegex(WitnessRefused, "STOP_BINDING_DURING_PROBE"):
            generate_boundary_standing_certificate(
                self.state,
                ["oven", "labor"],
                ["throughput"],
                make_clamped_cascade_runner,
                stopped=False,
                authorized_research=True,
                check_stop=mid_stop,
            )
        self.assertEqual(self.state, self.frozen_before)

    def test_10_classifies_non_simulable_sources_as_explicit_unknown(self) -> None:
        cert = generate_boundary_standing_certificate(
            self.state,
            ["oven", "external_live_webhook"],
            ["throughput"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            non_simulable_sources={"external_live_webhook"},
        )
        self.assertEqual(cert["next_action"], "HOLD_FOR_RECEIVER_REVIEW_NO_SIMULATOR")
        self.assertEqual(len(cert["explicit_unknown_links"]), 1)
        self.assertEqual(cert["explicit_unknown_links"][0]["source"], "external_live_webhook")

    def test_11_subprocess_isolation_kills_hanging_callback_without_state_loss(self) -> None:
        def hanging_runner(*args, **kwargs):
            time.sleep(5.0)
            return {"throughput": [0.0] * 48}

        with self.assertRaisesRegex(WitnessRefused, "SHADOW_CALLBACK_TIMEOUT_KILLED"):
            generate_boundary_standing_certificate(
                self.state,
                ["oven"],
                ["throughput"],
                hanging_runner,
                stopped=False,
                authorized_research=True,
                budget=WitnessBudget(max_sim_calls=10, timeout_seconds_per_call=0.25),
                use_subprocess_isolation=True,
            )
        self.assertEqual(self.state, self.frozen_before)

    def test_12_detects_protected_sqlite_file_tampering_by_malicious_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_file = pathlib.Path(tmp) / "genie_state.sqlite"
            db_file.write_bytes(b"ACCEPTED_IMMUTABLE_BYTES_V1")

            def malicious_writer(*args, **kwargs):
                db_file.write_bytes(b"CORRUPTED_BY_ROGUE_PROBE")
                return {"throughput": [0.45] * 48}

            with self.assertRaisesRegex(WitnessRefused, "PROTECTED_FILE_MUTATED_BY_PROBE"):
                generate_boundary_standing_certificate(
                    self.state,
                    ["oven"],
                    ["throughput"],
                    malicious_writer,
                    stopped=False,
                    authorized_research=True,
                    protected_files=[db_file],
                )

    def test_13_standing_drift_evaluation_respects_slack_margins(self) -> None:
        cert = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            perturbation=0.30,
            unclamp_transform=unclamp_bakery_shadow,
        )
        eval_sub = evaluate_standing_under_source_drift(cert, {"labor": -0.20, "marketing": 5.0})
        self.assertEqual(eval_sub["disposition"], "NO_ACTION")
        self.assertEqual(len(eval_sub["buffered_by_slack"]), 1)

        eval_cross = evaluate_standing_under_source_drift(cert, {"labor": -0.50})
        self.assertEqual(eval_cross["disposition"], "QUESTION_STANDING")
        self.assertEqual(eval_cross["triggered_sources"][0]["reason"], "LATENT_CLAMPED_BOUNDARY_CROSSED")

        eval_active = evaluate_standing_under_source_drift(cert, {"oven": -0.05})
        self.assertEqual(eval_active["disposition"], "QUESTION_STANDING")

    def test_14_repeatable_deterministic_certificate_hash(self) -> None:
        c1 = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            unclamp_transform=unclamp_bakery_shadow,
        )
        c2 = generate_boundary_standing_certificate(
            self.state,
            ["oven", "labor", "marketing"],
            ["throughput", "quality"],
            make_clamped_cascade_runner,
            stopped=False,
            authorized_research=True,
            unclamp_transform=unclamp_bakery_shadow,
        )
        c1_clean = {k: v for k, v in c1.items() if k not in ("cpu_ms", "certificate_sha256")}
        c2_clean = {k: v for k, v in c2.items() if k not in ("cpu_ms", "certificate_sha256")}
        self.assertEqual(c1_clean, c2_clean)

    def test_15_conventional_b1_read_tracer_vs_local_fd_tradeoff(self) -> None:
        def eval_fn(st: dict) -> dict:
            a = st["assumptions"]
            tp = min(float(a["oven"]), float(a["labor"]))
            net = tp * 4.5 - float(a["marketing"]) * 0.0 - float(a.get("fixed_cost", 10.0))
            return {"throughput": tp, "net_usd": net}

        st = {"assumptions": {"oven": 0.45, "labor": 0.90, "marketing": 0.60, "fixed_cost": 10.0}}
        res = probe_conventional_b1_read_and_local_fd(
            st,
            ["assumptions"],
            ["oven", "labor", "marketing", "fixed_cost"],
            eval_fn,
            ["throughput"],
        )
        read_srcs = {e["source"] for e in res["read_taint_edges"]}
        self.assertIn("marketing", read_srcs)
        self.assertIn("fixed_cost", read_srcs)
        fd_srcs = {e["source"] for e in res["local_fd_edges"]}
        self.assertEqual(fd_srcs, {"oven"})


if __name__ == "__main__":
    unittest.main()
