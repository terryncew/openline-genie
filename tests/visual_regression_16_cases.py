#!/usr/bin/env python3
"""Regression Test Fixtures for Visual-Geometric Counterfactual Perception & Repair
(`tests/visual_regression_16_cases.py`).

IMPORTANT EPISTEMIC & EVALUATION BOUNDARY DISCLOSURE (`Blocker 2.A Closed`):
- The 16 fixtures in this file (`REG-01` .. `REG-16`, formerly `DEV-01..08` and `HOLD-01..08`)
  were previously embedded in candidate source (`core/visual_intelligence_harness.py`).
- Per RC3 Release Closure Section 2.A:
  1. All 16 cases have been removed from `core/` and moved into `tests/` as known
     regression tests (`REGRESSION_SUITE_ONLY = True`, `IS_SEALED_HOLDOUT = False`,
     `CLAIMS_UNSEEN_GENERALIZATION = False`).
  2. Neither these 16 regression fixtures nor any candidate-side check is claimed as
     proof of unseen generalization or independent acceptance.
  3. Fresh unseen tasks, expected outcomes, and final acceptance decisions are controlled
     exclusively by the external independent evaluator (GPT-6) outside Argon's runtime.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import tempfile
import time
from typing import Any

import numpy as np

from core.independent_evaluation_boundary import (
    FORBIDDEN_EVALUATOR_ORACLE_KEYS,
    submit_candidate_repair_for_external_evaluation,
)
from core.portable_verified_inheritance import (
    WorkerBPortableInheritanceRuntime,
    qualify_and_export_visual_capsule_worker_a,
)
from core.rgpo_obligation_gate import RGPOPolicyViolation, enforce_zero_oracle
from core.visual_intelligence_harness import (
    CANDIDATE_HAS_EVALUATION_AUTHORITY,
    EVIDENCE_CLASS,
    VHarnessAtomicOperators,
    check_candidate_visual_and_functional_invariants,
    compute_functional_and_geometric_scores,
    diagnose_visual_causal_bottleneck,
    observe_rendered_artifact,
    probe_interactive_hit_topology,
    probe_spatial_and_svg_geometry,
    probe_state_view_coherence,
    repair_visual_artifact,
)

REGRESSION_SUITE_ONLY = True
IS_SEALED_HOLDOUT = False
CLAIMS_UNSEEN_GENERALIZATION = False


@dataclass(frozen=True)
class VisualRegressionCase:
    case_id: str
    legacy_id: str
    split: str  # Always "regression_fixture" (never "sealed_holdout")
    family: str  # "responsive_ui" | "svg_diagram" | "floor_plan" | "stateful_app"
    title: str
    defect_archetype: str
    initial_html: str
    accepted_state: dict[str, Any] = field(default_factory=dict)

    @property
    def task_id(self) -> str:
        return self.case_id


def build_regression_16_case_suite() -> list[VisualRegressionCase]:
    """Returns the 16 regression test fixtures (strictly classified as `regression_fixture`)."""
    return [
        VisualRegressionCase(
            case_id="REG-01-MOBILE-HEADER-OCCLUSION",
            legacy_id="DEV-01-MOBILE-HEADER-OCCLUSION",
            split="regression_fixture",
            family="responsive_ui",
            title="Solar Microgrid Dispatch Console (390px Mobile)",
            defect_archetype="structurally_valid_visually_defective_fixed_header_overlap",
            initial_html=(
                "<!DOCTYPE html><html><head><title>Solar Dispatch</title></head><body>"
                '<header id="sticky-nav" style="position:fixed;left:0px;top:0px;width:390px;height:68px;z-index:50;opacity:1.0;">Microgrid Header</header>'
                '<input id="kw-input" type="number" value="15" style="left:20px;top:90px;width:160px;height:36px;" />'
                '<button id="btn-dispatch" type="button" onclick="window.__handleAction && window.__handleAction()" '
                'style="left:24px;top:18px;width:140px;height:38px;">Add Dispatch</button>'
                '<div id="records-list"></div></body></html>'
            ),
        ),
        VisualRegressionCase(
            case_id="REG-02-ANCESTOR-OVERFLOW-CLIP",
            legacy_id="DEV-02-ANCESTOR-OVERFLOW-CLIP",
            split="regression_fixture",
            family="responsive_ui",
            title="Water Quality Telemetry Action Card",
            defect_archetype="structurally_valid_visually_defective_overflow_clipping",
            initial_html=(
                "<!DOCTYPE html><html><head><title>Water Telemetry</title></head><body>"
                '<div id="card-wrap" data-role="clip-wrapper" style="left:0px;top:0px;width:300px;height:120px;overflow:hidden;">'
                '<input id="ntu-input" type="number" value="4.2" style="left:16px;top:24px;width:120px;height:34px;" />'
                '<button id="btn-save-ntu" type="button" onclick="window.__handleAction && window.__handleAction()" '
                'style="left:320px;top:24px;width:140px;height:36px;">Save Reading</button>'
                "</div></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-03-SVG-VIEWBOX-TRUNCATION",
            legacy_id="DEV-03-SVG-VIEWBOX-TRUNCATION",
            split="regression_fixture",
            family="svg_diagram",
            title="Ed25519 Receipt Verification Topology SVG",
            defect_archetype="structurally_valid_visually_defective_svg_truncation",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<svg viewBox="0 0 320 180" width="320" height="180">'
                '<rect id="node-proposer" data-role="node" x="20" y="40" width="110" height="60" />'
                '<text id="label-proposer" x="30" y="70">Proposer</text>'
                '<rect id="node-verifier" data-role="node" x="260" y="40" width="130" height="60" />'
                '<text id="label-verifier" x="270" y="70">Receiver Gate</text>'
                "</svg></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-04-DIAGRAM-TEXT-NODE-COLLISION",
            legacy_id="DEV-04-DIAGRAM-TEXT-NODE-COLLISION",
            split="regression_fixture",
            family="svg_diagram",
            title="Closed-Loop Membrane Pressure Schematic",
            defect_archetype="structurally_valid_visually_defective_label_collision",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<svg viewBox="0 0 420 220" width="420" height="220">'
                '<rect id="node-a" data-role="node" x="24" y="32" width="120" height="64" />'
                '<rect id="node-b" data-role="node" x="90" y="32" width="120" height="64" />'
                '<text id="label-a" data-collide="true" x="95" y="64">RO Feed Pump 140 PSI</text>'
                "</svg></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-05-FLOORPLAN-OVERLAP-AND-LANDLOCK",
            legacy_id="DEV-05-FLOORPLAN-OVERLAP-AND-LANDLOCK",
            split="regression_fixture",
            family="floor_plan",
            title="Community Cold-Chain & Desalination Hub Floor Plan",
            defect_archetype="geometric_overlap_and_missing_egress",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<svg viewBox="0 0 460 300" width="460" height="300">'
                '<rect id="fp-main" data-role="footprint" x="20" y="20" width="400" height="240" />'
                '<rect id="room-1" data-role="room" data-label="Primary Lab" x="20" y="20" width="240" height="240" />'
                '<rect id="room-2" data-role="room" data-label="Control Bay" x="180" y="20" width="240" height="120" />'
                '<rect id="room-3" data-role="room" data-label="Cold Storage" x="220" y="140" width="200" height="120" />'
                "</svg></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-06-SANDBOX-NATIVE-SUBMIT-TRAP",
            legacy_id="DEV-06-SANDBOX-NATIVE-SUBMIT-TRAP",
            split="regression_fixture",
            family="stateful_app",
            title="Neighborhood Tool Library Checkout Ledger",
            defect_archetype="visually_plausible_functionally_broken_native_submit",
            initial_html=(
                "<!DOCTYPE html><html><body><form>"
                '<input id="tool-name" type="text" value="Torque Wrench" style="left:20px;top:24px;width:180px;height:36px;" />'
                '<button id="btn-checkout" type="submit" style="left:210px;top:24px;width:130px;height:36px;">Add Checkout</button>'
                "</form><div id='records-list'></div></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-07-STATE-VIEW-DEFAULT-DESYNC",
            legacy_id="DEV-07-STATE-VIEW-DEFAULT-DESYNC",
            split="regression_fixture",
            family="stateful_app",
            title="Cooperative Tariff Assumption Editor",
            defect_archetype="visually_plausible_functionally_broken_stale_defaults",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<input id="energy-tariff" data-bind-assumption="offpeak_tariff_usd_kwh" type="number" value="0.27" style="left:20px;top:24px;width:160px;height:36px;" />'
                '<input id="energy-households" data-bind-assumption="household_units" type="number" value="24" style="left:20px;top:72px;width:160px;height:36px;" />'
                '<button id="btn-stage" type="button" onclick="window.__handleAction && window.__handleAction()" style="left:20px;top:124px;width:150px;height:36px;">Save Plan</button>'
                "</body></html>"
            ),
            accepted_state={"offpeak_tariff_usd_kwh": 0.32, "household_units": 44},
        ),
        VisualRegressionCase(
            case_id="REG-08-OFFLINE-CDN-CHART-CRASH",
            legacy_id="DEV-08-OFFLINE-CDN-CHART-CRASH",
            split="regression_fixture",
            family="stateful_app",
            title="Sim2Real Torque Telemetry Monitor",
            defect_archetype="visually_plausible_offline_cdn_crash",
            initial_html=(
                "<!DOCTYPE html><html><head>"
                '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1"></script>'
                "</head><body>"
                '<canvas id="telemetry-chart" width="320" height="160"></canvas>'
                '<input id="gain-input" type="number" value="0.95" style="left:20px;top:180px;width:140px;height:34px;" />'
                '<button id="btn-apply-gain" type="button" onclick="new Chart(document.getElementById(\'telemetry-chart\'), {})" style="left:170px;top:180px;width:140px;height:34px;">Apply Gain</button>'
                "</body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-09-TRANSPARENT-OVERLAY-INTERCEPT",
            legacy_id="HOLD-01-TRANSPARENT-OVERLAY-INTERCEPT",
            split="regression_fixture",
            family="responsive_ui",
            title="Emergency Valve Override Panel",
            defect_archetype="visually_plausible_transparent_hit_blocker",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<div id="ghost-shield" style="position:fixed;left:0px;top:0px;width:390px;height:844px;opacity:0.0;pointer-events:auto;z-index:99;"></div>'
                '<input id="valve-psi" type="number" value="125" style="left:24px;top:40px;width:160px;height:36px;" />'
                '<button id="btn-trip-valve" type="button" onclick="window.__handleAction && window.__handleAction()" style="left:24px;top:96px;width:160px;height:38px;">Create Override</button>'
                "</body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-10-MOBILE-SIDEBAR-CLIP",
            legacy_id="HOLD-02-MOBILE-SIDEBAR-CLIP",
            split="regression_fixture",
            family="responsive_ui",
            title="Civic Setback Covenant Inspector (390px)",
            defect_archetype="structurally_valid_visually_defective_viewport_overflow",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<div id="covenant-row" data-role="clip-wrapper" style="left:0px;top:0px;width:360px;height:110px;overflow:clip;">'
                '<input id="setback-m" type="number" value="100" style="left:16px;top:24px;width:140px;height:36px;" />'
                '<button id="btn-verify-setback" type="button" onclick="window.__handleAction && window.__handleAction()" style="left:410px;top:24px;width:150px;height:36px;">Add Covenant</button>'
                "</div></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-11-SVG-BUSBAR-TRUNCATION",
            legacy_id="HOLD-03-SVG-BUSBAR-TRUNCATION",
            split="regression_fixture",
            family="svg_diagram",
            title="Three-Phase Inverter Busbar Topology SVG",
            defect_archetype="structurally_valid_visually_defective_svg_truncation",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<svg viewBox="0 0 280 160" width="280" height="160">'
                '<rect id="bus-a" data-role="node" x="16" y="24" width="100" height="56" />'
                '<rect id="bus-b" data-role="node" x="230" y="110" width="120" height="75" />'
                '<text id="label-bus-b" x="240" y="145">480V Tie Breaker</text>'
                "</svg></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-12-DAG-LINE-LABEL-COLLISION",
            legacy_id="HOLD-04-DAG-LINE-LABEL-COLLISION",
            split="regression_fixture",
            family="svg_diagram",
            title="Decision Recall DNF Support Graph",
            defect_archetype="structurally_valid_visually_defective_label_collision",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<svg viewBox="0 0 440 200" width="440" height="200">'
                '<rect id="node-a" data-role="node" x="30" y="36" width="130" height="60" />'
                '<rect id="node-b" data-role="node" x="105" y="36" width="130" height="60" />'
                '<text id="label-dnf" data-collide="true" x="110" y="68">REVOKED WITNESS</text>'
                "</svg></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-13-FLOORPLAN-NONCONSERVED-AREA",
            legacy_id="HOLD-05-FLOORPLAN-NONCONSERVED-AREA",
            split="regression_fixture",
            family="floor_plan",
            title="Municipal Biosand & Chlorine Contact Clinic Plan",
            defect_archetype="geometric_area_mismatch_and_narrow_corridor",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<svg viewBox="0 0 460 300" width="460" height="300">'
                '<rect id="fp-clinic" data-role="footprint" x="20" y="20" width="400" height="240" />'
                '<rect id="room-1" data-role="room" data-label="Intake Hall" x="20" y="20" width="150" height="240" />'
                '<rect id="room-2" data-role="room" data-label="Narrow Choke" x="170" y="20" width="24" height="120" />'
                '<rect id="room-3" data-role="room" data-label="Contact Basin" x="220" y="140" width="160" height="100" />'
                "</svg></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-14-DECORATIVE-NOOP-BUTTON-TRAP",
            legacy_id="HOLD-06-DECORATIVE-NOOP-BUTTON-TRAP",
            split="regression_fixture",
            family="stateful_app",
            title="HOA Dispute Mediation Evidence Log",
            defect_archetype="visually_plausible_functionally_broken_noop_button",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<input id="exhibit-title" type="text" value="Roof Drainage Photo" style="left:24px;top:28px;width:180px;height:36px;" />'
                '<button id="btn-add-exhibit" type="button" onclick="void(0)" style="left:216px;top:28px;width:130px;height:36px;">Add Exhibit</button>'
                "<div id='records-list'></div></body></html>"
            ),
        ),
        VisualRegressionCase(
            case_id="REG-15-ADVOCATE-DATE-DESYNC-TRAP",
            legacy_id="HOLD-07-ADVOCATE-DATE-DESYNC-TRAP",
            split="regression_fixture",
            family="stateful_app",
            title="Public Benefits Aid-Pending Deadline Calculator",
            defect_archetype="visually_plausible_functionally_broken_stale_defaults",
            initial_html=(
                "<!DOCTYPE html><html><body>"
                '<input id="advocate-notice-date" data-bind-assumption="notice_date" type="text" value="2026-11-01" style="left:24px;top:24px;width:160px;height:36px;" />'
                '<input id="advocate-receipt-date" data-bind-assumption="receipt_date" type="text" value="2026-11-06" style="left:24px;top:72px;width:160px;height:36px;" />'
                '<button id="btn-stage-adv" type="button" onclick="window.__handleAction && window.__handleAction()" style="left:24px;top:124px;width:150px;height:36px;">Save Dates</button>'
                "</body></html>"
            ),
            accepted_state={"notice_date": "2026-11-03", "receipt_date": "2026-11-09"},
        ),
        VisualRegressionCase(
            case_id="REG-16-COMPOUND-VISUAL-AND-STATE-TRAP",
            legacy_id="HOLD-08-COMPOUND-VISUAL-AND-STATE-TRAP",
            split="regression_fixture",
            family="stateful_app",
            title="Coupled Microgrid & SVG Busbar Workbench",
            defect_archetype="compound_fixed_header_svg_clip_and_state_desync",
            initial_html=(
                "<!DOCTYPE html><html><head>"
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter" />'
                "</head><body>"
                '<header id="top-lock" style="position:fixed;left:0px;top:0px;width:390px;height:72px;z-index:40;opacity:1.0;">Locked Header</header>'
                '<input id="civic-budget" data-bind-assumption="max_10yr_lifecycle_budget_musd" type="number" value="2.15" style="left:24px;top:90px;width:150px;height:36px;" />'
                '<button id="btn-save-civic" type="submit" style="left:24px;top:20px;width:140px;height:36px;">Save Budget</button>'
                '<svg viewBox="0 0 240 120" width="240" height="120">'
                '<rect id="node-main" data-role="node" x="180" y="30" width="120" height="60" />'
                "</svg></body></html>"
            ),
            accepted_state={"max_10yr_lifecycle_budget_musd": 1.85},
        ),
    ]


def run_regression_16_case_comparison(
    artifact_output_dir: Path | None = None,
) -> dict[str, Any]:
    """Executes the 16 regression cases across modes A/B/C/D strictly as a regression suite
    (not a generalization claim; `independently_accepted` is always `False`).
    """
    cases = build_regression_16_case_suite()
    arms = (
        ("A_EXISTING_GENIE", "A — Existing Genie (DOM smoke & external URL check)"),
        ("B_CONVENTIONAL", "B — Conventional Inspection (DOM, accessibility & bounding-box check)"),
        ("C_EXTERNAL_VISUAL_VHARNESS", "C — External Visual Intelligence (VHarness 5 atomic operators)"),
        ("D_HYBRID_EMERGENCE", "D — Hybrid Emergence (VGC-CDRI: visual + counterfactual probes)"),
    )

    arm_summaries: dict[str, Any] = {}
    for arm_code, arm_label in arms:
        t0 = time.perf_counter_ns()
        passed_precheck = 0
        total_defects_corrected = 0
        false_self_passes = 0
        total_retries = 0
        total_compute_units = 0
        func_scores: list[float] = []
        geom_scores: list[float] = []
        case_results: list[dict[str, Any]] = []

        for case in cases:
            shot_before = (
                artifact_output_dir / f"{case.case_id}_{arm_code}_before.png"
                if artifact_output_dir and arm_code == "D_HYBRID_EMERGENCE"
                else None
            )
            obs_before = observe_rendered_artifact(
                case.case_id,
                case.initial_html,
                artifact_family=case.family,
                accepted_state=case.accepted_state,
                screenshot_path=shot_before,
            )
            diag = diagnose_visual_causal_bottleneck(
                obs_before,
                accepted_state=case.accepted_state,
                mode=arm_code,
            )

            candidate_html = case.initial_html
            retries_used = 0
            if diag["bottleneck_identified"]:
                retries_used = 1
                candidate_html = repair_visual_artifact(
                    case.initial_html,
                    diag,
                    accepted_state=case.accepted_state,
                )

            compute_units = 1 + retries_used + (1 if arm_code in ("C_EXTERNAL_VISUAL_VHARNESS", "D_HYBRID_EMERGENCE") else 0)
            total_compute_units += compute_units
            total_retries += retries_used

            shot_after = (
                artifact_output_dir / f"{case.case_id}_{arm_code}_after.png"
                if artifact_output_dir and arm_code == "D_HYBRID_EMERGENCE"
                else None
            )
            obs_after = observe_rendered_artifact(
                case.case_id,
                candidate_html,
                artifact_family=case.family,
                accepted_state=case.accepted_state,
                screenshot_path=shot_after,
            )

            post_diag_self = diagnose_visual_causal_bottleneck(
                obs_after,
                accepted_state=case.accepted_state,
                mode=arm_code,
            )
            arm_self_passed = not post_diag_self["bottleneck_identified"]

            precheck = check_candidate_visual_and_functional_invariants(
                obs_before,
                obs_after,
                accepted_state=case.accepted_state,
            )
            precheck_ok = precheck["candidate_self_check_passed"]

            if arm_self_passed and not precheck_ok:
                false_self_passes += 1

            defects_fixed = max(
                0,
                precheck["before"]["total_defects_remaining"]
                - precheck["after"]["total_defects_remaining"],
            )
            total_defects_corrected += defects_fixed
            func_scores.append(precheck["after"]["functional_score"])
            geom_scores.append(precheck["after"]["geometric_score"])
            if precheck_ok:
                passed_precheck += 1

            case_results.append({
                "case_id": case.case_id,
                "legacy_id": case.legacy_id,
                "split": case.split,
                "family": case.family,
                "arm": arm_code,
                "diagnosed_faults": [d["fault_class"] for d in diag["defects"]],
                "retries_used": retries_used,
                "compute_units": compute_units,
                "arm_self_passed": arm_self_passed,
                "candidate_self_check_passed": precheck_ok,
                "independently_accepted": False,
                "defects_before": precheck["before"]["total_defects_remaining"],
                "defects_after": precheck["after"]["total_defects_remaining"],
                "functional_score_after": precheck["after"]["functional_score"],
                "geometric_score_after": precheck["after"]["geometric_score"],
                "before_screenshot_sha256": obs_before.screenshot_sha256,
                "after_screenshot_sha256": obs_after.screenshot_sha256,
            })

        elapsed_ms = round((time.perf_counter_ns() - t0) / 1e6, 2)
        arm_summaries[arm_code] = {
            "label": arm_label,
            "regression_cases_passed_precheck": passed_precheck,
            "total_regression_cases": len(cases),
            "regression_pass_rate": round(passed_precheck / len(cases), 4),
            "total_compute_units": total_compute_units,
            "passed_cases_per_compute_unit": round(passed_precheck / max(1, total_compute_units), 4),
            "confirmed_defects_corrected": total_defects_corrected,
            "false_self_pass_count": false_self_passes,
            "mean_functional_accuracy": round(float(np.mean(func_scores)), 4),
            "mean_geometric_accuracy": round(float(np.mean(geom_scores)), 4),
            "elapsed_ms": elapsed_ms,
            "external_api_spend_usd": 0.0,
            "cases": case_results,
        }

    return {
        "suite_id": "ARGON-VISUAL-16-CASE-REGRESSION-SUITE",
        "regression_suite_only": REGRESSION_SUITE_ONLY,
        "is_sealed_holdout": IS_SEALED_HOLDOUT,
        "claims_unseen_generalization": CLAIMS_UNSEEN_GENERALIZATION,
        "candidate_has_evaluation_authority": CANDIDATE_HAS_EVALUATION_AUTHORITY,
        "evidence_class": EVIDENCE_CLASS,
        "arms": arm_summaries,
    }
