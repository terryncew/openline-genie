#!/usr/bin/env python3
"""RC6 integration tests — NO model calls.

Covers the RC6 additions on top of the frozen RC3 engine:
- bakery capacity math (min-of-constraints, bottleneck shifts, the
  super-additive oven+shift synergy, 3rd-order ceilings);
- bakery build through the deterministic fallback path (no model):
  structured assumptions recorded as accepted state, family "bakery";
- propose -> accept / reject through the engine, with the candidate's
  computed capacities re-derived (preview numbers == accepted numbers);
- STOP blocking propose/accept while reject stays allowed;
- worker replacement preserving accepted SHA;
- bundle shape the living-world projection needs (receipt envelope,
  receiver key, exploratory/rejected/stopped);
- bakery paths endpoint data.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from genie_engine import OpenLineGenieEngine
from core.bakery import (
    PATH_ASSUMPTION_PATCHES,
    apply_path,
    baseline_assumptions,
    compute_bakery,
    new_bakery_record,
)

BAKERY_PROMPT = (
    "Design a small neighborhood bakery — Hearth & Crumb Bakery: a single-file "
    "HTML app to plan daily baking, track batches, and see capacity."
)


def fresh_engine() -> OpenLineGenieEngine:
    return OpenLineGenieEngine(state_dir=tempfile.mkdtemp(prefix="genie-rc6-test-"))


def bakery_bundle(engine: OpenLineGenieEngine):
    bundle = engine.build_from_prompt(BAKERY_PROMPT, use_model=False)
    return bundle


class TestBakeryMath(unittest.TestCase):
    def test_baseline_matches_rc5u_demo_numbers(self):
        c = compute_bakery(baseline_assumptions())
        self.assertEqual(c["capacities"]["oven"], 174)
        self.assertEqual(c["capacities"]["staff"], 240)
        self.assertEqual(c["capacities"]["ingredients"], 280)
        self.assertEqual(c["throughput_loaves_per_day"], 174)
        self.assertEqual(c["bottleneck_id"], "oven")
        self.assertEqual(c["net_daily_usd"], 643)  # 174*4.5 - 140
        self.assertEqual(c["throughput_band_loaves_per_day"], [162, 186])

    def test_oven_alone_shifts_bottleneck_to_staff(self):
        a = apply_path(baseline_assumptions(), "oven2")
        c = compute_bakery(a)
        self.assertEqual(c["capacities"]["oven"], 348)
        self.assertEqual(c["throughput_loaves_per_day"], 240)
        self.assertEqual(c["bottleneck_id"], "staff")
        self.assertEqual(c["net_daily_usd"], 925)  # 240*4.5 - 155

    def test_shift_alone_is_a_clamped_trap(self):
        a = apply_path(baseline_assumptions(), "hours")
        c = compute_bakery(a)
        self.assertEqual(c["capacities"]["staff"], 300)
        self.assertEqual(c["throughput_loaves_per_day"], 174)  # oven clamps
        self.assertEqual(c["bottleneck_id"], "oven")

    def test_oven_plus_shift_synergy_is_super_additive(self):
        base = compute_bakery(baseline_assumptions())
        oven_only = compute_bakery(apply_path(baseline_assumptions(), "oven2"))
        shift_only = compute_bakery(apply_path(baseline_assumptions(), "hours"))
        a = apply_path(apply_path(baseline_assumptions(), "oven2"), "hours")
        combo = compute_bakery(a)
        self.assertEqual(combo["throughput_loaves_per_day"], 280)
        self.assertEqual(combo["bottleneck_id"], "ingredients")
        gain_oven = oven_only["throughput_loaves_per_day"] - base["throughput_loaves_per_day"]
        gain_shift = shift_only["throughput_loaves_per_day"] - base["throughput_loaves_per_day"]
        gain_combo = combo["throughput_loaves_per_day"] - base["throughput_loaves_per_day"]
        self.assertEqual((gain_oven, gain_shift, gain_combo), (66, 0, 106))
        self.assertGreater(gain_combo, gain_oven + gain_shift)  # +40 synergy

    def test_add_baker_and_retarder_combos(self):
        a = apply_path(baseline_assumptions(), "add_baker")
        self.assertEqual(compute_bakery(a)["throughput_loaves_per_day"], 174)
        a2 = apply_path(apply_path(baseline_assumptions(), "oven2"), "add_baker")
        c2 = compute_bakery(a2)
        self.assertEqual(c2["throughput_loaves_per_day"], 280)
        self.assertEqual(c2["bottleneck_id"], "ingredients")
        a3 = apply_path(
            apply_path(apply_path(baseline_assumptions(), "oven2"), "hours"),
            "retarder_rack",
        )
        c3 = compute_bakery(a3)
        self.assertEqual(c3["throughput_loaves_per_day"], 300)
        self.assertEqual(c3["bottleneck_id"], "staff")

    def test_all_four_hit_the_shop_ceiling(self):
        a = baseline_assumptions()
        for pid in ("oven2", "hours", "add_baker", "retarder_rack"):
            a = apply_path(a, pid)
        c = compute_bakery(a)
        # oven 348, staff 460, ingredients 340, demand 320, shop 300:
        # the shop counter flow becomes the binding constraint.
        self.assertEqual(c["throughput_loaves_per_day"], 300)
        self.assertEqual(c["bottleneck_id"], "shop")

    def test_unknown_path_rejected(self):
        with self.assertRaises(ValueError):
            apply_path(baseline_assumptions(), "third_oven")

    def test_new_record_is_self_consistent(self):
        rec = new_bakery_record()
        self.assertEqual(rec["computed"]["throughput_loaves_per_day"], 174)
        self.assertEqual(set(rec["paths"]), set(PATH_ASSUMPTION_PATCHES))


class TestBakeryEngineFlow(unittest.TestCase):
    def test_deterministic_bakery_build_records_assumptions(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        self.assertEqual(bundle["project_family"], "bakery")
        state = bundle["accepted"]["state"]
        self.assertEqual(state["project_family"], "bakery")
        self.assertIn("bakery", state)
        self.assertEqual(
            state["bakery"]["computed"]["throughput_loaves_per_day"], 174
        )
        self.assertEqual(state["bakery"]["assumptions"]["ovens"], 1)
        self.assertTrue(bundle["accepted"]["receipt"])
        self.assertTrue(bundle["receiver_public_key"])

    def test_propose_recomputes_candidate_and_accept_commits_it(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        accepted_sha_before = bundle["accepted"]["state_sha256"]
        paths = eng.bakery_paths()["paths"]
        patch = {
            "bakery": {
                "assumptions": apply_path(
                    bundle["accepted"]["state"]["bakery"]["assumptions"], "oven2"
                )
            }
        }
        self.assertEqual(paths["oven2"]["assumption_patch"], {"ovens": 2})
        after_propose = eng.propose_exploratory_change(
            pid, "Another oven?", patch
        )
        # Accepted untouched by propose.
        self.assertEqual(
            after_propose["accepted"]["state_sha256"], accepted_sha_before
        )
        self.assertEqual(len(after_propose["exploratory"]), 1)
        cand = after_propose["exploratory"][0]["candidate_state"]
        # Candidate recomputed by the engine: preview == what accept commits.
        self.assertEqual(cand["bakery"]["computed"]["throughput_loaves_per_day"], 240)
        self.assertEqual(cand["bakery"]["computed"]["bottleneck_id"], "staff")
        prop_id = after_propose["exploratory"][0]["proposal_id"]
        after_accept = eng.accept_exploratory_change(pid, prop_id)
        acc = after_accept["accepted"]["state"]
        self.assertEqual(acc["bakery"]["computed"]["throughput_loaves_per_day"], 240)
        self.assertEqual(acc["bakery"]["assumptions"]["ovens"], 2)
        self.assertNotEqual(
            after_accept["accepted"]["state_sha256"], accepted_sha_before
        )
        self.assertEqual(
            after_accept["exploratory"][0]["status"], "ACCEPTED_PROMOTED"
        )

    def test_reject_preserves_accepted_byte_identical(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        sha_before = bundle["accepted"]["state_sha256"]
        state_before = bundle["accepted"]["state"]
        patch = {
            "bakery": {
                "assumptions": apply_path(
                    state_before["bakery"]["assumptions"], "hours"
                )
            }
        }
        after_propose = eng.propose_exploratory_change(
            pid, "Adjust shift schedule", patch
        )
        prop_id = after_propose["exploratory"][0]["proposal_id"]
        after_reject = eng.reject_exploratory_change(pid, prop_id, "not_now")
        self.assertEqual(after_reject["accepted"]["state_sha256"], sha_before)
        self.assertEqual(after_reject["accepted"]["state"], state_before)
        self.assertEqual(len(after_reject["rejected"]), 1)
        self.assertEqual(
            after_reject["rejected"][0]["preserved_accepted_sha256"], sha_before
        )

    def test_stop_blocks_propose_and_accept_but_not_reject(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        patch = {
            "bakery": {
                "assumptions": apply_path(
                    bundle["accepted"]["state"]["bakery"]["assumptions"], "oven2"
                )
            }
        }
        before_stop = eng.propose_exploratory_change(pid, "Another oven?", patch)
        prop_id = before_stop["exploratory"][0]["proposal_id"]
        eng.trigger_stop("test_stop")
        with self.assertRaises(Exception):
            eng.propose_exploratory_change(pid, "Another oven?", patch)
        with self.assertRaises(Exception):
            eng.accept_exploratory_change(pid, prop_id)
        # Reject stays allowed during STOP (owner safety action).
        after_reject = eng.reject_exploratory_change(pid, prop_id, "stopped_reject")
        self.assertEqual(len(after_reject["rejected"]), 1)
        self.assertTrue(eng.get_project_bundle(pid)["stopped"])
        eng.clear_stop("test_resume")
        self.assertFalse(eng.get_project_bundle(pid)["stopped"])

    def test_worker_replacement_preserves_accepted(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        sha_before = bundle["accepted"]["state_sha256"]
        res = eng.replace_worker_and_recover()
        self.assertEqual(res["new_active_worker"], "worker-b")
        after = eng.get_project_bundle(pid)
        self.assertEqual(after["accepted"]["state_sha256"], sha_before)
        self.assertEqual(after["active_worker_id"], "worker-b")

    def test_close_blocks_mutation_and_reopen_restores(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        eng.close_project(pid)
        patch = {
            "bakery": {
                "assumptions": apply_path(
                    bundle["accepted"]["state"]["bakery"]["assumptions"], "oven2"
                )
            }
        }
        with self.assertRaises(Exception):
            eng.propose_exploratory_change(pid, "Another oven?", patch)
        eng.reopen_project(pid)
        after = eng.propose_exploratory_change(pid, "Another oven?", patch)
        self.assertEqual(len(after["exploratory"]), 1)

    def test_bundle_shape_for_living_world_projection(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        # Everything projectGenieBundleToLivingGraph + verifyGenieBundleReceipt need.
        self.assertIn("accepted", bundle)
        self.assertIn("state", bundle["accepted"])
        self.assertIn("state_sha256", bundle["accepted"])
        self.assertIn("receipt", bundle["accepted"])
        receipt = bundle["accepted"]["receipt"]
        inner = receipt.get("receipt", receipt)
        for key in ("payload", "payload_sha256", "signer_pub", "signature"):
            self.assertIn(key, inner, f"receipt missing {key}")
        self.assertEqual(inner["payload"]["schema"], "openline.guard.receipt.v1")
        self.assertEqual(inner["payload"]["status"], "COMMITTED")
        self.assertEqual(inner["signer_pub"], bundle["receiver_public_key"])
        self.assertIn("exploratory", bundle)
        self.assertIn("rejected", bundle)
        self.assertIn("stopped", bundle)
        self.assertIn("project_id", bundle)
        self.assertIn("project_family", bundle)

    def test_attach_is_idempotent(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        again = eng.attach_bakery_domain(pid)
        self.assertEqual(
            again["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"],
            174,
        )

    def test_bakery_paths_endpoint_data(self):
        eng = fresh_engine()
        data = eng.bakery_paths()
        self.assertEqual(
            set(data["paths"]), {"oven2", "hours", "add_baker", "retarder_rack"}
        )
        self.assertEqual(data["paths"]["oven2"]["capex_usd"], 18500)
        self.assertEqual(data["baseline_assumptions"]["ovens"], 1)

    def test_bakery_paths_are_next_steps_from_current_state(self):
        eng = fresh_engine()
        bundle = bakery_bundle(eng)
        pid = bundle["project_id"]
        base = eng.bakery_paths(pid)
        self.assertEqual(base["paths"]["oven2"]["assumption_patch"], {"ovens": 2})
        patch = {
            "bakery": {
                "assumptions": apply_path(
                    bundle["accepted"]["state"]["bakery"]["assumptions"], "oven2"
                )
            }
        }
        after = eng.propose_exploratory_change(pid, "Another oven?", patch)
        eng.accept_exploratory_change(pid, after["exploratory"][0]["proposal_id"])
        nxt = eng.bakery_paths(pid)
        # A second "Another oven?" now means a THIRD oven.
        self.assertEqual(nxt["paths"]["oven2"]["assumption_patch"], {"ovens": 3})
        self.assertEqual(nxt["current_assumptions"]["ovens"], 2)
        self.assertEqual(nxt["paths"]["add_baker"]["assumption_patch"], {"bakers": 2})


if __name__ == "__main__":
    unittest.main()
