#!/usr/bin/env python3
"""Unit test suite for Section 3 Real Product Dogfooding & Second-Worker
Visual Capability Inheritance (`tests/test_rc3_dogfood_and_inheritance.py`).
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_rc3_dogfood_and_browser_acceptance import run_dogfood_and_inheritance_suite


class TestRC3DogfoodAndInheritance(unittest.TestCase):
    def test_01_real_product_dogfood_three_artifacts_and_worker_b_inheritance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rc3_dogfood_test_") as td:
            out_dir = Path(td)
            rep = run_dogfood_and_inheritance_suite(output_dir=out_dir)

            # 1. Responsive Interface (ClearCovenant across 390x844, 320x640, 1280x800 in real Chromium)
            a1 = rep["dogfood_artifacts"]["artifact_1_responsive_interface"]
            self.assertIn("FIXED_HEADER_HIT_OCCLUSION", a1["failure_trace_before"])
            self.assertIn("ANCESTOR_OVERFLOW_CLIPPING", a1["failure_trace_before"])
            self.assertTrue(a1["staged_exploratory_preserved_accepted_sha"])
            for vp_name in ("390x844", "320x640", "1280x800"):
                vp_res = a1["viewport_verifications"][vp_name]
                self.assertTrue(vp_res["observed_via_real_browser"])
                self.assertTrue(vp_res["candidate_self_check_passed"])
                self.assertEqual(vp_res["total_defects_remaining"], 0)
                self.assertTrue(vp_res["interactive_click_status_text"].startswith("Inspected:"))
                self.assertTrue((out_dir / vp_res["screenshot_file"]).is_file())

            # 2. Stateful Application (Solar & Cold-Room Dispatch + Corrupted Repair Rejection)
            a2 = rep["dogfood_artifacts"]["artifact_2_stateful_application"]
            self.assertIn("SANDBOX_NATIVE_SUBMIT_TRAP", a2["failure_trace_before"])
            self.assertIn("STATE_VIEW_DEFAULT_DESYNC", a2["failure_trace_before"])
            self.assertIn("EXTERNAL_CDN_RUNTIME_ERROR", a2["failure_trace_before"])
            self.assertIn("REJECTED_FUNCTIONAL_DEGRADATION", a2["corrupted_repair_rejection_trace"])
            self.assertTrue(a2["observed_via_real_browser"])
            self.assertTrue(a2["candidate_self_check_passed"])
            self.assertEqual(
                a2["stateful_interaction_verification"]["dispatch_readout_after_two_clicks"],
                "Committed:2",
            )
            self.assertEqual(
                a2["stateful_interaction_verification"]["dom_bound_values"],
                {"solar_kw": 145, "battery_kwh": 280, "reserve_floor_pct": 25},
            )
            self.assertEqual(
                a2["stateful_interaction_verification"]["advocate_persisted_inputs"],
                {"filing_date": "2026-11-15", "appeal_window_days": 45},
            )

            # 3. Structured Diagram & 4-Bay Facility Floor Plan (SDD-PCM Hub)
            a3 = rep["dogfood_artifacts"]["artifact_3_structured_diagram_and_floorplan"]
            self.assertIn("SVG_VIEWBOX_TRUNCATION", a3["failure_trace_before"])
            self.assertIn("FLOORPLAN_ROOM_OVERLAP", a3["failure_trace_before"])
            self.assertIn("FLOORPLAN_LANDLOCKED_ROOM", a3["failure_trace_before"])
            self.assertTrue(a3["observed_via_real_browser"])
            self.assertTrue(a3["candidate_self_check_passed"])
            gm_after = a3["geometric_metrics_after"]
            self.assertEqual(gm_after["defects_count"], 0)
            self.assertTrue(gm_after["spatial_geometry_passed"])
            self.assertEqual(gm_after["rooms_count"], 4)
            self.assertGreaterEqual(gm_after["doors_count"], 3)
            self.assertEqual(gm_after["svg_clipped_count"], 0)

            # 4. Second-Worker Visual Capability Inheritance (Clean-Room Worker B)
            inh = rep["second_worker_inheritance"]
            self.assertEqual(inh["clean_room_worker_b_import"]["standing"], "ACCEPTED")
            self.assertTrue(inh["worker_b_all_real_dogfood_passed"])
            self.assertEqual(inh["worker_b_standing_after_assumption_drift"], "REOPEN")
            self.assertTrue(inh["ten_step_inheritance_regression"]["all_10_steps_passed"])


if __name__ == "__main__":
    unittest.main()
