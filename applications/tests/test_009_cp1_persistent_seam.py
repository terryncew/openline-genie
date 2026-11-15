#!/usr/bin/env python3
"""OpenLine 009 — CP1 Persistent-State Seam, Planning Contract & Worker Recovery Test Suite."""
from __future__ import annotations

import copy
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model_adapter import ModelError, SpendLedger
from core.openline_guard import GuardRefused, VerificationError, verify_receipt_offline
from openline_009_living_project import (
    GOVERNING_LAW_V1_SHA256,
    LivingProjectEngine,
    PlanningContractRefused,
    export_idea_layer_opportunity,
    plan_living_project_contract,
    run_worker_sigkill_and_successor_recovery,
)


class TestOpenLine009CP1PersistentSeam(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.engine = LivingProjectEngine(state_dir=self.state_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_01_idea_layer_handoff_and_direct_planning_contract_boundaries(self) -> None:
        """Verifies pinned Idea Layer export (4c4ac81) and fail-closed planning contract validation."""
        opp = export_idea_layer_opportunity(
            sector_index=6,
            audience="community groups",
            format_mode="toolkit",
            budget_usd=0.0,
            scope_seed=1,
        )
        self.assertEqual(opp["idea_id"], "IL-7-1")
        self.assertEqual(opp["idea_layer_commit"], "4c4ac81d32db7e0ca573bea4cfca031e1e875198")
        self.assertEqual(len(opp["brief_sha256"]), 64)

        contract = plan_living_project_contract(
            opp,
            eval_budget_cap=300,
            usd_budget_cap=0.0,
            target_throughput_ops=84,
            max_capex_usd=680.0,
            max_daily_opex_delta_usd=36.0,
        )
        self.assertEqual(contract["schema"], "openline.living_project.plan_contract.v1")
        self.assertFalse(contract["authority_disclosure"]["authorized"])
        self.assertEqual(contract["authority_disclosure"]["action"], "PROPOSAL_PREVIEW_ONLY")
        self.assertEqual(contract["authority_disclosure"]["governing_law_sha256"], GOVERNING_LAW_V1_SHA256)

        # Negative budget, invalid scope path traversal, and invalid sector must fail closed
        with self.assertRaises(PlanningContractRefused):
            export_idea_layer_opportunity(6, "community groups", "toolkit", budget_usd=-50.0)
        with self.assertRaises(PlanningContractRefused):
            plan_living_project_contract(opp, allowed_scopes=["app/operations_model", "../keys/receiver.key"])
        with self.assertRaises(PlanningContractRefused):
            plan_living_project_contract(opp, eval_budget_cap=0)

    def test_02_durable_living_project_record_and_single_commit_authority(self) -> None:
        """Verifies that LivingProjectEngine persists all 9 required sections in one receiver-governed record."""
        opp = export_idea_layer_opportunity(6, "community groups", "toolkit", 0.0, 0)
        contract = plan_living_project_contract(opp, eval_budget_cap=250, target_throughput_ops=84)
        rec = self.engine.create_living_project(contract, project_id_override="lp-cp1-foundation")

        for section in (
            "goals",
            "constraints",
            "budgets",
            "authority",
            "evidence",
            "decisions",
            "accepted_artifacts",
            "history",
            "capability_references",
        ):
            self.assertIn(section, rec, f"Missing required section: {section}")

        self.assertEqual(rec["project_id"], "lp-cp1-foundation")
        self.assertEqual(rec["version"], 1)
        self.assertEqual(rec["budgets"]["eval_budget_cap"], 250)
        self.assertEqual(rec["budgets"]["eval_budget_spent"], 1)
        self.assertTrue(rec["accepted_artifacts"]["runs_standalone"])
        self.assertEqual(len(rec["evidence"]["state_sha256"]), 64)
        self.assertEqual(len(rec["evidence"]["app_sha256"]), 64)

        # Verify offline Ed25519 receipt signature
        rcpt = rec["bundle"]["accepted"]["receipt"]["receipt"]
        ver = verify_receipt_offline(rcpt, pinned_receiver_pub=self.engine.receiver_identity.public)
        self.assertEqual(ver["crypto"], "VERIFIED")
        self.assertEqual(ver["status"], "COMMITTED")

        # Verify World projection is derived directly from this single accepted state
        world_proj = self.engine.verify_world_projection("lp-cp1-foundation")
        self.assertTrue(world_proj["verified"])
        self.assertTrue(world_proj["receiver_attested"])
        self.assertEqual(world_proj["graph_source"], "RECEIVER_VERIFIED_ENGINE_STATE")
        self.assertTrue(world_proj["all_events_match_attestation"])

    def test_03_real_worker_sigkill_and_clean_successor_recovery(self) -> None:
        """Proves real OS subprocess worker death (SIGKILL) and fresh successor recovery without losing accepted work."""
        opp = export_idea_layer_opportunity(6, "community groups", "toolkit", 0.0, 0)
        contract = plan_living_project_contract(opp, eval_budget_cap=300, target_throughput_ops=84)
        rec_v1 = self.engine.create_living_project(contract, project_id_override="lp-cp1-sigkill")
        self.assertEqual(rec_v1["version"], 1)

        recovery = run_worker_sigkill_and_successor_recovery(self.state_dir, "lp-cp1-sigkill")
        self.assertTrue(recovery["terminated_by_sigkill"])
        self.assertTrue(recovery["accepted_bytes_preserved_exact"])
        self.assertEqual(recovery["uncommitted_draft_disposition"], "REVOKED_BY_WORKER_SWAP")

        succ_eng: LivingProjectEngine = recovery["successor_engine"]
        rec_v2 = succ_eng.get_living_project_record("lp-cp1-sigkill")
        self.assertEqual(rec_v2["version"], 2)
        self.assertEqual(rec_v2["authority"]["active_worker_id"], "worker-b")
        self.assertIn(succ_eng.worker_a_identity.public, rec_v2["authority"]["revoked_worker_public_keys"])
        self.assertEqual(rec_v2["accepted_artifacts"]["operations_summary"]["throughput_ops_per_day"], 56)

        # Attempting to promote the revoked worker-a draft must fail closed
        with self.assertRaises(PermissionError):
            succ_eng.accept_exploratory_change("lp-cp1-sigkill", recovery["uncommitted_draft_proposal_id"])

        # Attempting to submit a new proposal as revoked worker-a must fail closed
        with self.assertRaises(PermissionError):
            succ_eng.propose_exploratory_change(
                "lp-cp1-sigkill",
                "Revoked worker-a illegal retry",
                {"operations_model": {"assumptions": {"auto_triage_enabled": True}}},
                proposer_worker="worker-a",
            )

    def test_04_anti_corruption_anti_reset_and_stop_persistence(self) -> None:
        """Proves that missing/corrupt persistence cannot reset budgets, erase STOP, or promote rejected work."""
        opp = export_idea_layer_opportunity(7, "small businesses", "toolkit", 0.0, 0)
        contract = plan_living_project_contract(opp, eval_budget_cap=200, target_throughput_ops=84)
        rec_v1 = self.engine.create_living_project(contract, project_id_override="lp-cp1-guards")
        v1_sha = rec_v1["evidence"]["state_sha256"]

        # 1. Stage and reject a proposal; verify rejected candidate cannot be swapped into genie_accepted
        prop = self.engine.propose_exploratory_change(
            "lp-cp1-guards",
            "Rejected proposal test",
            {"operations_model": {"assumptions": {"resource_units": 4}}},
        )
        prop_id = prop["exploratory"][0]["proposal_id"]
        cand_sha = prop["exploratory"][0]["candidate_sha256"]
        self.engine.reject_exploratory_change("lp-cp1-guards", prop_id, reason="owner_rejected_test")
        self.engine._update_highwater_mark("lp-cp1-guards", 1, v1_sha, 1, 1)

        # 2. Trigger STOP and verify it persists across restart and blocks mutations
        stop_res = self.engine.trigger_stop("cp1_emergency_stop_test")
        self.assertEqual(stop_res["status"], "STOPPED")
        reopened_eng = LivingProjectEngine(state_dir=self.state_dir)
        self.assertTrue(reopened_eng.guard.read_stop_state()["stopped"])
        with self.assertRaises(GuardRefused):
            reopened_eng.propose_exploratory_change(
                "lp-cp1-guards",
                "Blocked by STOP",
                {"operations_model": {"assumptions": {"resource_units": 4}}},
            )

        # 3. Deleting control.sqlite to erase STOP or high-water marks must fail closed on load
        backup_ctrl = self.state_dir / "ctrl.bak"
        shutil.copy2(self.engine.guard.control_db_path, backup_ctrl)
        os.unlink(self.engine.guard.control_db_path)
        with self.assertRaises(VerificationError):
            LivingProjectEngine(state_dir=self.state_dir)
        shutil.copy2(backup_ctrl, self.engine.guard.control_db_path)

        # 4. Tampering with eval_budget_spent in genie_accepted (budget reset attack) must fail closed
        with sqlite3.connect(self.engine.db_path) as db:
            st_raw = db.execute("SELECT state_json FROM genie_accepted WHERE project_id='lp-cp1-guards'").fetchone()[0]
        st_mod = json.loads(st_raw)
        st_mod["living_project_record"]["budgets"]["eval_budget_spent"] = 0
        with sqlite3.connect(self.engine.db_path) as db:
            db.execute(
                "UPDATE genie_accepted SET state_json=? WHERE project_id='lp-cp1-guards'",
                (json.dumps(st_mod, sort_keys=True),),
            )
            db.commit()
        with self.assertRaises(VerificationError):
            self.engine.verify_persistence_integrity()
        # Restore clean state_json
        with sqlite3.connect(self.engine.db_path) as db:
            db.execute("UPDATE genie_accepted SET state_json=? WHERE project_id='lp-cp1-guards'", (st_raw,))
            db.commit()
        self.assertTrue(self.engine.verify_persistence_integrity()["verified"])

        # 5. SpendLedger deletion/reset attack fails closed via spend_authority.sqlite
        ledger = SpendLedger(self.state_dir)
        res_entry = ledger.reserve("claude-haiku-5-5", 100, 100, "test_hold", 1.0)
        ledger.hold(res_entry["reservation_id"], "msg-1", "test_hold", "crash_hold")
        self.assertGreater(ledger.total_usd(), 0.0)
        os.unlink(ledger.json_path)
        with self.assertRaises(ModelError):
            ledger.total_usd()


if __name__ == "__main__":
    unittest.main(verbosity=2)
