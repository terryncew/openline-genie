#!/usr/bin/env python3
"""Independent Evaluation Boundary Contract for OpenLine Genie v1.2.0-rc3
(`core/independent_evaluation_boundary.py`).

Closes Blocker 2.A (Holdout Contamination & Evaluation Authority Separation):
1. Candidate Runtime Has Zero Evaluation Authority:
   - The candidate (`openline-genie`) never controls unseen evaluation tasks, expected
     outcomes, or acceptance verdicts (`CANDIDATE_HAS_EVALUATION_AUTHORITY = False`).
2. Strict Oracle & Private-Vault Isolation:
   - Rejects any task input containing evaluator-private oracle keys (`expected_html`,
     `expected_defects`, `expected_outcome`, `ground_truth`, `evaluator_secret`,
     `private_holdout_verdict`, `evaluator_signing_key`, `acceptance_decision`,
     `private_eval_vault`).
   - Refuses access to any path inside `GENIE_PRIVATE_EVALUATOR_VAULT` if configured
     in the environment (`PermissionError`).
3. Stateless Candidate Submission Entrypoint for External Evaluators (e.g., GPT-6):
   - External evaluators invoke `submit_candidate_repair_for_external_evaluation(task_input)`
     (or `python3 -m core.independent_evaluation_boundary --task-json <path>`) to obtain
     the candidate's proposed HTML repair, diagnosed fault classes, and precheck telemetry,
     and then judge the output independently outside Argon's candidate runtime.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from core.rgpo_obligation_gate import RGPOPolicyViolation, enforce_zero_oracle
from core.visual_intelligence_harness import (
    CANDIDATE_HAS_EVALUATION_AUTHORITY,
    check_candidate_visual_and_functional_invariants,
    diagnose_visual_causal_bottleneck,
    observe_rendered_artifact,
    repair_visual_artifact,
)

FORBIDDEN_EVALUATOR_ORACLE_KEYS = frozenset({
    "expected_html",
    "expected_defects",
    "expected_outcome",
    "expected_score",
    "ground_truth",
    "ground_truth_html",
    "evaluator_secret",
    "private_holdout_verdict",
    "evaluator_signing_key",
    "evaluator_private_key",
    "acceptance_decision",
    "private_eval_vault",
    "holdout_answer_key",
    "force_accept",
    "bypass_receiver",
})


def _enforce_evaluator_boundary(payload: Any) -> None:
    """Recursively verifies that no evaluator-private oracle or answer key is exposed to the candidate."""
    try:
        enforce_zero_oracle(payload)
    except RGPOPolicyViolation as exc:
        raise PermissionError(
            f"INDEPENDENT_EVALUATOR_BOUNDARY_VIOLATION:{exc}"
        ) from exc
    if isinstance(payload, Mapping):
        for k, v in payload.items():
            key_low = str(k).strip().lower()
            if key_low in FORBIDDEN_EVALUATOR_ORACLE_KEYS:
                raise PermissionError(
                    f"INDEPENDENT_EVALUATOR_BOUNDARY_VIOLATION:forbidden_oracle_key:{k}"
                )
            _enforce_evaluator_boundary(v)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            _enforce_evaluator_boundary(item)


def assert_not_inside_private_evaluator_vault(target_path: str | Path) -> None:
    """Blocks the candidate from reading or modifying any path inside `GENIE_PRIVATE_EVALUATOR_VAULT`."""
    vault_env = os.environ.get("GENIE_PRIVATE_EVALUATOR_VAULT", "").strip()
    if not vault_env:
        return
    vault_resolved = Path(vault_env).resolve()
    target_resolved = Path(target_path).resolve()
    if target_resolved == vault_resolved or vault_resolved in target_resolved.parents:
        raise PermissionError(
            f"INDEPENDENT_EVALUATOR_BOUNDARY_VIOLATION:candidate_cannot_access_private_vault:{target_resolved}"
        )


def submit_candidate_repair_for_external_evaluation(
    task_input: Mapping[str, Any],
    *,
    browser_page: Any | None = None,
    artifact_output_dir: Path | None = None,
) -> dict[str, Any]:
    """Stateless candidate entrypoint for an external independent evaluator (such as GPT-6).

    Accepts a raw task specification (`task_id`, `initial_html`, `artifact_family`, `viewport`,
    `accepted_state`), verifies zero oracle contamination, executes candidate visual perception,
    diagnosis, and repair, and returns a `CandidateRepairSubmission` without claiming
    independent acceptance.
    """
    if not isinstance(task_input, Mapping):
        raise ValueError("task_input must be a mapping")
    _enforce_evaluator_boundary(task_input)

    if artifact_output_dir is not None:
        assert_not_inside_private_evaluator_vault(artifact_output_dir)

    task_id = str(task_input.get("task_id") or "EXTERNAL-TASK")
    initial_html = task_input.get("initial_html")
    if not isinstance(initial_html, str) or not initial_html.strip():
        raise ValueError("task_input['initial_html'] must be a non-empty HTML string")
    family = str(task_input.get("artifact_family") or task_input.get("family") or "responsive_ui")
    viewport = task_input.get("viewport") or {"width": 390, "height": 844}
    accepted_state = task_input.get("accepted_state") or {}

    shot_before = (artifact_output_dir / f"{task_id}_before.png") if artifact_output_dir else None
    shot_after = (artifact_output_dir / f"{task_id}_after.png") if artifact_output_dir else None

    obs_before = observe_rendered_artifact(
        f"{task_id}:before",
        initial_html,
        artifact_family=family,
        viewport=viewport,
        accepted_state=accepted_state,
        screenshot_path=shot_before,
        browser_page=browser_page,
    )
    if obs_before.inspection_failed:
        return {
            "schema": "openline.genie.candidate_repair_submission.v1",
            "task_id": task_id,
            "artifact_family": family,
            "status": "CANDIDATE_INSPECTION_FAILED_REJECTED",
            "candidate_has_evaluation_authority": CANDIDATE_HAS_EVALUATION_AUTHORITY,
            "candidate_self_check_passed": False,
            "independently_accepted": False,
            "promoted_to_accepted_state": False,
            "inspection_errors": list(obs_before.inspection_errors),
            "initial_html_sha256": obs_before.html_sha256,
            "proposed_html": initial_html,
            "proposed_html_sha256": obs_before.html_sha256,
        }

    diagnosis = diagnose_visual_causal_bottleneck(
        obs_before,
        accepted_state=accepted_state,
        mode="D_HYBRID_EMERGENCE",
    )
    proposed_html = (
        repair_visual_artifact(initial_html, diagnosis, accepted_state=accepted_state)
        if diagnosis["bottleneck_identified"]
        else initial_html
    )
    obs_after = observe_rendered_artifact(
        f"{task_id}:after",
        proposed_html,
        artifact_family=family,
        viewport=viewport,
        accepted_state=accepted_state,
        screenshot_path=shot_after,
        browser_page=browser_page,
    )
    precheck = check_candidate_visual_and_functional_invariants(
        obs_before,
        obs_after,
        accepted_state=accepted_state,
    )

    return {
        "schema": "openline.genie.candidate_repair_submission.v1",
        "task_id": task_id,
        "artifact_family": family,
        "status": (
            "CANDIDATE_SUBMISSION_AWAITING_INDEPENDENT_EVALUATOR"
            if precheck["candidate_self_check_passed"]
            else "CANDIDATE_PRECHECK_FAILED_DO_NOT_ACCEPT"
        ),
        "candidate_has_evaluation_authority": CANDIDATE_HAS_EVALUATION_AUTHORITY,
        "candidate_self_check_passed": precheck["candidate_self_check_passed"],
        "independently_accepted": False,
        "independent_acceptance_status": precheck["independent_acceptance_status"],
        "promoted_to_accepted_state": False,
        "rejection_reason": precheck["rejection_reason"],
        "diagnosed_faults": [d["fault_class"] for d in diagnosis["defects"]],
        "initial_html_sha256": obs_before.html_sha256,
        "proposed_html": proposed_html,
        "proposed_html_sha256": obs_after.html_sha256,
        "before_screenshot_sha256": obs_before.screenshot_sha256,
        "after_screenshot_sha256": obs_after.screenshot_sha256,
        "observed_via_real_browser": obs_after.observed_via_real_browser,
        "precheck_metrics": precheck,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stateless candidate repair submission CLI for external independent evaluators."
    )
    parser.add_argument("--task-json", type=Path, required=True, help="Path to external task JSON input")
    parser.add_argument("--output-json", type=Path, default=None, help="Optional path to write submission JSON")
    parser.add_argument("--artifact-dir", type=Path, default=None, help="Optional directory for PNG screenshots")
    args = parser.parse_args()

    assert_not_inside_private_evaluator_vault(args.task_json)
    task_data = json.loads(args.task_json.read_text(encoding="utf-8"))
    submission = submit_candidate_repair_for_external_evaluation(
        task_data,
        artifact_output_dir=args.artifact_dir,
    )
    out_str = json.dumps(submission, indent=2, sort_keys=True) + "\n"
    if args.output_json is not None:
        assert_not_inside_private_evaluator_vault(args.output_json)
        args.output_json.write_text(out_str, encoding="utf-8")
    else:
        print(out_str, end="")
    return 0 if submission["candidate_self_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
