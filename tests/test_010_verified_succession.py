"""Unit and adversarial falsification tests for ARGON — ULTIMATE LOOP 010: Verified Autonomous Succession."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.verified_succession import (
    UNFAMILIAR_HELD_OUT_TASKS,
    run_decisive_hostile_experiment,
    run_emergence_and_live_succession_experiment,
    run_normative_revocation_closure_matrix,
)


class TestVerifiedAutonomousSuccession010(unittest.TestCase):
    def test_decisive_hostile_experiment_arms_a_b_c_d(self) -> None:
        res = run_decisive_hostile_experiment()
        arm_a = res["A_existing_openline_009"]
        arm_b = res["B_conventional_coordination"]
        arm_c = res["C_minimal_repair_openline_010"]
        arm_d = res["D_new_mechanism_evaluation"]

        # Arm A (unchanged 009) demonstrates the diagnosed post-revocation outbox/lineage/epoch gaps
        self.assertGreater(arm_a["unauthorized_effects_after_revocation"], 0)
        self.assertGreater(arm_a["false_closure_declarations"], 0)
        self.assertTrue(arm_a["accepted_work_preserved"])

        # Arm B (conventional) demonstrates lease TTL / derived token / outbox / retry duplication gaps
        self.assertGreater(arm_b["unauthorized_effects_after_revocation"], 0)
        self.assertGreater(arm_b["false_closure_declarations"], 0)
        self.assertGreater(arm_b["duplicate_sink_effects"], 0)

        # Arm C (minimal repair) passes all 8/8 hostile conditions with 0 unauthorized effects and 0 false closures
        self.assertEqual(arm_c["unauthorized_effects_after_revocation"], 0)
        self.assertEqual(arm_c["false_closure_declarations"], 0)
        self.assertEqual(arm_c["duplicate_sink_effects"], 0)
        self.assertTrue(arm_c["accepted_work_preserved"])
        self.assertEqual(arm_c["hostile_conditions_passed"], 8)
        self.assertEqual(arm_c["hostile_conditions_total"], 8)
        self.assertEqual(arm_c["closure_transitions_verified"]["while_c2_dropped"], "PARTIAL")
        self.assertEqual(arm_c["closure_transitions_verified"]["after_c4_and_c5"], "CLOSED")
        self.assertEqual(arm_c["closure_transitions_verified"]["while_outbox_in_flight_unknown"], "UNKNOWN")

        # Arm D is excluded because Arm C meets all acceptance conditions
        self.assertFalse(arm_d["included"])

    def test_normative_eb27_and_watts_closure_matrix(self) -> None:
        mat = run_normative_revocation_closure_matrix()
        self.assertEqual(mat["eb27_cases_total"], 8)
        self.assertEqual(mat["c3_detector_false_positives"], 7)
        self.assertEqual(mat["c4_detector_false_positives"], 5)
        self.assertEqual(mat["openline_c0_c5_false_positives"], 0)

    def test_emergence_and_live_succession_on_unfamiliar_tasks(self) -> None:
        em = run_emergence_and_live_succession_experiment()
        self.assertTrue(em["in_flight_c1_fenced"])
        self.assertEqual(em["e1_closure_disposition"], "CLOSED")
        self.assertEqual(em["unauthorized_post_revocation_effects"], 0)
        self.assertTrue(em["pre_replacement_work_preserved_and_not_redone"])

        comp = em["unfamiliar_tasks_comparison"]
        self.assertEqual(comp["fixed_capability_baseline"]["feasible_count"], 0)
        self.assertEqual(comp["verified_autonomous_succession"]["feasible_count"], 4)
        self.assertEqual(comp["net_feasibility_gain_pp"], 100.0)
        self.assertGreater(comp["net_utility_gain_points"], 45.0)

    def test_clean_room_subprocess_worker_capability_transfer(self) -> None:
        """Verifies that a separate clean-room subprocess worker reconstructs and executes
        the inherited capability on unfamiliar tasks with zero discovery context."""
        em = run_emergence_and_live_succession_experiment()
        with tempfile.TemporaryDirectory() as sub_dir:
            payload_file = Path(sub_dir) / "transfer_input.json"
            payload_file.write_text(json.dumps({
                "strategy": em["inherited_capability"]["capability_id"].replace("_balancer", "").replace("coupled_constraint_horizon_optimizer_v2", "coupled_constraint_horizon_optimizer_v2"),
                "tasks": UNFAMILIAR_HELD_OUT_TASKS,
            }), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json, sys; "
                        "from core.verified_succession import execute_capability_program, IndependentSuccessionEvaluator; "
                        "data = json.loads(open(sys.argv[1]).read()); "
                        "ev = IndependentSuccessionEvaluator(); "
                        "scores = [ev.score_task_execution(execute_capability_program({'strategy': data['strategy']}, t)) for t in data['tasks']]; "
                        "print(json.dumps({'feasible': sum(1 for s in scores if s['feasible']), 'total': len(scores)}))"
                    ),
                    str(payload_file),
                ],
                cwd=str(Path(__file__).resolve().parent.parent),
                capture_output=True,
                text=True,
                check=True,
            )
            out = json.loads(proc.stdout.strip())
            self.assertEqual(out["feasible"], 4)
            self.assertEqual(out["total"], 4)


if __name__ == "__main__":
    unittest.main()
