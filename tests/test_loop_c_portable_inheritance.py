#!/usr/bin/env python3
"""Unit & Adversarial Falsification Tests for Loop C: Portable Verified Inheritance & Automatic Revalidation
(`tests/test_loop_c_portable_inheritance.py`)."""
from __future__ import annotations

import copy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from core.portable_verified_inheritance import (
    WorkerBPortableInheritanceRuntime,
    qualify_and_export_capsule_worker_a,
    run_loop_c_portable_inheritance_and_revalidation_experiment,
)
from core.rgpo_obligation_gate import sha256_hex


class TestLoopCPortableInheritance(unittest.TestCase):
    def test_01_forged_issuer_and_invalid_ed25519_signature_rejected_before_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as d_a, tempfile.TemporaryDirectory() as d_b:
            cap = asdict(qualify_and_export_capsule_worker_a(Path(d_a)))
            fake = copy.deepcopy(cap)
            fake["worker_a_receipt"]["issuer_receiver_public"] = "UNTRUSTED-ISSUER"
            fake["worker_a_receipt"]["signature_sha256"] = "0" * 64
            wb = WorkerBPortableInheritanceRuntime(Path(d_b))
            with self.assertRaises((PermissionError, ValueError)):
                wb.verify_and_import_capsule(fake)

            # Even with a valid trusted issuer, a forged signature is rejected
            fake_sig = copy.deepcopy(cap)
            fake_sig["worker_a_receipt"]["signed_envelope"]["signature"] = "AAAA" + fake_sig["worker_a_receipt"]["signed_envelope"]["signature"][4:]
            with self.assertRaises((PermissionError, ValueError)):
                wb.verify_and_import_capsule(fake_sig)

    def test_02_tampered_executable_source_never_executes_during_import(self) -> None:
        with tempfile.TemporaryDirectory() as d_a, tempfile.TemporaryDirectory() as d_b:
            cap = asdict(qualify_and_export_capsule_worker_a(Path(d_a)))
            marker = Path(d_b) / "source_was_executed.txt"
            cap["executable_source"] += f'\nfrom pathlib import Path\nPath({repr(str(marker))}).write_text("EXECUTED")\n'
            cap["source_sha256"] = sha256_hex(cap["executable_source"])
            cap["capsule_digest_sha256"] = sha256_hex({
                k: cap[k]
                for k in (
                    "capsule_id",
                    "capability_id",
                    "domain",
                    "version",
                    "source_sha256",
                    "test_suite_sha256",
                    "operating_envelope",
                    "supporting_assumptions",
                    "rollback_triggers",
                    "parameters",
                )
            })
            wb = WorkerBPortableInheritanceRuntime(Path(d_b) / "worker")
            with self.assertRaises((PermissionError, ValueError)):
                wb.verify_and_import_capsule(cap)
            self.assertFalse(marker.exists(), "Untrusted capsule source must NEVER be executed!")

    def test_03_consequential_effect_enforces_revocation_and_assumption_drift_without_manual_recall_call(self) -> None:
        """Verifies that mutating assumptions or triggering STOP blocks execute_on_unseen_task()
        automatically even when the worker never calls check_assumptions_and_auto_recall()."""
        with tempfile.TemporaryDirectory() as d_a, tempfile.TemporaryDirectory() as d_b:
            cap = asdict(qualify_and_export_capsule_worker_a(Path(d_a)))
            wb = WorkerBPortableInheritanceRuntime(Path(d_b))
            wb.verify_and_import_capsule(cap)
            vec = {"solar_kw": 3.6, "vaccine_kw": 1.2, "ro_pump_kw": 1.6, "feed_temp_c": 25.0, "ref_ok": True, "dp_psi": 140.0}

            # 1. Direct in-memory assumption mutation on active_capsule without calling check_assumptions_and_auto_recall
            wb.active_capsule.supporting_assumptions["data_version"] = "dataset-v9.9-unverified"
            with self.assertRaises(PermissionError):
                wb.execute_on_unseen_task(vec)
            self.assertEqual(wb.current_standing, "REOPEN")

    def test_04_portable_inheritance_and_all_six_assumption_revalidations(self) -> None:
        res = run_loop_c_portable_inheritance_and_revalidation_experiment()
        self.assertTrue(res["all_6_assumption_mutations_reopened_and_blocked_fail_closed"])
        self.assertTrue(res["real_agent_6x_claim_retired"])
        cmp_table = res["three_way_worker_comparison"]
        self.assertEqual(
            cmp_table["Worker_B_With_Portable_Verified_Capsule"]["evaluations_spent_to_converge"],
            2,
        )
        self.assertEqual(
            cmp_table["Worker_B_With_Portable_Verified_Capsule"]["unsafe_trial_commits_during_search"],
            0,
        )
        self.assertEqual(len(res["mid_stream_assumption_revalidation_matrix"]), 6)
        for row in res["mid_stream_assumption_revalidation_matrix"]:
            self.assertEqual(row["standing_after_mutation"], "REOPEN")
            self.assertTrue(row["blocked_at_effect_boundary_without_manual_recall_call"])
            self.assertTrue(row["unrelated_project_preserved_exact"])
            self.assertEqual(row["standing_after_revalidation"], "ACCEPTED")


if __name__ == "__main__":
    unittest.main()
