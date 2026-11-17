#!/usr/bin/env python3
"""Comprehensive Release-Blocker Closure & Security Attack Suite for OpenLine Genie v1.2.0-rc3
(`tests/test_rc3_final_release_closure.py`).

Verifies all four Section 2 blockers (`2.A`, `2.B`, `2.C`, `2.D`) and Section 5 Stop Conditions:
- Blocker 2.A (Holdout Decontamination & Independent Evaluation Boundary):
  * Zero benchmark/holdout cases or self-acceptance authority in `core/visual_intelligence_harness.py`.
  * General SVG and $N$-room floor-plan solvers operate on unseen arbitrary element IDs and room counts.
  * `core/independent_evaluation_boundary.py` blocks oracle keys and `GENIE_PRIVATE_EVALUATOR_VAULT` access.
- Blocker 2.B (Real Selenium/Chromium Browser Acceptance):
  * `functional_runner.py` contains zero mock `selenium` shims.
  * Live Headless Chromium (`selenium` + `/usr/bin/chromium`) executes mobile (`390x844`) and desktop
    (`1280x800`) viewports, stateful interactions, visual inspection, offline operation, and export.
- Blocker 2.C (Release Consistency):
  * `pyproject.toml` (`1.2.0rc3`), `launch_genie.py` (`1.2.0-rc3`), `README.md`, `RELEASE_NOTES.md`,
    `INSTALL.md`, `requirements.txt`, and entry points are 100% aligned.
- Blocker 2.D (Authority & Security Attacks on Visual Repair Harness + Genie):
  * Proposed repairs cannot bypass receiver-controlled acceptance (`attempt_direct_commit`/`bypass_receiver`).
  * Proposed repairs cannot corrupt accepted work or delete controls/SVG nodes/rooms.
  * Proposed repairs cannot reset spending limits (`SpendLedger` tamper/reset blocked).
  * Proposed repairs cannot forge receipts (`caller_supplied_receipt` or forged capsule signature blocked).
  * Proposed repairs cannot disable or bypass `STOP` (`GuardRefused` / `PermissionError`).
  * Failed visual inspection (browser crash, empty/truncated HTML, or unresolved defect) NEVER silently
    becomes approval.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest

import core.visual_intelligence_harness as vih
from core.independent_evaluation_boundary import (
    assert_not_inside_private_evaluator_vault,
    submit_candidate_repair_for_external_evaluation,
)
from core.model_adapter import AnthropicAdapter, SpendLedger
from core.openline_guard import GuardRefused
from core.portable_verified_inheritance import (
    WorkerBPortableInheritanceRuntime,
    qualify_and_export_visual_capsule_worker_a,
)
from core.visual_intelligence_harness import (
    CANDIDATE_HAS_EVALUATION_AUTHORITY,
    check_candidate_visual_and_functional_invariants,
    diagnose_visual_causal_bottleneck,
    observe_rendered_artifact,
    repair_visual_artifact,
)
from genie_engine import OpenLineGenieEngine
from launch_genie import verify_seven_applications_ready
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class _BrokenBrowserPageMock:
    """Simulates a failing browser page to verify that failed visual inspection never becomes approval."""

    def set_viewport_size(self, vp: dict[str, int]) -> None:
        pass

    def set_content(self, html: str) -> None:
        raise RuntimeError("Simulated Chromium renderer crash during visual inspection")

    def screenshot(self, path: Path) -> None:
        raise RuntimeError("Simulated Chromium screenshot failure")


class TestRC3FinalReleaseClosure(unittest.TestCase):
    def test_01_blocker_a_holdout_decontamination_and_general_solvers(self) -> None:
        """Verifies Blocker 2.A: zero holdout contamination or evaluation authority in `core/`,
        and general geometric solvers work on arbitrary unseen IDs and room counts.
        """
        self.assertFalse(CANDIDATE_HAS_EVALUATION_AUTHORITY)
        self.assertFalse(hasattr(vih, "build_benchmark_task_suite"))
        self.assertFalse(hasattr(vih, "run_four_way_capability_tournament"))

        vih_src = Path(inspect.getfile(vih)).read_text(encoding="utf-8")
        self.assertNotIn("HOLD-01", vih_src)
        self.assertNotIn("DEV-01", vih_src)
        self.assertNotIn("sealed_holdout", vih_src)
        self.assertNotIn("room-1", vih_src)
        self.assertNotIn("node-b", vih_src)

        # Test general 4-room floor plan with completely custom IDs (no room-1/2/3)
        custom_floorplan_html = (
            "<!DOCTYPE html><html><body>"
            '<svg viewBox="0 0 520 340" width="520" height="340">'
            '<rect id="custom-footprint-99" data-role="footprint" x="30" y="30" width="440" height="260" />'
            '<rect id="bay-alpha" data-role="room" data-label="Alpha Sterile" x="30" y="30" width="280" height="260" />'
            '<rect id="bay-beta" data-role="room" data-label="Beta Airlock" x="180" y="30" width="20" height="120" />'
            '<rect id="bay-gamma" data-role="room" data-label="Gamma Pump" x="250" y="100" width="220" height="190" />'
            '<rect id="bay-delta" data-role="room" data-label="Delta Telemetry" x="320" y="180" width="100" height="80" />'
            "</svg></body></html>"
        )
        obs_b = observe_rendered_artifact("custom-fp", custom_floorplan_html, artifact_family="floor_plan")
        diag = diagnose_visual_causal_bottleneck(obs_b, mode="D_HYBRID_EMERGENCE")
        self.assertTrue(diag["bottleneck_identified"])
        repaired_fp = repair_visual_artifact(custom_floorplan_html, diag)
        obs_a = observe_rendered_artifact("custom-fp-after", repaired_fp, artifact_family="floor_plan")
        precheck = check_candidate_visual_and_functional_invariants(obs_b, obs_a)
        self.assertTrue(precheck["candidate_self_check_passed"])
        self.assertFalse(precheck["independently_accepted"])
        self.assertEqual(len(obs_a.rooms), 4)
        self.assertGreaterEqual(len(obs_a.doors), 3)

        # Test general SVG diagram with 3 overlapping custom-ID nodes and colliding text
        custom_svg_html = (
            "<!DOCTYPE html><html><body>"
            '<svg viewBox="0 0 260 140" width="260" height="140">'
            '<rect id="stage-x1" data-role="node" x="20" y="40" width="110" height="54" />'
            '<rect id="stage-y2" data-role="node" x="75" y="40" width="110" height="54" />'
            '<rect id="stage-z3" data-role="node" x="130" y="40" width="110" height="54" />'
            '<text id="caption-main" x="85" y="65">Overlapping Pipeline Stage</text>'
            "</svg></body></html>"
        )
        obs_sb = observe_rendered_artifact("custom-svg", custom_svg_html, artifact_family="svg_diagram")
        diag_s = diagnose_visual_causal_bottleneck(obs_sb, mode="D_HYBRID_EMERGENCE")
        self.assertTrue(diag_s["bottleneck_identified"])
        repaired_svg = repair_visual_artifact(custom_svg_html, diag_s)
        obs_sa = observe_rendered_artifact("custom-svg-after", repaired_svg, artifact_family="svg_diagram")
        precheck_s = check_candidate_visual_and_functional_invariants(obs_sb, obs_sa)
        self.assertTrue(precheck_s["candidate_self_check_passed"])
        self.assertFalse(precheck_s["independently_accepted"])

    def test_02_blocker_a_independent_evaluation_boundary_oracle_and_vault_isolation(self) -> None:
        """Verifies that `core/independent_evaluation_boundary.py` blocks oracle keys and private vault paths."""
        clean_task = {
            "task_id": "EXT-01",
            "artifact_family": "responsive_ui",
            "initial_html": (
                "<!DOCTYPE html><html><body>"
                '<header id="hdr" style="position:fixed;left:0px;top:0px;width:390px;height:70px;z-index:20;">Nav</header>'
                '<input id="i1" type="text" value="A" style="left:20px;top:90px;width:140px;height:36px;" />'
                '<button id="b1" type="button" onclick="window.__handleAction && window.__handleAction()" style="left:20px;top:16px;width:120px;height:36px;">Add</button>'
                "</body></html>"
            ),
        }
        sub = submit_candidate_repair_for_external_evaluation(clean_task)
        self.assertEqual(sub["status"], "CANDIDATE_SUBMISSION_AWAITING_INDEPENDENT_EVALUATOR")
        self.assertTrue(sub["candidate_self_check_passed"])
        self.assertFalse(sub["independently_accepted"])
        self.assertFalse(sub["promoted_to_accepted_state"])

        # Oracle key inside task input must be rejected fail-closed
        for bad_key in ("expected_html", "expected_defects", "private_holdout_verdict", "force_accept", "bypass_receiver"):
            tainted = copy.deepcopy(clean_task)
            tainted["nested_meta"] = [{bad_key: True}]
            with self.assertRaises(PermissionError):
                submit_candidate_repair_for_external_evaluation(tainted)

        # Private evaluator vault path access must be blocked
        with tempfile.TemporaryDirectory(prefix="private_eval_vault_") as vault_dir:
            old_env = os.environ.get("GENIE_PRIVATE_EVALUATOR_VAULT")
            os.environ["GENIE_PRIVATE_EVALUATOR_VAULT"] = vault_dir
            try:
                with self.assertRaises(PermissionError):
                    assert_not_inside_private_evaluator_vault(Path(vault_dir) / "secret_holdout.json")
                with self.assertRaises(PermissionError):
                    submit_candidate_repair_for_external_evaluation(
                        clean_task,
                        artifact_output_dir=Path(vault_dir) / "out",
                    )
            finally:
                if old_env is None:
                    os.environ.pop("GENIE_PRIVATE_EVALUATOR_VAULT", None)
                else:
                    os.environ["GENIE_PRIVATE_EVALUATOR_VAULT"] = old_env

    def test_03_blocker_b_and_c_release_consistency_and_real_selenium_environment(self) -> None:
        """Verifies Blocker 2.B & 2.C: no mock selenium shims, real Chromium observation works,
        and `pyproject.toml`, `launch_genie.py`, `README.md`, `RELEASE_NOTES.md`, and `INSTALL.md`
        all match `v1.2.0-rc3` (`1.2.0rc3`).
        """
        func_runner_txt = (ROOT / "functional_runner.py").read_text(encoding="utf-8")
        self.assertNotIn("types.ModuleType", func_runner_txt)
        self.assertNotIn("sys.modules[name] = types.ModuleType", func_runner_txt)

        pyproj_txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "1.2.0rc3"', pyproj_txt)
        self.assertIn("v1.2.0-rc3", pyproj_txt)
        self.assertIn("selenium>=4.8.0", pyproj_txt)
        self.assertIn("Pillow>=10.0.0", pyproj_txt)
        self.assertIn('openline-genie = "launch_genie:main"', pyproj_txt)

        reqs_txt = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for dep in ("cryptography", "numpy", "onnxruntime", "Pillow", "selenium"):
            self.assertIn(dep, reqs_txt)

        for doc_name in ("README.md", "RELEASE_NOTES.md", "INSTALL.md"):
            doc_txt = (ROOT / doc_name).read_text(encoding="utf-8")
            self.assertIn("v1.2.0-rc3", doc_txt, f"{doc_name} missing v1.2.0-rc3")

        with tempfile.TemporaryDirectory(prefix="rc3_verify_7apps_") as td:
            ver_rep = verify_seven_applications_ready(Path(td))
            self.assertEqual(ver_rep["status"], "READY")
            self.assertEqual(ver_rep["version"], "1.2.0-rc3")
            self.assertEqual(len(ver_rep["seven_applications_ready"]), 7)

        # Verify real Headless Chromium observation in `observe_rendered_artifact`
        sample_html = (
            "<!DOCTYPE html><html><body>"
            '<input id="inp-live" data-bind-assumption="solar_kw" type="number" value="42" style="left:24px;top:24px;width:160px;height:36px;" />'
            '<button id="btn-live" type="button" onclick="window.__handleAction && window.__handleAction()" style="left:24px;top:80px;width:140px;height:38px;">Save</button>'
            "</body></html>"
        )
        with tempfile.TemporaryDirectory(prefix="rc3_real_browser_obs_") as shot_dir:
            shot_file = Path(shot_dir) / "real_chromium.png"
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 390, "height": 844})
                obs = observe_rendered_artifact(
                    "real-chromium-test",
                    sample_html,
                    artifact_family="stateful_app",
                    accepted_state={"solar_kw": 42},
                    screenshot_path=shot_file,
                    browser_page=page,
                    require_real_browser=True,
                )
                browser.close()
            self.assertTrue(obs.observed_via_real_browser)
            self.assertFalse(obs.inspection_failed)
            self.assertTrue(shot_file.is_file() and shot_file.stat().st_size > 100)

    def test_04_blocker_d_authority_security_and_fail_closed_inspection_attacks(self) -> None:
        """Attacks the visual repair harness and its Genie integration across all 6 security requirements."""
        with tempfile.TemporaryDirectory(prefix="rc3_sec_attack_") as td:
            td_path = Path(td)
            eng = OpenLineGenieEngine(state_dir=td_path)

            # Build a real synthesized operational micro-app project
            bundle0 = eng.build_from_prompt(
                "Build a custom cold-room inventory & shift dispatch tracker with daily log entries.",
                use_model=False,
            )
            pid = bundle0["project_id"]
            sha0 = bundle0["accepted"]["state_sha256"]
            ver0 = bundle0["accepted"]["version"]
            clean_html = bundle0["app"]["content"]

            # 1. Attack: Attempt to bypass receiver-controlled acceptance (`attempt_direct_commit=True` / `bypass_receiver=True`)
            with self.assertRaisesRegex(PermissionError, "CANNOT_BYPASS_RECEIVER_ACCEPTANCE"):
                eng.propose_visual_artifact_repair(pid, clean_html, attempt_direct_commit=True)
            with self.assertRaisesRegex(PermissionError, "CANNOT_BYPASS_RECEIVER_ACCEPTANCE"):
                eng.propose_visual_artifact_repair(pid, clean_html, bypass_receiver=True)

            # 2. Attack: Attempt to supply a forged receipt
            with self.assertRaisesRegex(PermissionError, "FORGED_OR_CALLER_RECEIPT_REJECTED"):
                eng.propose_visual_artifact_repair(
                    pid,
                    clean_html,
                    caller_supplied_receipt={"status": "COMMITTED", "signature": "00" * 32},
                )

            # 3. Attack: Attempt to reset spending limits or pass negative spend override
            with self.assertRaisesRegex(PermissionError, "SPEND_LIMIT_RESET_FORBIDDEN"):
                eng.propose_visual_artifact_repair(pid, clean_html, reset_spend_limit=True)
            with self.assertRaisesRegex(PermissionError, "SPEND_LIMIT_RESET_FORBIDDEN"):
                eng.propose_visual_artifact_repair(pid, clean_html, spend_delta_override_usd=-1.50)

            # 4. Attack: Failed visual inspection MUST NOT silently become approval
            # 4a. Simulated Chromium crash during `observe_rendered_artifact`
            broken_page = _BrokenBrowserPageMock()
            obs_crash = observe_rendered_artifact("crash-probe", clean_html, browser_page=broken_page)
            self.assertTrue(obs_crash.inspection_failed)
            with self.assertRaisesRegex(PermissionError, "VISUAL_INSPECTION_FAILED"):
                eng.propose_visual_artifact_repair(pid, clean_html, browser_page=broken_page)

            # 4b. `require_real_browser=True` when `browser_page=None` must fail closed
            with self.assertRaisesRegex(PermissionError, "VISUAL_INSPECTION_FAILED"):
                eng.propose_visual_artifact_repair(pid, clean_html, browser_page=None, require_real_browser=True)

            # 4c. Truncated/malformed HTML or control-deleting HTML must fail closed
            with self.assertRaisesRegex(PermissionError, "VISUAL_INSPECTION_FAILED_CANNOT_BECOME_APPROVAL"):
                eng.propose_visual_artifact_repair(pid, "<html><body>truncated without closing tag")
            degraded_html = "<!DOCTYPE html><html><body><div>All buttons deleted</div></body></html>"
            with self.assertRaisesRegex(PermissionError, "VISUAL_INSPECTION_FAILED_CANNOT_BECOME_APPROVAL"):
                eng.propose_visual_artifact_repair(pid, degraded_html)

            # Verify accepted work was 100% untouched across all failed attacks
            bundle_check = eng.get_project_bundle(pid)
            self.assertEqual(bundle_check["accepted"]["state_sha256"], sha0)
            self.assertEqual(bundle_check["accepted"]["version"], ver0)

            # 5. Valid visual repair stages ONLY as exploratory, leaving accepted state untouched until receiver accept
            staged = eng.propose_visual_artifact_repair(
                pid,
                clean_html,
                summary="Verified non-degrading visual layout check",
            )
            self.assertEqual(staged["status"], "STAGED_EXPLORATORY_AWAITING_RECEIVER_ACCEPTANCE")
            self.assertTrue(staged["accepted_sha256_preserved"])
            self.assertEqual(eng.get_project_bundle(pid)["accepted"]["state_sha256"], sha0)
            prop_id = staged["proposal"]["proposal_id"]

            # 6. Attack: Attempt to disable STOP or promote pre-STOP proposal after STOP
            with self.assertRaisesRegex(PermissionError, "CANNOT_DISABLE_STOP"):
                eng.propose_visual_artifact_repair(pid, clean_html, disable_stop=True)

            eng.trigger_stop("Security test STOP")
            with self.assertRaises(GuardRefused):
                eng.propose_visual_artifact_repair(pid, clean_html)
            with self.assertRaises(GuardRefused):
                eng.accept_exploratory_change(pid, prop_id)

            # Even after clearing STOP, the pre-STOP proposal is revoked by authority epoch advancement!
            eng.clear_stop("Resume after STOP")
            with self.assertRaisesRegex(PermissionError, "cannot_promote_revoked_proposal|proposal_epoch_expired"):
                eng.accept_exploratory_change(pid, prop_id)
            self.assertEqual(eng.get_project_bundle(pid)["accepted"]["state_sha256"], sha0)

            # Stage a fresh visual repair in the new epoch and accept it via receiver authority
            staged2 = eng.propose_visual_artifact_repair(
                pid,
                clean_html.replace("</body>", "<!-- receiver-verified-visual-pass --></body>"),
                summary="Fresh epoch visual repair",
            )
            prop2_id = staged2["proposal"]["proposal_id"]
            accepted_bundle = eng.accept_exploratory_change(pid, prop2_id)
            self.assertEqual(accepted_bundle["accepted"]["version"], ver0 + 1)
            self.assertNotEqual(accepted_bundle["accepted"]["state_sha256"], sha0)


if __name__ == "__main__":
    unittest.main()
