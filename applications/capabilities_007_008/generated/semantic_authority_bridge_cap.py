"""Generation 4 (G4) Inheritable Capability: `semantic_authority_bridge_cap.py`.

Provenance disclosure:
  - Authored by Argon engineering lead during ARGON — OPENLINE SEMANTIC AUTHORITY BREAKTHROUGH 001 (`AUTHORED_BY_ARGON_ENGINEER`).
  - Registered as `semantic-authority-bridge` in `capabilities_007_008/registry_g4_semantic.json`.
  - Enables any clean successor agent (Worker B) in an isolated workspace to inherit
    `SSB-CDIG` (Canonical Semantic Slice Closure & Harmless-vs-Consequential Diff Gate),
    inspect an unfamiliar Apache Ossie / NVIDIA Auto-Ontology model, detect semantic/join/
    certification changes (including Boundary Conditions A & B), reopen only affected
    decisions, refuse stale consequential execution, re-evaluate under revised semantics,
    and export an independently verifiable case history.
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.semantic_authority_bridge import (
    SemanticAuthorityBridge,
    StaleSemanticAuthorityRefused,
    simulate_nvidia_semantic_recompilation,
)


def run_semantic_authority_bridge(facts: dict[str, Any]) -> dict[str, Any]:
    """Executes the inherited `semantic-authority-bridge` capability on a structured task envelope."""
    bridge = SemanticAuthorityBridge()
    project_id = str(facts["project_id"])

    # 1. Register any immutable evidence documents
    for doc in facts.get("evidence_documents", []):
        bridge.register_evidence_document(
            doc_id=str(doc["doc_id"]),
            content=str(doc["content"]),
            role=str(doc.get("role", "GOVERNING_RULE_OR_EVIDENCE_RECORD")),
            version=int(doc.get("version", 1)),
        )

    # 2. Import initial ontology
    init_model = bridge.import_ontology(
        facts["initial_ontology"],
        auto_sign_certified_with_pinned_steward=bool(facts.get("auto_sign_initial", True)),
    )

    # 3. Bind project decisions
    bound_records = []
    for d in facts["decisions"]:
        b_res = bridge.bind_decision(
            project_id=project_id,
            decision_id=str(d["decision_id"]),
            conclusion_summary=str(d["conclusion_summary"]),
            proposed_action=str(d["proposed_action"]),
            bound_term_ids=list(d["bound_term_ids"]),
            bound_sql_attr_ids=d.get("bound_sql_attr_ids"),
            bound_join_edge_ids=d.get("bound_join_edge_ids"),
            bound_evidence_doc_ids=d.get("bound_evidence_doc_ids"),
            evidence_spans=d.get("evidence_spans"),
            initial_evaluation_result=d.get("initial_evaluation_result"),
        )
        bound_records.append(b_res)

    # 4. Obtain updated ontology (either explicit `updated_ontology` or `simulate_recompilation`)
    if facts.get("simulate_recompilation", False):
        updated_model = simulate_nvidia_semantic_recompilation(init_model)
        if facts.get("auto_sign_updated", True):
            bridge.sign_all_certified_terms_in_ontology(updated_model)
    else:
        updated_model = bridge.import_ontology(
            facts["updated_ontology"],
            auto_sign_certified_with_pinned_steward=bool(facts.get("auto_sign_updated", True)),
        )

    # 5. Detect semantic changes and reopen affected decisions
    drift_report = bridge.detect_and_apply_semantic_changes(updated_model, project_id=project_id)

    # 6. Attempt stale consequential execution on any affected decision (must fail closed!)
    stale_attempts = []
    for aff in drift_report["affected_decisions"]:
        did = aff["decision_id"]
        try:
            bridge.attempt_consequential_action(
                project_id=project_id,
                decision_id=did,
                task_id=f"stale-exec-{did}",
                action_note="Attempt execution under stale semantic basis",
            )
            stale_attempts.append({"decision_id": did, "refused": False})
        except StaleSemanticAuthorityRefused as exc:
            stale_attempts.append({"decision_id": did, "refused": True, "error": str(exc)})

    # 7. Re-evaluate and authorize continuation (or refusal) for affected decisions
    reauthorization_receipts = []
    reauth_specs = facts.get("reauthorizations", {})
    for aff in drift_report["affected_decisions"]:
        did = aff["decision_id"]
        spec = reauth_specs.get(did, {})
        disp = str(spec.get("disposition", "AUTHORIZE_CONTINUATION"))
        # If certification was revoked in updated_model, re-sign before authorizing continuation if requested
        if disp == "AUTHORIZE_CONTINUATION" and spec.get("recertify_terms_before_continue", False):
            for tid in bridge.decisions[(project_id, did)]["pinned_slice"].bound_term_ids:
                if tid in updated_model.terms:
                    updated_model.terms[tid]["certified"] = True
            bridge.sign_all_certified_terms_in_ontology(updated_model)
        rcpt = bridge.reevaluate_and_authorize(
            project_id=project_id,
            decision_id=did,
            disposition=disp,
            updated_conclusion_summary=spec.get("updated_conclusion_summary"),
            updated_proposed_action=spec.get("updated_proposed_action"),
            authorization_note=str(spec.get("authorization_note", "Authorized after semantic re-evaluation")),
            custom_reevaluation_result=spec.get("reevaluation_result"),
        )
        reauthorization_receipts.append(rcpt)

    # 8. Export & independently verify portable case history
    exported = bridge.export_verifiable_case_history(project_id=project_id)
    verified = SemanticAuthorityBridge.verify_imported_case_history(exported)

    return {
        "project_id": project_id,
        "bound_decisions": bound_records,
        "semantic_change_report": drift_report,
        "stale_execution_attempts": stale_attempts,
        "reauthorization_receipts": reauthorization_receipts,
        "exported_case_history_sha256": exported["case_history_sha256"],
        "independent_verification": verified,
    }
