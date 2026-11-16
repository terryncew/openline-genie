#!/usr/bin/env python3
"""ARGON — OPENLINE CIVILIZATION APPLICATIONS 001
Automated Unit, Integration, Adversarial Falsifier & Regression Test Suite (`tests/test_civilization_applications_001.py`).
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE / "core") not in sys.path:
    sys.path.insert(0, str(HERE / "core"))

from core.civilization_applications import (
    EvidenceTriagedCounterfactualAuditor,
    compute_appeal_deadlines_fail_closed,
    conventional_energy_coop_calculator,
    evaluate_community_energy_cooperative,
    evaluate_public_benefits_appeal,
    evaluate_public_infrastructure_accountability,
    evaluate_unfamiliar_sixth_task_pharmacy_coldchain,
    independent_research_replayer,
    run_self_correcting_scientific_workspace,
)
from openline_009_living_project import LivingProjectEngine, plan_living_project_contract
from run_civilization_applications_001 import (
    run_application_a_franklin,
    run_application_b_baldwin,
    run_application_c_morrison,
    run_application_d_einstein,
    run_application_e_arendt,
    run_central_experiment_and_sixth_finding,
    run_operating_law_eight_falsifier_suite,
)


class TestCivilizationApplications001(unittest.TestCase):
    def test_01_application_a_franklin_energy_cooperative_and_conventional_parity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_application_a_franklin(Path(tmp))
            self.assertEqual(res["level_1_verdict"], "WORKING")
            self.assertEqual(res["conventional_parity_max_diff_usd"], 0.0)
            self.assertEqual(res["failure_condition_probes_blocked"], "4/4")
            self.assertEqual(res["human_approval_gate"]["unapproved_spend"], "BLOCKED_OWNER_AUTHORIZATION_REQUIRED")
            self.assertEqual(res["human_approval_gate"]["approved_spend"], "COMMITTED")
            self.assertEqual(res["decision_recall_on_assumption_change"]["standing"], "REOPEN")
            self.assertTrue(res["decision_recall_on_assumption_change"]["accepted_bytes_preserved"])

    def test_02_application_b_baldwin_appeal_assistant_epistemic_and_deadline_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_application_b_baldwin(Path(tmp))
            self.assertEqual(res["level_1_verdict"], "WORKING")
            self.assertTrue(res["incomplete_packet_blocked"])
            self.assertTrue(res["expired_rule_blocked"])
            self.assertTrue(res["unsupported_conclusion_blocked"])
            self.assertTrue(res["pii_redaction_verified"])
            self.assertEqual(res["unauthorized_filing_status"], "BLOCKED_OWNER_AUTHORIZATION_REQUIRED")
            self.assertEqual(res["decision_recall_standing"], "REOPEN")

    def test_03_application_c_morrison_three_community_projects_and_defect_10_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_application_c_morrison(Path(tmp))
            self.assertEqual(res["level_1_verdict"], "WORKING")
            self.assertEqual(res["defect_10_repair_verified"]["status"], "FIXED_AND_VERIFIED")
            self.assertEqual(len(res["projects_verified"]), 3)
            for proj in res["projects_verified"]:
                self.assertEqual(proj["post_transfer_recall_standing"], "REOPEN")
                self.assertGreaterEqual(proj["successor_continued_version"], 2)
            self.assertTrue(res["creator_persistence_verified"])
            self.assertTrue(res["successor_persistence_verified"])

    def test_04_application_d_einstein_scientific_workspace_and_zero_trust_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_application_d_einstein(Path(tmp))
            self.assertEqual(res["level_1_verdict"], "WORKING")
            self.assertIn("H3_REGIME_CLAMPED_LATENT_CONSERVATION", res["surviving_hypotheses"])
            self.assertIn("H2_VISCOELASTIC_SCALAR_WITNESS_CRP001", res["falsified_hypotheses_preserved"])
            self.assertTrue(res["negative_finding_erasure_blocked"])
            self.assertTrue(res["fabricated_observation_blocked"])
            self.assertTrue(res["oracle_answer_leakage_blocked"])
            self.assertTrue(res["independent_replay"]["replay_verified"])
            self.assertEqual(
                res["invalidated_evidence_propagation"]["reopened_conclusions"],
                ["C2_EXTREME_HEAT_43C_THRESHOLD_CALIBRATION"],
            )

    def test_05_application_e_arendt_public_infrastructure_accountability_and_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_application_e_arendt(Path(tmp))
            self.assertEqual(res["level_1_verdict"], "WORKING")
            self.assertIn("PROP-B-OVERSIZED-LFP-MEMBRANE", res["qualified_proposals_before_challenge"])
            self.assertNotIn("PROP-B-OVERSIZED-LFP-MEMBRANE", res["qualified_proposals_after_challenge"])
            self.assertEqual(res["recommended_proposal_id"], "PROP-C-SDD-GRAVITY-MULTIBARRIER")
            self.assertEqual(res["decision_recall_standing"], "REOPEN")
            self.assertEqual(len(res["standalone_dossier_sha256"]), 64)

    def test_06_central_experiment_and_sixth_finding_on_unfamiliar_pharmacy_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_central_experiment_and_sixth_finding(Path(tmp))
            ce = res["central_experiment"]
            self.assertEqual(ce["break_even_project_count_n"], 4)
            self.assertTrue(ce["provider_swap_preserved_accepted_bytes"])
            self.assertLess(ce["subsequent_project_eval_cost"], ce["conventional_project_eval_cost"])

            sf = res["sixth_finding_emergent_capability"]
            self.assertEqual(sf["capability_id"], "evidence-triaged-counterfactual-auditor-v1")
            self.assertEqual(sf["missing_evidence_fail_closed_status"], "HOLD_INCOMPLETE_EPISTEMIC_BASIS")
            self.assertEqual(sf["verified_evidence_accepted_status"], "ACCEPTED")
            self.assertEqual(sf["inheritance_mode"], "INHERITED")
            self.assertEqual(sf["recommended_option_at_34c"], "PHARM-OPT-2-WHO-PQS-PCM-COOP-HUB")
            self.assertEqual(sf["recommended_option_at_52c_heatwave"], "PHARM-OPT-3-HYBRID-PCM-MICRO-LFP")

    def test_07_operating_law_eight_adversarial_falsifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_operating_law_eight_falsifier_suite(Path(tmp))
            self.assertTrue(res["all_eight_vectors_passed"])
            self.assertEqual(res["vectors_passed_count"], 8)



    def test_08_http_server_end_to_end_civilization_journey(self) -> None:
        from http.server import ThreadingHTTPServer
        import json as _json
        import threading
        import urllib.error
        import urllib.request
        from genie_server import GenieRequestHandler

        with tempfile.TemporaryDirectory() as tmp:
            eng = LivingProjectEngine(Path(tmp))
            handler_cls = type("CivTestHandler", (GenieRequestHandler,), {"engine": eng})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
            port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            base_url = f"http://127.0.0.1:{port}"

            def _post(path: str, payload: dict) -> tuple[int, dict]:
                req = urllib.request.Request(
                    base_url + path,
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Host": f"127.0.0.1:{port}"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return resp.status, _json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as e:
                    return e.code, _json.loads(e.read().decode("utf-8"))

            try:
                prompts = [
                    "Build a community energy cooperative and essential-cost analyzer for Franklin",
                    "Build a privacy-conscious public-benefits and institutional appeal assistant for Baldwin",
                    "Build a community rainwater and biosand multi-barrier safe water filtration hub",
                    "Build a self-correcting scientific research workspace for competing hypotheses (Einstein)",
                    "Build a public infrastructure decision accountability record system for Arendt",
                ]
                built_pids = []
                for pr in prompts:
                    st_code, b = _post("/api/build", {"prompt": pr, "use_model": False})
                    self.assertEqual(st_code, 200)
                    built_pids.append(b["project_id"])

                pid_a = built_pids[0]
                st_p, b_prop = _post("/api/propose", {"project_id": pid_a, "summary": "HTTP proposal test", "patch": {"notes": "http_v2"}})
                self.assertEqual(st_p, 200)
                prop_id = b_prop["exploratory"][0]["proposal_id"]

                # Trigger STOP -> verify HTTP 409 on mutation
                st_stop, _ = _post("/api/stop", {"reason": "HTTP stop test"})
                self.assertEqual(st_stop, 200)
                st_blocked, _ = _post("/api/propose", {"project_id": pid_a, "summary": "Blocked while stopped", "patch": {}})
                self.assertEqual(st_blocked, 409)

                # Clear STOP and stage fresh proposal -> accept
                st_clr, _ = _post("/api/clear_stop", {"reason": "Resume"})
                self.assertEqual(st_clr, 200)
                st_p2, b_prop2 = _post("/api/propose", {"project_id": pid_a, "summary": "Post-stop valid proposal", "patch": {"notes": "http_v2_valid"}})
                self.assertEqual(st_p2, 200)
                st_acc, b_acc = _post("/api/accept", {"project_id": pid_a, "proposal_id": b_prop2["exploratory"][0]["proposal_id"]})
                self.assertEqual(st_acc, 200)
                self.assertEqual(b_acc["accepted"]["version"], 2)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
