"""Hostile Adversarial & Dogfood Test Suite for Repaired OpenLine 008 (`tests/test_hostile_dogfood_008.py`).

Tests all 10 hostile vectors required by ARGON — OPENLINE 008:
  1. Original GPT-6 stale-dependency reproducer on `upstream/bakery.py` & `upstream/community_garden.py`
     across G1 (`compressed-trajectory-stabilizer`), G2 (`coupled-portfolio-allocator`), and G3 (`distilled-artifact-gate`).
  2. Decision Recall standing transitions (`CURRENT` -> `REOPEN` on dependency mutation, `REVOKED` on authority/permission revocation).
  3. Unfamiliar engineering domain transfer (`upstream/ro_desalination_hub.py`) with 2-level nested imports
     (`upstream/ro_membrane_physics.py` -> `upstream/subpkg/brine_thermodynamics.py`) and leaf-only mutation.
  4. Orthogonal multi-resource mid-trajectory shock & changed model assumptions.
  5. In-memory and persistent disk cache poisoning (`_ENVELOPE_CACHE`, `_DOMAIN_MOD_CACHE`, disk JSON tamper).
  6. Restored files (`A -> B -> A` state transition) with evidence-bound reuse and revoked-digest refusal.
  7. Revoked OS permissions (`chmod 000`), capability revocation, `authority_epoch` advancement, and `owner_stop`.
  8. Concurrent changes / mid-execution TOCTOU file mutation race.
  9. Interrupted execution / mid-envelope-compilation crash recovery & atomic disk persistence.
  10. Clean-room Worker A -> Worker B subprocess inheritance with selective transitive invalidation,
      plus deep tuple/set/frozenset/depth-64 zero-oracle leakage protection.
"""
from __future__ import annotations

import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kernel
from generated import compressed_trajectory_stabilizer as g1
from generated import coupled_portfolio_allocator as g2
from generated import distilled_artifact_gate as g3
from run_exp1_compression import build_trajectory_episodes
from run_exp2_exp3_flywheel import build_g2_portfolio_suite, build_g3_incident_audit_suite


class TestHostileDogfood008(unittest.TestCase):
    def setUp(self) -> None:
        kernel.reset_authority_and_recall_state()
        g3.invalidate_caches()

    def tearDown(self) -> None:
        kernel.reset_authority_and_recall_state()
        kernel._MID_EXECUTION_HOOK = None

    def test_01_gpt6_reproducer_bakery_and_garden_closed_across_g1_g2_g3(self) -> None:
        """Verify that mutating bakery.py or community_garden.py invalidates G1/G2/G3 caches,
        reopens prior Decision Recall standing, and matches fresh-load infeasibility."""
        bakery_path = ROOT / "upstream/bakery.py"
        garden_path = ROOT / "upstream/community_garden.py"
        orig_bakery = bakery_path.read_bytes()
        orig_garden = garden_path.read_bytes()

        eps = build_trajectory_episodes("dev")
        bakery_ep = next(ep for ep in eps if "bakery.py" in ep["facts"]["domain_module"] and ep["expected"]["feasible"])
        garden_ep = next(ep for ep in eps if "community_garden.py" in ep["facts"]["domain_module"] and ep["expected"]["feasible"])
        g2_ep = next(t for t in build_g2_portfolio_suite("dev") if t["expected"]["portfolio_feasible"])
        g3_ep = build_g3_incident_audit_suite("dev")[0]

        g1_task = {
            "facts": bakery_ep["facts"],
            "required_outputs": [
                "feasible_stabilization",
                "interventions",
                "min_stabilized_throughput",
                "total_capex_usd",
                "cumulative_opex_delta_usd",
            ],
            "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
        }
        g2_task = {
            "facts": g2_ep["facts"],
            "required_outputs": [
                "portfolio_feasible",
                "facility_plans",
                "charge_schedule",
                "total_portfolio_capex_usd",
                "total_portfolio_ops_usd",
            ],
            "constraints": {"max_relative_cost_units": 4, "strict_zero_oracle": True},
        }
        g3_task = {
            "facts": g3_ep["facts"],
            "required_outputs": ["triage_action", "portfolio_executed", "portfolio_result"],
            "constraints": {"max_relative_cost_units": 4, "strict_zero_oracle": True},
        }

        try:
            r1_pre = kernel.execute(g1_task, ROOT / "registry_g1.json")["executed"][0]
            r2_pre = kernel.execute(g2_task, ROOT / "registry_g2.json")["executed"][0]
            r3_pre = kernel.execute(g3_task, ROOT / "registry_g3.json")["executed"][0]

            self.assertTrue(r1_pre["result"]["feasible_stabilization"])
            self.assertTrue(r2_pre["result"]["portfolio_feasible"])
            self.assertTrue(r3_pre["result"]["portfolio_result"]["portfolio_feasible"])

            self.assertEqual(kernel.get_decision_standing(r1_pre["receipt"])["standing"], "CURRENT")
            self.assertEqual(kernel.get_decision_standing(r2_pre["receipt"])["standing"], "CURRENT")
            self.assertEqual(kernel.get_decision_standing(r3_pre["receipt"])["standing"], "CURRENT")

            # Mutate bakery.py so trajectory stabilization is strictly infeasible
            mod_bakery = (
                orig_bakery.decode("utf-8")
                .replace('"bake_window_minutes": 300,', '"bake_window_minutes": 150,')
                .replace(
                    '"oven2": {"capex_usd": 18500, "fixed_cost_delta_usd_per_day": 15},',
                    '"oven2": {"capex_usd": 45000, "fixed_cost_delta_usd_per_day": 150},',
                )
            )
            bakery_path.write_text(mod_bakery, encoding="utf-8")

            # Prior receipts must immediately transition to REOPEN
            st1 = kernel.get_decision_standing(r1_pre["receipt"])
            st2 = kernel.get_decision_standing(r2_pre["receipt"])
            st3 = kernel.get_decision_standing(r3_pre["receipt"])
            self.assertEqual(st1["standing"], "REOPEN")
            self.assertIn("upstream/bakery.py", st1["invalidated_dependencies"])
            self.assertEqual(st2["standing"], "REOPEN")
            self.assertEqual(st3["standing"], "REOPEN")

            # Re-executing with warm cache must invalidate and return False (matching fresh load)
            r1_post = kernel.execute(g1_task, ROOT / "registry_g1.json")["executed"][0]
            r2_post = kernel.execute(g2_task, ROOT / "registry_g2.json")["executed"][0]
            r3_post = kernel.execute(g3_task, ROOT / "registry_g3.json")["executed"][0]

            self.assertFalse(r1_post["result"]["feasible_stabilization"])
            self.assertEqual(r1_post["result"]["min_stabilized_throughput"], 87)
            self.assertFalse(r2_post["result"]["portfolio_feasible"])
            self.assertFalse(r3_post["result"]["portfolio_result"]["portfolio_feasible"])

            # Verify receipt dependency_closure_sha256 and output_sha256 changed and match fresh load
            self.assertNotEqual(
                r1_pre["receipt"]["dependency_closure_sha256"],
                r1_post["receipt"]["dependency_closure_sha256"],
            )
            r1_fresh_res = g1.stabilize_trajectory({**bakery_ep["facts"], "use_envelope_cache": False})
            self.assertEqual(r1_post["result"]["feasible_stabilization"], r1_fresh_res["feasible_stabilization"])
            self.assertEqual(r1_post["result"]["min_stabilized_throughput"], r1_fresh_res["min_stabilized_throughput"])

            # Also verify community_garden.py mutation through kernel.execute and direct g1
            g1_garden_task = {
                "facts": garden_ep["facts"],
                "required_outputs": [
                    "feasible_stabilization",
                    "interventions",
                    "min_stabilized_throughput",
                    "total_capex_usd",
                    "cumulative_opex_delta_usd",
                ],
                "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
            }
            rg_pre = kernel.execute(g1_garden_task, ROOT / "registry_g1.json")["executed"][0]
            self.assertTrue(rg_pre["result"]["feasible_stabilization"])

            mod_garden = (
                orig_garden.decode("utf-8")
                .replace('"gallons_per_lb_produce": 2.625,', '"gallons_per_lb_produce": 4.8,')
                .replace('gal_per_lb = 2.625 if a.get("drip_mulch_enabled")', 'gal_per_lb = 4.8 if a.get("drip_mulch_enabled")')
                .replace('"lbs_per_volunteer_hour": 7.5,', '"lbs_per_volunteer_hour": 4.0,')
            )
            garden_path.write_text(mod_garden, encoding="utf-8")

            self.assertEqual(kernel.get_decision_standing(rg_pre["receipt"])["standing"], "REOPEN")
            rg_post = kernel.execute(g1_garden_task, ROOT / "registry_g1.json")["executed"][0]
            self.assertFalse(rg_post["result"]["feasible_stabilization"])
            self.assertEqual(rg_post["result"]["min_stabilized_throughput"], 72)
        finally:
            bakery_path.write_bytes(orig_bakery)
            garden_path.write_bytes(orig_garden)

    def test_02_unfamiliar_ro_desalination_and_depth2_nested_import_invalidation(self) -> None:
        """Verify unfamiliar domain (`upstream/ro_desalination_hub.py`) and Depth-2 transitive leaf mutation
        (`upstream/subpkg/brine_thermodynamics.py`) invalidate G1/G2 and reload intermediate `from ... import` bindings."""
        leaf_path = ROOT / "upstream/subpkg/brine_thermodynamics.py"
        orig_leaf = leaf_path.read_bytes()

        ro_traj = [
            {"feed_tds_g_per_l": 4.2, "ro_vessels_count": 3},
            {"feed_tds_g_per_l": 4.2, "ro_vessels_count": 3},
            {"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3},
            {"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3},
            {"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3},
            {"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3},
        ]
        ro_task = {
            "facts": {
                "domain_module": "upstream/ro_desalination_hub.py",
                "trajectory_assumptions": ro_traj,
                "target_throughput": 2500,
                "max_capex_usd": 2500.0,
                "max_cumulative_opex_delta_usd": 120.0,
            },
            "required_outputs": [
                "feasible_stabilization",
                "interventions",
                "min_stabilized_throughput",
                "total_capex_usd",
                "cumulative_opex_delta_usd",
            ],
            "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
        }

        try:
            r_pre = kernel.execute(ro_task, ROOT / "registry_g1.json")["executed"][0]
            self.assertTrue(r_pre["result"]["feasible_stabilization"])
            self.assertGreaterEqual(r_pre["result"]["min_stabilized_throughput"], 2500)
            dep_hashes = r_pre["receipt"]["dependency_hashes"]
            # Must contain Depth-0, Depth-1, and Depth-2 files in closure!
            self.assertIn("upstream/ro_desalination_hub.py", dep_hashes)
            self.assertIn("upstream/ro_membrane_physics.py", dep_hashes)
            self.assertIn("upstream/subpkg/brine_thermodynamics.py", dep_hashes)

            # Mutate ONLY Depth-2 leaf helper `brine_thermodynamics.py` (severe biofouling resistance 1.00 -> 2.40)
            # leaving ro_membrane_physics.py (Depth-1) and ro_desalination_hub.py (Depth-0) completely untouched!
            mod_leaf = orig_leaf.decode("utf-8").replace(
                "BIOFOULING_RESISTANCE_MULTIPLIER: float = 1.00",
                "BIOFOULING_RESISTANCE_MULTIPLIER: float = 2.40",
            )
            leaf_path.write_text(mod_leaf, encoding="utf-8")

            # Prior receipt standing must immediately become REOPEN citing the Depth-2 file
            st = kernel.get_decision_standing(r_pre["receipt"])
            self.assertEqual(st["standing"], "REOPEN")
            self.assertEqual(st["invalidated_dependencies"], ["upstream/subpkg/brine_thermodynamics.py"])

            # Re-running G1 must reload Depth-2 -> Depth-1 -> Depth-0 and determine infeasibility
            r_post = kernel.execute(ro_task, ROOT / "registry_g1.json")["executed"][0]
            self.assertFalse(r_post["result"]["feasible_stabilization"])
            self.assertLess(r_post["result"]["min_stabilized_throughput"], 1500)
        finally:
            leaf_path.write_bytes(orig_leaf)

    def test_03_orthogonal_multi_resource_mid_trajectory_shock(self) -> None:
        """Verify that when Epoch t=2 has the deepest water drop (t_worst) and intermediate Epoch t=4
        has a secondary volunteer shock (with higher total throughput than t=2), G1 includes both
        resource trough epochs in critical_epochs and selects the combined ['drip_mulch', 'weekend_workday'] plan."""
        traj = [
            {"cistern_gallons_per_week": 560, "volunteer_hours_per_week": 18, "plot_beds_count": 12},
            {"cistern_gallons_per_week": 560, "volunteer_hours_per_week": 18, "plot_beds_count": 12},
            # t=2 (t_breach & global t_worst): water=340 gal -> 85 lbs/wk, volunteers=18 hrs -> 135 lbs/wk
            {"cistern_gallons_per_week": 340, "volunteer_hours_per_week": 18, "plot_beds_count": 12},
            {"cistern_gallons_per_week": 340, "volunteer_hours_per_week": 18, "plot_beds_count": 12},
            # t=4 (intermediate secondary resource shock!): water=420 gal -> 105 lbs/wk, volunteers=14 hrs -> 105 lbs/wk!
            {"cistern_gallons_per_week": 420, "volunteer_hours_per_week": 14, "plot_beds_count": 12},
            # t=5 (t_end): water=360 gal -> 90 lbs/wk, volunteers=18 hrs -> 135 lbs/wk
            {"cistern_gallons_per_week": 360, "volunteer_hours_per_week": 18, "plot_beds_count": 12},
        ]
        facts = {
            "domain_module": "upstream/community_garden.py",
            "trajectory_assumptions": traj,
            "target_throughput": 128,
            "max_capex_usd": 400.0,
            "max_cumulative_opex_delta_usd": 60.0,
        }
        res = g1.stabilize_trajectory(facts)
        self.assertTrue(res["feasible_stabilization"])
        # Single-step ['drip_mulch'] alone would leave t=4 at 105 lbs/wk (volunteer bottleneck)!
        # Repaired G1 must select both 'drip_mulch' and 'weekend_workday'!
        chosen_seq = res["interventions"][0]["upgrade_sequence"]
        self.assertIn("drip_mulch", chosen_seq)
        self.assertIn("weekend_workday", chosen_seq)
        self.assertGreaterEqual(res["min_stabilized_throughput"], 128)

    def test_04_in_memory_and_disk_cache_poisoning_defense(self) -> None:
        """Verify that tampering with _ENVELOPE_CACHE, _DOMAIN_MOD_CACHE, or persistent disk cache
        is detected by cryptographic integrity digests, evicted, and either fails closed or self-heals."""
        eps = build_trajectory_episodes("dev")
        ep = eps[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            facts = {**ep["facts"], "persist_cache_dir": tmpdir}
            res1 = g1.stabilize_trajectory(facts)
            self.assertTrue(res1["feasible_stabilization"])

            # 1. Poison in-memory _ENVELOPE_CACHE by injecting a bogus $0 package
            env_key = next(iter(g1._ENVELOPE_CACHE.keys()))
            pkgs, evals, env_sha = g1._ENVELOPE_CACHE[env_key]
            pkgs[1]["capex_delta"] = -9999.0  # Tamper in place!

            # With fail_on_cache_poison=True, must raise ContractError
            with self.assertRaises(kernel.ContractError):
                g1.stabilize_trajectory({**ep["facts"], "fail_on_cache_poison": True})

            # And on normal call, must have evicted the poisoned entry and rebuilt cleanly
            res2 = g1.stabilize_trajectory(ep["facts"])
            self.assertEqual(res2["total_capex_usd"], res1["total_capex_usd"])
            self.assertGreaterEqual(len(g1._CACHE_POISON_EVENTS), 1)

            # 2. Poison persistent disk cache file
            disk_files = list(Path(tmpdir).glob("env_*.json"))
            self.assertEqual(len(disk_files), 1)
            bad_payload = json.loads(disk_files[0].read_text())
            bad_payload["packages"][0]["capex_delta"] = -500.0
            disk_files[0].write_text(json.dumps(bad_payload))
            g1.invalidate_caches()

            with self.assertRaises(kernel.ContractError):
                g1.stabilize_trajectory({**ep["facts"], "persist_cache_dir": tmpdir, "fail_on_cache_poison": True})

    def test_05_restored_files_a_to_b_to_a_and_revoked_digest_guard(self) -> None:
        """Verify A -> B -> A file restoration reuses A's evidence-bound cache with 0 envelope rebuild evals,
        recovered CURRENT standing, zero B leakage, and refuses A if A's digest is explicitly revoked."""
        bakery_path = ROOT / "upstream/bakery.py"
        bytes_a = bakery_path.read_bytes()
        sha_a = sha256(bytes_a).hexdigest()

        eps = build_trajectory_episodes("dev")
        bakery_ep = next(ep for ep in eps if "bakery.py" in ep["facts"]["domain_module"] and ep["expected"]["feasible"])
        task_a = {
            "facts": bakery_ep["facts"],
            "required_outputs": [
                "feasible_stabilization",
                "interventions",
                "min_stabilized_throughput",
                "total_capex_usd",
                "cumulative_opex_delta_usd",
            ],
            "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
        }

        try:
            # State A: warm cache
            exec_a1 = kernel.execute(task_a, ROOT / "registry_g1.json")["executed"][0]
            self.assertTrue(exec_a1["result"]["feasible_stabilization"])
            receipt_a = exec_a1["receipt"]

            # Transition A -> B (infeasible)
            bytes_b = (
                bytes_a.decode("utf-8")
                .replace('"bake_window_minutes": 300,', '"bake_window_minutes": 150,')
                .encode("utf-8")
            )
            bakery_path.write_bytes(bytes_b)
            self.assertEqual(kernel.get_decision_standing(receipt_a)["standing"], "REOPEN")

            exec_b = kernel.execute(task_a, ROOT / "registry_g1.json")["executed"][0]
            self.assertFalse(exec_b["result"]["feasible_stabilization"])
            receipt_b = exec_b["receipt"]
            self.assertEqual(kernel.get_decision_standing(receipt_b)["standing"], "CURRENT")

            # Transition B -> A (restore original file bytes)
            bakery_path.write_bytes(bytes_a)
            self.assertEqual(kernel.get_decision_standing(receipt_b)["standing"], "REOPEN")
            self.assertEqual(kernel.get_decision_standing(receipt_a)["standing"], "CURRENT")

            # Re-executing under restored A reuses A's cached envelope (0 build evals, 33 trajectory evals vs 86 initial)
            exec_a2 = kernel.execute(task_a, ROOT / "registry_g1.json")["executed"][0]
            self.assertTrue(exec_a2["result"]["feasible_stabilization"])
            self.assertEqual(exec_a2["receipt"]["output_sha256"], receipt_a["output_sha256"])
            self.assertLess(exec_a2["result"]["domain_evaluations"], exec_a1["result"]["domain_evaluations"])

            # Now explicitly revoke digest sha_a in receiver authority controls
            kernel.set_authority_state(revoke_source_digest=sha_a)
            self.assertEqual(kernel.get_decision_standing(receipt_a)["standing"], "REVOKED")
            denied = kernel.execute(task_a, ROOT / "registry_g1.json")
            self.assertEqual(denied["disposition"], "DENY")
            self.assertIn("source_digest_revoked", denied["reason"])
        finally:
            bakery_path.write_bytes(bytes_a)

    def test_06_revoked_permissions_and_authority_epoch_controls(self) -> None:
        """Verify OS chmod 000 permission revocation, authority_epoch advancement, and capability revocation."""
        ro_phys = ROOT / "upstream/ro_membrane_physics.py"
        ro_task = {
            "facts": {
                "domain_module": "upstream/ro_desalination_hub.py",
                "trajectory_assumptions": [
                    {"feed_tds_g_per_l": 4.2, "ro_vessels_count": 3},
                    {"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3},
                ],
                "target_throughput": 2500,
                "max_capex_usd": 2500.0,
                "max_cumulative_opex_delta_usd": 120.0,
            },
            "required_outputs": [
                "feasible_stabilization",
                "interventions",
                "min_stabilized_throughput",
                "total_capex_usd",
                "cumulative_opex_delta_usd",
            ],
            "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
        }
        r1 = kernel.execute(ro_task, ROOT / "registry_g1.json")
        self.assertEqual(r1["disposition"], "EXECUTED")
        rec1 = r1["executed"][0]["receipt"]

        # 1. Authority permission revocation on transitive dependency
        kernel.set_authority_state(revoke_permission="upstream/ro_membrane_physics.py")
        self.assertEqual(kernel.get_decision_standing(rec1)["standing"], "REVOKED")
        r_denied = kernel.execute(ro_task, ROOT / "registry_g1.json")
        self.assertEqual(r_denied["disposition"], "DENY")
        self.assertIn("permission_revoked:upstream/ro_membrane_physics.py", r_denied["reason"])
        kernel.set_authority_state(restore_permission="upstream/ro_membrane_physics.py")

        # 2. OS file permission revocation (chmod 000) if running as non-root
        orig_mode = ro_phys.stat().st_mode
        try:
            os.chmod(ro_phys, 0)
            if not os.access(ro_phys, os.R_OK):
                self.assertEqual(kernel.get_decision_standing(rec1)["standing"], "REVOKED")
                r_chmod = kernel.execute(ro_task, ROOT / "registry_g1.json")
                self.assertEqual(r_chmod["disposition"], "DENY")
        finally:
            os.chmod(ro_phys, orig_mode)

        # 3. Advance authority_epoch (1 -> 2)
        kernel.set_authority_state(authority_epoch=2)
        st_epoch = kernel.get_decision_standing(rec1)
        self.assertEqual(st_epoch["standing"], "REOPEN")
        self.assertEqual(st_epoch["reason"], "authority_epoch_advanced")

    def test_07_concurrent_mid_execution_toctou_mutation_fails_closed(self) -> None:
        """Verify that if a dependency file mutates mid-execution (TOCTOU race), execution fails closed
        without emitting a false receipt or poisoning the cache."""
        bakery_path = ROOT / "upstream/bakery.py"
        orig_bytes = bakery_path.read_bytes()
        eps = build_trajectory_episodes("dev")
        bakery_ep = next(ep for ep in eps if "bakery.py" in ep["facts"]["domain_module"] and ep["expected"]["feasible"])

        def _mutate_mid_flight() -> None:
            bakery_path.write_text(
                orig_bytes.decode("utf-8").replace('"bake_window_minutes": 300,', '"bake_window_minutes": 150,'),
                encoding="utf-8",
            )

        try:
            facts_race = copy.deepcopy(bakery_ep["facts"])
            facts_race["_on_mid_execution"] = _mutate_mid_flight
            r_race = kernel.execute(
                {
                    "facts": facts_race,
                    "required_outputs": [
                        "feasible_stabilization",
                        "interventions",
                        "min_stabilized_throughput",
                        "total_capex_usd",
                        "cumulative_opex_delta_usd",
                    ],
                    "constraints": {"max_relative_cost_units": 3, "strict_zero_oracle": True},
                },
                ROOT / "registry_g1.json",
            )
            self.assertEqual(r_race["disposition"], "INVESTIGATE")
            self.assertEqual(r_race["reason"], "concurrent_dependency_mutation_detected")
            self.assertEqual(r_race["executed"], [])
            # Ensure no poisoned bakery entry survived in _ENVELOPE_CACHE
            bakery_keys = [k for k in g1._ENVELOPE_CACHE if k[0] == "upstream/bakery.py"]
            self.assertEqual(bakery_keys, [])
        finally:
            bakery_path.write_bytes(orig_bytes)

    def test_08_interrupted_execution_atomic_recovery(self) -> None:
        """Verify that an interrupted envelope compilation leaves zero partial state in memory or disk."""
        eps = build_trajectory_episodes("dev")
        ep = eps[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                g1.stabilize_trajectory({
                    **ep["facts"],
                    "persist_cache_dir": tmpdir,
                    "interrupt_after_evals": 4,
                })
            # Verify no partial envelope in memory or leftover temp file on disk
            self.assertEqual(len(g1._ENVELOPE_CACHE), 0)
            self.assertEqual(list(Path(tmpdir).glob("*")), [])

            # Subsequent clean execution succeeds and persists atomically
            res = g1.stabilize_trajectory({**ep["facts"], "persist_cache_dir": tmpdir})
            self.assertTrue(res["feasible_stabilization"])
            self.assertEqual(len(list(Path(tmpdir).glob("env_*.json"))), 1)

    def test_09_worker_a_to_worker_b_inheritance_and_selective_invalidation(self) -> None:
        """Verify clean-room Worker A -> Worker B inheritance across subprocesses with selective invalidation."""
        leaf_path = ROOT / "upstream/subpkg/brine_thermodynamics.py"
        orig_leaf = leaf_path.read_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            receipt_file = Path(tmpdir) / "worker_a_receipts.json"
            try:
                # Worker A runs in subprocess 1, populates persistent envelope cache for garden, bakery, and RO hub
                worker_a_code = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT)!r})
import kernel
from run_exp1_compression import build_trajectory_episodes
eps = build_trajectory_episodes("dev")
garden_ep = next(e for e in eps if "community_garden.py" in e["facts"]["domain_module"])
bakery_ep = next(e for e in eps if "bakery.py" in e["facts"]["domain_module"])
ro_facts = {{
    "domain_module": "upstream/ro_desalination_hub.py",
    "trajectory_assumptions": [
        {{"feed_tds_g_per_l": 4.2, "ro_vessels_count": 3}},
        {{"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3}},
    ],
    "target_throughput": 2500,
    "max_capex_usd": 2500.0,
    "max_cumulative_opex_delta_usd": 120.0,
    "persist_cache_dir": {tmpdir!r},
}}
r_g = kernel.execute({{"facts": {{**garden_ep["facts"], "persist_cache_dir": {tmpdir!r}}}, "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"], "constraints": {{"strict_zero_oracle": True}}}}, Path({str(ROOT / 'registry_g1.json')!r}))["executed"][0]
r_b = kernel.execute({{"facts": {{**bakery_ep["facts"], "persist_cache_dir": {tmpdir!r}}}, "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"], "constraints": {{"strict_zero_oracle": True}}}}, Path({str(ROOT / 'registry_g1.json')!r}))["executed"][0]
r_ro = kernel.execute({{"facts": ro_facts, "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"], "constraints": {{"strict_zero_oracle": True}}}}, Path({str(ROOT / 'registry_g1.json')!r}))["executed"][0]
Path({str(receipt_file)!r}).write_text(json.dumps({{"garden": r_g, "bakery": r_b, "ro": r_ro}}))
"""
                subprocess.run([sys.executable, "-c", worker_a_code], check=True)
                wa_data = json.loads(receipt_file.read_text())

                # Mutate ONLY RO's Depth-2 dependency before Worker B starts
                leaf_path.write_text(
                    orig_leaf.decode("utf-8").replace(
                        "BIOFOULING_RESISTANCE_MULTIPLIER: float = 1.00",
                        "BIOFOULING_RESISTANCE_MULTIPLIER: float = 2.40",
                    ),
                    encoding="utf-8",
                )

                # Worker B runs in subprocess 2: verifies standing of Worker A's 3 receipts,
                # reuses garden and bakery persistent envelopes (0 build evals), and invalidates + recomputes RO!
                worker_b_code = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT)!r})
import kernel
from run_exp1_compression import build_trajectory_episodes
wa = json.loads(Path({str(receipt_file)!r}).read_text())
st_g = kernel.evaluate_receipt_standing(wa["garden"]["receipt"])
st_b = kernel.evaluate_receipt_standing(wa["bakery"]["receipt"])
st_ro = kernel.evaluate_receipt_standing(wa["ro"]["receipt"])

eps = build_trajectory_episodes("dev")
garden_ep = next(e for e in eps if "community_garden.py" in e["facts"]["domain_module"])
bakery_ep = next(e for e in eps if "bakery.py" in e["facts"]["domain_module"])
ro_facts = {{
    "domain_module": "upstream/ro_desalination_hub.py",
    "trajectory_assumptions": [
        {{"feed_tds_g_per_l": 4.2, "ro_vessels_count": 3}},
        {{"feed_tds_g_per_l": 5.8, "ro_vessels_count": 3}},
    ],
    "target_throughput": 2500,
    "max_capex_usd": 2500.0,
    "max_cumulative_opex_delta_usd": 120.0,
    "persist_cache_dir": {tmpdir!r},
}}
rb_g = kernel.execute({{"facts": {{**garden_ep["facts"], "persist_cache_dir": {tmpdir!r}}}, "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"], "constraints": {{"strict_zero_oracle": True}}}}, Path({str(ROOT / 'registry_g1.json')!r}))["executed"][0]
rb_b = kernel.execute({{"facts": {{**bakery_ep["facts"], "persist_cache_dir": {tmpdir!r}}}, "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"], "constraints": {{"strict_zero_oracle": True}}}}, Path({str(ROOT / 'registry_g1.json')!r}))["executed"][0]
rb_ro = kernel.execute({{"facts": ro_facts, "required_outputs": ["feasible_stabilization", "interventions", "min_stabilized_throughput", "total_capex_usd", "cumulative_opex_delta_usd"], "constraints": {{"strict_zero_oracle": True}}}}, Path({str(ROOT / 'registry_g1.json')!r}))["executed"][0]
print(json.dumps({{
    "st_g": st_g["standing"],
    "st_b": st_b["standing"],
    "st_ro": st_ro["standing"],
    "wb_g_evals": rb_g["result"]["domain_evaluations"],
    "wb_b_evals": rb_b["result"]["domain_evaluations"],
    "wb_ro_feasible": rb_ro["result"]["feasible_stabilization"],
}}))
"""
                proc_b = subprocess.run([sys.executable, "-c", worker_b_code], capture_output=True, text=True, check=True)
                wb_out = json.loads(proc_b.stdout.strip())
                self.assertEqual(wb_out["st_g"], "CURRENT")
                self.assertEqual(wb_out["st_b"], "CURRENT")
                self.assertEqual(wb_out["st_ro"], "REOPEN")
                # Garden and bakery reused Worker A's persistent envelopes (24 and 33 evals vs 46 and 86 cold)
                self.assertLess(wb_out["wb_g_evals"], wa_data["garden"]["result"]["domain_evaluations"])
                self.assertLess(wb_out["wb_b_evals"], wa_data["bakery"]["result"]["domain_evaluations"])
                # RO hub invalidated and determined False
                self.assertFalse(wb_out["wb_ro_feasible"])
            finally:
                leaf_path.write_bytes(orig_leaf)

    def test_10_recursive_zero_oracle_set_tuple_and_depth_bomb_defense(self) -> None:
        """Verify that oracle keys hidden inside tuples, sets, frozensets, or >64 deep structures are refused."""
        ep = build_trajectory_episodes("dev")[0]
        for container in (
            ("tuple_wrap", ({"gold_action": "ALLOW"},)),
            ("set_wrap", frozenset(["gold_action"])),
        ):
            contaminated = copy.deepcopy(ep["facts"])
            contaminated[container[0]] = container[1]
            r = kernel.execute(
                {
                    "facts": contaminated,
                    "required_outputs": ["feasible_stabilization"],
                    "constraints": {"strict_zero_oracle": True},
                },
                ROOT / "registry_g1.json",
            )
            self.assertEqual(r["disposition"], "REFUSE")
            self.assertIn("REFUSE_LABEL_LEAKAGE", r["reason"])

        # Depth > 64 bomb
        deep: dict[str, Any] = {"leaf": 1}
        for _ in range(70):
            deep = {"nested": deep}
        contaminated_deep = copy.deepcopy(ep["facts"])
        contaminated_deep["bomb"] = deep
        r_deep = kernel.execute(
            {
                "facts": contaminated_deep,
                "required_outputs": ["feasible_stabilization"],
                "constraints": {"strict_zero_oracle": True},
            },
            ROOT / "registry_g1.json",
        )
        self.assertEqual(r_deep["disposition"], "REFUSE")
        self.assertIn("EXCESSIVE_NESTING_DEPTH", r_deep["reason"])


if __name__ == "__main__":
    unittest.main()
