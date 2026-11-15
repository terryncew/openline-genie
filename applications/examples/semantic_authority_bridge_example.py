#!/usr/bin/env python3
"""Reproducible end-to-end example: OpenLine Semantic Authority Bridge.

Run from inside ``applications/``:

    python3 examples/semantic_authority_bridge_example.py

What it shows, using the shipped Energy Commons ontology fixture
(``examples/ontologies/energy_commons_ossie.yaml``, Apache Ossie YAML):

1. A decision is bound to the exact meaning it relied on: a certified
   term, its SQL expression, the default join edge, and an evidence
   document. The binding is a canonical digest, not the raw text.
2. A harmless edit (a new synonym on the term) does NOT reopen anything.
3. A consequential edit (the export rate in the SQL expression changes
   from $0.065 to $0.018) reopens ONLY the decision that depended on it;
   the unrelated pump decision stays CURRENT.
4. A consequential action under the reopened decision is REFUSED
   (``StaleSemanticAuthorityRefused``); the same action under the
   unaffected decision still executes. No global STOP is involved.
5. Re-evaluating the reopened decision under the new meaning authorizes
   it again, and the case history exports and verifies.

Everything runs locally, with no network and no paid service. The
certification signatures in this example are self-attestations: the
bridge generates a fresh ephemeral Ed25519 steward key per instance
(see ``SEMANTIC_AUTHORITY_BRIDGE.md``). They prove the record was not
altered after signing, not that an outside authority endorsed it.

Exit code 0 means every check above behaved as described.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from core.semantic_authority_bridge import (  # noqa: E402
    SemanticAuthorityBridge,
    SemanticOntologyModel,
    StaleSemanticAuthorityRefused,
)


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        raise SystemExit(f"example failed at: {label}")


def main() -> int:
    fixture = HERE / "examples" / "ontologies" / "energy_commons_ossie.yaml"
    bridge = SemanticAuthorityBridge()
    model = bridge.import_ontology(
        fixture.read_text(encoding="utf-8"),
        auto_sign_certified_with_pinned_steward=True,
    )
    print(f"Imported {model.model_name} ({len(model.terms)} terms, "
          f"{len(model.sql_attributes)} SQL attributes, "
          f"{len(model.relationships)} relationships)")

    bridge.register_evidence_document(
        "DOC-EXAMPLE-TARIFF-2026",
        "Cooperative tariff schedule: $0.39 peak, $0.27 off-peak, "
        "$0.065 export (fictional example rates).",
    )

    bridge.bind_decision(
        project_id="PROJ-EXAMPLE-ENERGY",
        decision_id="DEC-EXAMPLE-TARIFF",
        conclusion_summary="Cooperative Option 3 is cheapest under the retail tariff.",
        proposed_action="Sign the EPC contract for Option 3.",
        bound_term_ids=["TERM_NET_AVOIDED_ELECTRICITY_COST"],
        bound_sql_attr_ids=["SQL_ATTR_AVOIDED_TOU_COST"],
        bound_join_edge_ids=["REL_METER_TO_SERVICE_TARIFF"],
        bound_evidence_doc_ids=["DOC-EXAMPLE-TARIFF-2026"],
    )
    bridge.bind_decision(
        project_id="PROJ-EXAMPLE-ENERGY",
        decision_id="DEC-EXAMPLE-PUMP",
        conclusion_summary="Booster pump schedule meets the cistern demand.",
        proposed_action="Run the booster pump on the approved schedule.",
        bound_term_ids=["TERM_PUMP_HYDRAULIC_HEAD"],
        bound_sql_attr_ids=["SQL_ATTR_PUMP_HEAD"],
    )
    print("Bound 2 decisions to their semantic definitions.")

    # 1. Harmless edit: a new synonym on the tariff term.
    harmless = copy.deepcopy(model.export_ossie_dict())
    for term in harmless["datasets"][0]["terms"]:
        if term["id"] == "TERM_NET_AVOIDED_ELECTRICITY_COST":
            term["synonyms"].append("coop_avoided_rate")
    report = bridge.detect_and_apply_semantic_changes(
        SemanticOntologyModel(harmless), project_id="PROJ-EXAMPLE-ENERGY"
    )
    check("harmless synonym edit reopens nothing",
          len(report["affected_decisions"]) == 0)

    # 2. Consequential edit: the export rate in the SQL expression.
    changed = copy.deepcopy(model.export_ossie_dict())
    for attr in changed["datasets"][0]["sql_attributes"]:
        if attr["id"] == "SQL_ATTR_AVOIDED_TOU_COST":
            attr["expression"] = attr["expression"].replace("0.065", "0.018")
    changed_model = SemanticOntologyModel(changed)
    report = bridge.detect_and_apply_semantic_changes(
        changed_model, project_id="PROJ-EXAMPLE-ENERGY"
    )
    affected = [d["decision_id"] for d in report["affected_decisions"]]
    check("formula change reopens only the tariff decision",
          affected == ["DEC-EXAMPLE-TARIFF"])
    check("pump decision stays CURRENT",
          "DEC-EXAMPLE-PUMP" in
          [d["decision_id"] for d in report["unaffected_decisions"]])

    # 3. Stale authority is refused; unaffected authority still executes.
    try:
        bridge.attempt_consequential_action(
            project_id="PROJ-EXAMPLE-ENERGY",
            decision_id="DEC-EXAMPLE-TARIFF",
            task_id="TASK-EXAMPLE-EPC-SIGN",
            action_note="Sign the EPC contract.",
        )
        check("stale EPC signing is refused", False)
    except StaleSemanticAuthorityRefused:
        check("stale EPC signing is refused", True)
    res = bridge.attempt_consequential_action(
        project_id="PROJ-EXAMPLE-ENERGY",
        decision_id="DEC-EXAMPLE-PUMP",
        task_id="TASK-EXAMPLE-PUMP-RUN",
        action_note="Run the booster pump schedule.",
    )
    check("unaffected pump action executes",
          res["status"] == "EXECUTED_WITH_CURRENT_AUTHORITY")

    # 4. Re-evaluate the reopened decision under the new meaning. The
    # changed expression invalidated the old certification attestation,
    # so the steward must first re-certify the revised definition (here
    # by re-importing with auto-sign); only then can the decision be
    # re-authorized. That is the point: a changed meaning cannot be
    # re-authorized on the old attestation.
    bridge.import_ontology(changed, auto_sign_certified_with_pinned_steward=True)
    bridge.reevaluate_and_authorize(
        project_id="PROJ-EXAMPLE-ENERGY",
        decision_id="DEC-EXAMPLE-TARIFF",
        disposition="AUTHORIZE_CONTINUATION",
        updated_conclusion_summary=(
            "Cooperative Option 3 remains cheapest at the $0.018 export rate."
        ),
        authorization_note="Re-evaluated after the export-rate revision.",
    )
    res = bridge.attempt_consequential_action(
        project_id="PROJ-EXAMPLE-ENERGY",
        decision_id="DEC-EXAMPLE-TARIFF",
        task_id="TASK-EXAMPLE-EPC-SIGN-2",
        action_note="Sign the EPC contract after re-evaluation.",
    )
    check("re-authorized tariff action executes after re-evaluation",
          res["status"] == "EXECUTED_WITH_CURRENT_AUTHORITY")

    # 5. The case history exports and verifies.
    packet = bridge.export_verifiable_case_history(
        project_id="PROJ-EXAMPLE-ENERGY"
    )
    verdict = SemanticAuthorityBridge.verify_imported_case_history(packet)
    check("exported case history verifies", bool(verdict.get("valid")))

    print("Example complete: selective recall, stale-authority refusal, "
          "and re-authorization all behaved as documented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
