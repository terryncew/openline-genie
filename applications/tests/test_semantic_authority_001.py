#!/usr/bin/env python3
"""Unit, Integration, Adversarial Falsification & Capability Inheritance Test Suite
for ARGON — OPENLINE SEMANTIC AUTHORITY BREAKTHROUGH 001 (`tests/test_semantic_authority_001.py`).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.semantic_authority_bridge import (
    ConventionalSemanticDependencyTracker,
    HistoricalEvidenceRewriteRefused,
    NaiveUnconditionalSemanticRecall,
    SemanticAuthorityBridge,
    SemanticOntologyModel,
    SemanticValidationError,
    StaleSemanticAuthorityRefused,
    dump_ontology_yaml,
    normalize_sql_ast_signature,
    simulate_nvidia_semantic_recompilation,
)
from genie_server import start_genie_server
from run_semantic_authority_001 import (
    build_advocate_benefits_ossie_ontology,
    build_civic_infrastructure_ossie_ontology,
    build_energy_commons_ossie_ontology,
    build_unfamiliar_biotech_coldchain_ossie_ontology,
    run_11_stage_ultimate_loop_and_comparators,
    run_adversarial_falsification_suite,
    run_all_semantic_authority_001,
    run_three_application_dogfood,
    run_worker_a_to_worker_b_inheritance,
)


class TestSemanticAuthorityBreakthrough001(unittest.TestCase):
    def test_01_ossie_and_auto_ontology_interchange_and_9_mcp_tools(self) -> None:
        bridge = SemanticAuthorityBridge()
        ossie_dict = build_energy_commons_ossie_ontology()
        yaml_str = dump_ontology_yaml(ossie_dict)
        model = bridge.import_ontology(yaml_str, auto_sign_certified_with_pinned_steward=True)

        # Verify all 9 NVIDIA Auto-Ontology read-only MCP tools
        r1 = model.mcp_check_readiness(can_execute_sql=True)
        self.assertTrue(r1["ready"])
        self.assertEqual(r1["terms_count"], 2)

        r2 = model.mcp_search_terms("avoided")
        self.assertEqual(len(r2["matches"]), 1)
        self.assertEqual(r2["matches"][0]["id"], "TERM_NET_AVOIDED_ELECTRICITY_COST")

        r3 = model.mcp_get_term("TERM_NET_AVOIDED_ELECTRICITY_COST")
        self.assertTrue(r3["term"]["certified"])

        r4 = model.mcp_get_term_columns("TERM_NET_AVOIDED_ELECTRICITY_COST")
        self.assertEqual(len(r4["columns"]), 4)
        self.assertEqual(len(r4["missing_columns"]), 0)

        r5 = model.mcp_get_term_sql_attributes("TERM_NET_AVOIDED_ELECTRICITY_COST")
        self.assertEqual(len(r5["sql_attributes"]), 1)

        r6 = model.mcp_get_sql_attribute("SQL_ATTR_AVOIDED_TOU_COST")
        self.assertEqual(r6["sql_attribute"]["term_id"], "TERM_NET_AVOIDED_ELECTRICITY_COST")

        r7 = model.mcp_describe_table("meters")
        self.assertIn("TERM_NET_AVOIDED_ELECTRICITY_COST", r7["related_terms"])

        # Answerable vs Cannot Answer ("ad spend" test per NVIDIA README)
        r8_ok = model.mcp_check_answerable("avoided electricity cost", ["avoided", "electricity"])
        self.assertEqual(r8_ok["verdict"], "answerable")
        r8_no = model.mcp_check_answerable("return on advertising spend", ["advertising"])
        self.assertEqual(r8_no["verdict"], "cannot_answer")
        self.assertEqual(r8_no["coverage"], 0.0)

        r9 = model.mcp_ask_question(
            "What is the net avoided electricity cost?",
            term_ids=["TERM_NET_AVOIDED_ELECTRICITY_COST"],
            require_certified_gate=True,
        )
        self.assertEqual(r9["status"], "ok")
        self.assertIn("service_tariff_schedule_id", r9["sql"])

        # Round-trip native Auto-Ontology format import/export
        native_dict = model.export_auto_ontology_native_dict()
        model_native = SemanticOntologyModel(native_dict)
        self.assertEqual(set(model_native.terms.keys()), set(model.terms.keys()))

    def test_02_boundary_conditions_a_and_b_vs_conventional_tracker(self) -> None:
        bridge = SemanticAuthorityBridge()
        m_init = bridge.import_ontology(build_energy_commons_ossie_ontology(), auto_sign_certified_with_pinned_steward=True)

        # Conventional tracker binds to term version + raw SQL expression
        conv = ConventionalSemanticDependencyTracker()
        conv.bind(
            m_init,
            project_id="P_BOUNDARY",
            decision_id="DEC_1",
            bound_term_ids=["TERM_NET_AVOIDED_ELECTRICITY_COST"],
            bound_sql_attr_ids=["SQL_ATTR_AVOIDED_TOU_COST"],
        )

        # OpenLine bridge binds decision
        bridge.bind_decision(
            project_id="P_BOUNDARY",
            decision_id="DEC_1",
            conclusion_summary="Coop Option 3",
            proposed_action="Sign EPC contract",
            bound_term_ids=["TERM_NET_AVOIDED_ELECTRICITY_COST"],
            bound_sql_attr_ids=["SQL_ATTR_AVOIDED_TOU_COST"],
            bound_join_edge_ids=["REL_METER_TO_SERVICE_TARIFF"],
        )

        # Boundary Condition B: Semantic recompilation reselects default FK join role (`all_legacy_wholesale_schedule` < `service_tariff_schedule`)
        m_recomp = simulate_nvidia_semantic_recompilation(m_init)
        bridge.sign_all_certified_terms_in_ontology(m_recomp)

        # Conventional tracker misses Boundary B completely!
        conv_affected, _ = conv.check_affected(m_recomp, "P_BOUNDARY", "DEC_1")
        self.assertFalse(conv_affected)

        # OpenLine SSB-CDIG catches Boundary B deterministically!
        rep_b = bridge.detect_and_apply_semantic_changes(m_recomp, project_id="P_BOUNDARY")
        self.assertEqual(len(rep_b["affected_decisions"]), 1)
        self.assertEqual(rep_b["affected_decisions"][0]["standing"], "REOPEN")
        self.assertIn(
            "SEMANTIC_FK_JOIN_DEFAULT_OR_RELATIONSHIP_CHANGED",
            rep_b["affected_decisions"][0]["reasons_for_reopening"],
        )

    def test_03_ultimate_loop_11_stages_and_60_holdout_episodes(self) -> None:
        loop_res = run_11_stage_ultimate_loop_and_comparators()
        scores = loop_res["stages"]["1_OBSERVE"]["candidate_scores"]
        c3 = scores["C3_OPENLINE_SSB_CDIG"]
        self.assertEqual(c3["accuracy_pct"], 100.0)
        self.assertEqual(c3["false_recalls_out_of_20_harmless"], 0)
        self.assertEqual(c3["missed_consequential_out_of_40"], 0)
        self.assertEqual(c3["stale_authority_execution_leaks_out_of_40"], 0)
        self.assertGreater(c3["accuracy_pct"], scores["C1_CONVENTIONAL_TERM_VERSION_TRACKER"]["accuracy_pct"])
        self.assertGreater(c3["accuracy_pct"], scores["C2_INITIAL_HYPOTHESIS_UNCONDITIONAL_RECALL"]["accuracy_pct"])

    def test_04_three_application_workflows_dogfood(self) -> None:
        dogfood = run_three_application_dogfood()
        # Energy Commons
        ec = dogfood["energy_commons"]
        self.assertEqual(ec["harmless_edit_false_recalls"], 0)
        self.assertEqual(ec["affected_decisions"], ["DEC-ENERGY-COOP-RANKING"])
        self.assertEqual(ec["unaffected_decisions"], ["DEC-ENERGY-PUMP-SCHEDULE"])
        self.assertTrue(ec["stale_epc_execution_blocked"])
        self.assertTrue(ec["unaffected_pump_action_executed"])
        self.assertTrue(ec["export_verification"]["valid"])

        # Civic
        cv = dogfood["civic_infrastructure"]
        self.assertEqual(cv["affected_decisions"], ["DEC-CIVIC-WATER-RESILIENCE-REC"])
        self.assertEqual(cv["unaffected_decisions"], ["DEC-CIVIC-NOISE-WALL-SPEC"])
        self.assertTrue(cv["stale_bond_execution_blocked"])
        self.assertTrue(cv["v2_reevaluation"]["requires_roughing_prefilter_covenant"])
        self.assertTrue(cv["export_verification"]["valid"])

        # Advocate
        adv = dogfood["advocate_appeal"]
        self.assertTrue(adv["historical_evidence_overwrite_blocked"])
        self.assertEqual(adv["affected_decisions"], ["CLAIM-1-DISASTER-GRANT-EXCLUSION"])
        self.assertEqual(adv["unaffected_decisions"], ["CLAIM-2-MEDICAL-RECERT-FAX"])
        self.assertTrue(adv["stale_brief_submission_blocked"])
        self.assertTrue(adv["export_verification"]["valid"])

    def test_05_ten_adversarial_falsification_vectors(self) -> None:
        adv = run_adversarial_falsification_suite()
        self.assertEqual(adv["total_adversarial_vectors"], 10)
        self.assertEqual(adv["blocked_count"], 10)
        self.assertTrue(adv["all_blocked"])

    def test_06_worker_a_to_worker_b_clean_isolated_inheritance(self) -> None:
        # Also verify in a genuinely separate temporary directory copy with only capabilities_007_008 + core
        with tempfile.TemporaryDirectory(prefix="worker_b_isolated_") as tmp_b:
            b_root = Path(tmp_b)
            shutil.copytree(HERE / "core", b_root / "core")
            shutil.copytree(HERE / "capabilities_007_008", b_root / "capabilities_007_008")
            # Run Worker B in a separate subprocess with cwd=b_root
            cmd = [
                sys.executable,
                "-c",
                (
                    "import sys, json; sys.path.insert(0, \".\"); from pathlib import Path; "
                    "from capabilities_007_008 import kernel; "
                    f"from run_semantic_authority_001 import run_worker_a_to_worker_b_inheritance; "
                    "res = run_worker_a_to_worker_b_inheritance(); "
                    "assert res['worker_b_kernel_disposition'] == 'EXECUTED'; "
                    "assert res['affected_decisions'] == ['DEC-BIOLOGICS-LOT-RELEASE']; "
                    "assert res['unaffected_decisions'] == ['DEC-BIOLOGICS-VIAL-INVENTORY']; "
                    "assert res['independent_verification']['valid'] is True; "
                    "print('WORKER_B_ISOLATED_OK')"
                ),
            ]
            # Copy run_semantic_authority_001.py helper ontology builder into b_root
            shutil.copy2(HERE / "run_semantic_authority_001.py", b_root / "run_semantic_authority_001.py")
            proc = subprocess.run(cmd, cwd=str(b_root), capture_output=True, text=True, check=True)
            self.assertIn("WORKER_B_ISOLATED_OK", proc.stdout)

    def test_07_http_semantic_workbench_and_api_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_state:
            # Find free port
            port = 8891
            for p in range(8891, 8930):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex(("127.0.0.1", p)) != 0:
                        port = p
                        break
            srv = start_genie_server(port=port, state_dir=tmp_state, use_model=False)
            import threading
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/semantic", timeout=10) as r:
                    html_body = r.read().decode("utf-8")
                    self.assertEqual(r.status, 200)
                    self.assertIn("OPENLINE SEMANTIC AUTHORITY BRIDGE", html_body)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/semantic/state", timeout=15) as r:
                    data = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(r.status, 200)
                    self.assertEqual(
                        data["ultimate_loop_11_stages"]["stages"]["6_VERIFY"]["verified_accuracy_pct"],
                        100.0,
                    )
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
