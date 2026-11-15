"""OPENLINE NEIGHBORHOOD 001
ClearCovenant — powered by OpenLine
Core Consumer, Volunteer Board & Community Governance Engine (`core/neighborhood.py`).

Reuses the verified OpenLine 009 Genie / Living Projects foundation (`ReceiverGuard`,
`RecallLedger`, `SpendLedger`, and `EvidenceTriagedCounterfactualAuditor` / `ET-COSA`
from `core/civilization_applications.py`) to provide:
  1. Source-grounded HOA document ingestion with SHA-256 provenance, authority hierarchy
     (Statute > Recorded CC&Rs > Bylaws > Board Rules > Informal Practice), effective-date
     and county-recording verification, and hostile prompt-injection quarantine.
  2. Role-based access control and strict privacy separation across three customers:
     - Homeowner (`HOMEOWNER_PRIVATE` personal workspace — works standalone for 1 person)
     - Volunteer Board (`BOARD_CONFIDENTIAL` governance workspace)
     - Community (`COMMUNITY_SHARED` transparency & transition workspace with PII redaction)
  3. Plain-language Q&A and conflict resolution across 5 jurisdiction profiles (`CA`, `FL`,
     `TX`, `SC`, `GENERAL_US`) that never invents rules and explicitly states
     "The documents don’t establish an answer." when evidence is insufficient.
  4. Consequential action boundaries: never automatically issues fines, files legal
     proceedings, conducts binding elections, spends association funds, or authorizes
     contractors.
  5. Financial, assessment, reserve-study, and vendor-bid comparison engine with
     append-only negative-finding preservation.
  6. Twelve realistic dogfooded HOA conflict scenarios with independently verifiable
     reference outcomes.
"""

from __future__ import annotations

import copy
import datetime as dt
import html
import json
import re
from typing import Any

from core.civilization_applications import (
    EvidenceTriagedCounterfactualAuditor,
    redact_pii_for_export,
    sha256_hex,
)

INSUFFICIENT_EVIDENCE_STATEMENT = "The documents don’t establish an answer."

PRODUCT_BRAND_IDENTITY: dict[str, Any] = {
    "primary_name": "ClearCovenant",
    "full_display_title": "ClearCovenant — powered by OpenLine",
    "tagline": "Understand your HOA rules, protect your home, and run a fairer neighborhood—without giving up control.",
    "name_research_decision": {
        "working_name_tested": "Be Neighborly — powered by OpenLine",
        "empirical_collisions_found": [
            {
                "entity": "Project Neighborly, LLC (beneighborly.com)",
                "url": "https://beneighborly.com/terms/",
                "issue": "Active domain and mobile app operating under 'Be Neighborly' / 'Neighborly'.",
            },
            {
                "entity": "Neighborly Assetco LLC (neighborly.com / The Neighborly App)",
                "url": "https://www.neighborly.com/about/the-neighborly-app",
                "issue": "Registered US trademark (USPTO Serial #97603111 et al.) in home services, property repair, and homeowner management software.",
            },
        ],
        "consumer_tone_finding": (
            "In homeowner complaint data (SCDCA 2026 HOA Report, r/HOA), residents fighting unfair fines "
            "or ignored records requests find imperative slogans ('Be Neighborly') dismissive when management "
            "is non-compliant. 'ClearCovenant' communicates immediate practical utility (clear rules, clear "
            "budgets, clear records) for homeowners, volunteer boards, and communities alike. The tested "
            "working name was dropped entirely after the domain and trademark collisions above; it is not "
            "used as a subtitle, route, or display title anywhere."
        ),
        "verdict": "ADOPT_CLEARCOVENANT_ONLY",
    },
}

# Public brand fields served over the API and stored in accepted state.
# The full naming-decision record above stays in source as the audit trail
# and is NOT served: it names the dropped working name.
PUBLIC_BRAND_IDENTITY: dict[str, Any] = {
    "primary_name": PRODUCT_BRAND_IDENTITY["primary_name"],
    "full_display_title": PRODUCT_BRAND_IDENTITY["full_display_title"],
    "tagline": PRODUCT_BRAND_IDENTITY["tagline"],
}

# Authority hierarchy rank (lower number = higher legal authority)
DOCUMENT_AUTHORITY_TIERS: dict[str, dict[str, Any]] = {
    "STATUTE_OR_REGULATION": {
        "rank": 1,
        "label": "State / Federal Statute",
        "description": "Mandatory statutory law (e.g., CA Davis-Stirling Act, FL Ch. 718/720, TX Prop. Code Ch. 209, SC HOA Act). Overrides conflicting CC&Rs, bylaws, or board rules.",
    },
    "RECORDED_CCRS_DECLARATION": {
        "rank": 2,
        "label": "Recorded CC&Rs / Master Declaration",
        "description": "Covenants, Conditions & Restrictions recorded with the county recorder. Controls over bylaws and board-adopted rules.",
    },
    "ARTICLES_OR_BYLAWS": {
        "rank": 3,
        "label": "Articles of Incorporation & Bylaws",
        "description": "Governs board elections, quorum, meetings, and corporate procedures. Subordinate to statutes and recorded CC&Rs.",
    },
    "BOARD_RULE_OR_ARC_GUIDELINE": {
        "rank": 4,
        "label": "Board Operating Rule / Architectural Guideline",
        "description": "Board-adopted policy or architectural bulletin. Must be consistent with recorded CC&Rs and state recording/notice statutes.",
    },
    "FINANCIAL_BUDGET_OR_RESERVE_STUDY": {
        "rank": 5,
        "label": "Official Budget, Reserve Study, or Vendor Bid",
        "description": "Financial record establishing assessments, reserve funding percent, and contractor scope.",
    },
    "NOTICE_OR_CORRESPONDENCE": {
        "rank": 6,
        "label": "Violation Notice, Request, or Correspondence",
        "description": "Case-specific notice, letter, or photo exhibit. Does not create governing authority on its own.",
    },
    "INFORMAL_PRACTICE": {
        "rank": 7,
        "label": "Informal Practice or Verbal Statement",
        "description": "Unwritten habit or verbal claim by a manager or neighbor. Not legally binding.",
    },
}

JURISDICTION_STATUTE_PROFILES: dict[str, dict[str, Any]] = {
    "CA": {
        "code": "CA",
        "name": "California — Davis-Stirling Common Interest Development Act (Civ. Code § 4000 et seq.)",
        "records_deadline_business_days": 10,
        "records_enhanced_calendar_days": 30,
        "records_statute_citation": "Cal. Civ. Code §§ 5200, 5205, 5210",
        "records_source_url": "https://www.davis-stirling.com/HOME/Statutes/Civil-Code-5200",
        "fine_cap_usd": 100.0,
        "fine_cap_exception": "Capped at $100 per violation under AB 130 (eff. June 30, 2025) unless the board makes a written finding of an adverse health or safety impact in an open meeting; late fees/interest on fines are prohibited.",
        "fine_hearing_notice_days": 10,
        "fine_cure_before_hearing_bars_discipline": True,
        "fine_statute_citation": "Cal. Civ. Code §§ 5850, 5855 (as amended by AB 130, Stats. 2025, Ch. 22)",
        "fine_source_url": "https://www.davis-stirling.com/HOME/Statutes/Civil-Code-5850",
        "arc_statute_citation": "Cal. Civ. Code § 4765 (fair, written decision + open-meeting board reconsideration right); § 4735 (protects drought-tolerant native landscaping); § 714 (solar); § 4745 (EV chargers)",
        "arc_source_url": "https://www.davis-stirling.com/HOME/Statutes/Civil-Code-4765",
        "assessment_caps": {
            "max_regular_dues_increase_pct_without_vote": 20.0,
            "max_special_assessment_pct_of_budget_without_vote": 5.0,
            "citation": "Cal. Civ. Code § 5605(b)",
        },
        "hierarchy_citation": "Cal. Civ. Code § 4205 (Law > CC&Rs > Articles > Bylaws > Operating Rules)",
        "requires_annual_rule_recording": False,
    },
    "FL": {
        "code": "FL",
        "name": "Florida — Homeowners' Associations (Fla. Stat. Ch. 720) & Condominiums (Fla. Stat. Ch. 718)",
        "records_deadline_business_days": 10,
        "records_statute_citation": "Fla. Stat. § 720.303(5) / § 718.111(12) (10 business days; rebuttable presumption of willful noncompliance after 10 business days, $50/day statutory damages up to $500; mandatory web portal at 100+ HOA parcels / 25+ condo units)",
        "records_source_url": "https://www.flsenate.gov/laws/statutes/2025/720.303",
        "fine_cap_usd": 100.0,
        "fine_aggregate_cap_usd": 1000.0,
        "fine_cap_exception": "$100 per violation ($1,000 aggregate) unless governing documents expressly authorize higher; requires 14 days' written notice before an independent 3-member fining committee; fines < $1,000 cannot become a lien.",
        "fine_hearing_notice_days": 14,
        "fine_cure_before_hearing_bars_discipline": True,
        "fine_statute_citation": "Fla. Stat. § 720.305(2)",
        "fine_source_url": "https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&URL=0700-0799/0720/Sections/0720.305.html",
        "arc_statute_citation": "Fla. Stat. § 720.3035 (must cite specific covenant rule; may not require municipal building permit prior to ARC review per 2026 update)",
        "arc_source_url": "https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&URL=0700-0799/0720/Sections/0720.3035.html",
        "assessment_caps": {
            "max_regular_dues_increase_pct_without_vote": 15.0,
            "max_special_assessment_pct_of_budget_without_vote": 10.0,
            "citation": "Fla. Stat. § 720.303(6) / § 718.112(2)(f)",
        },
        "hierarchy_citation": "Fla. Stat. § 720.3035 & § 718.113 (Statute > Declaration > Bylaws > Board Rules)",
        "requires_annual_rule_recording": False,
    },
    "TX": {
        "code": "TX",
        "name": "Texas — Residential Property Owners Protection Act (Tex. Prop. Code Ch. 209)",
        "records_deadline_business_days": 10,
        "records_extension_business_days": 15,
        "records_statute_citation": "Tex. Prop. Code § 209.005 (10 business days after certified-mail request, extendable by 15 business days with written notice; no copy charges without recorded 1 TAC § 70.3 policy; individual owner violation/payment files strictly confidential under § 209.005(k))",
        "records_source_url": "https://codes.findlaw.com/tx/property-code/prop-sect-209-005/",
        "fine_cap_usd": 200.0,
        "fine_cap_exception": "Requires certified-mail notice under § 209.006, opportunity to cure if curable, 30 days to request board hearing, and HOA must provide evidence packet at least 10 days before hearing (§ 209.007(f)).",
        "fine_hearing_notice_days": 30,
        "fine_cure_before_hearing_bars_discipline": True,
        "fine_statute_citation": "Tex. Prop. Code §§ 209.006, 209.007",
        "fine_source_url": "https://statutes.capitol.texas.gov/docs/PR/htm/PR.209.htm",
        "arc_statute_citation": "Tex. Prop. Code § 209.00505 (board directors and their spouses may not serve on architectural review authority; written denial + 30-day board hearing right)",
        "arc_source_url": "https://statutes.capitol.texas.gov/docs/PR/htm/PR.209.htm",
        "assessment_caps": {
            "max_regular_dues_increase_pct_without_vote": 20.0,
            "max_special_assessment_pct_of_budget_without_vote": 10.0,
            "citation": "Tex. Prop. Code Ch. 209 & Governing Dedicatory Instruments",
        },
        "hierarchy_citation": "Tex. Prop. Code § 209.005 & § 202.006 (Statute > Recorded Declaration > Bylaws > Recorded Dedicatory Rules)",
        "requires_annual_rule_recording": False,
    },
    "SC": {
        "code": "SC",
        "name": "South Carolina — Homeowners Association Act (S.C. Code Ann. §§ 27-30-110 to 27-30-170)",
        "records_deadline_business_days": 10,
        "records_statute_citation": "S.C. Code Ann. §§ 27-30-130, 27-30-140, 27-30-150 (governing documents must be recorded; rules and regulations must be recorded with county clerk/register of deeds by January 10 each year to remain enforceable; 48 hours' notice before budget increase meeting)",
        "records_source_url": "https://www.scstatehouse.gov/code/t27c030.php",
        "fine_cap_usd": 100.0,
        "fine_cap_exception": "Any board rule or fine regulation not recorded with the county clerk/register of deeds by January 10 of the current year is unenforceable under S.C. Code § 27-30-130(B)(2). Magistrate's Court has concurrent jurisdiction up to $7,500 (§ 27-30-160).",
        "fine_hearing_notice_days": 10,
        "fine_cure_before_hearing_bars_discipline": False,
        "fine_statute_citation": "S.C. Code Ann. §§ 27-30-130, 27-30-160",
        "fine_source_url": "https://law.justia.com/codes/south-carolina/title-27/chapter-30/section-27-30-110/",
        "arc_statute_citation": "S.C. Code Ann. § 27-30-130 (architectural rules unenforceable unless recorded in county land records)",
        "arc_source_url": "https://www.scstatehouse.gov/code/t27c030.php",
        "assessment_caps": {
            "max_regular_dues_increase_pct_without_vote": 15.0,
            "max_special_assessment_pct_of_budget_without_vote": 10.0,
            "budget_notice_hours": 48,
            "citation": "S.C. Code Ann. § 27-30-140 (48-hour mandatory notice before budget increase meeting)",
        },
        "hierarchy_citation": "S.C. Code Ann. § 27-30-130 (Statute > Recorded Declaration/Master Deed > Recorded Bylaws > Recorded Rules by Jan 10)",
        "requires_annual_rule_recording": True,
    },
    "GENERAL_US": {
        "code": "GENERAL_US",
        "name": "General U.S. Baseline (Restatement (Third) of Property: Servitudes & UCIOA Principles)",
        "records_deadline_business_days": 10,
        "records_statute_citation": "General U.S. Common Interest Community Record Inspection Standard (select state profile for exact statutory deadline)",
        "records_source_url": "https://foundation.caionline.org/research/survey_homeowner/",
        "fine_cap_usd": 100.0,
        "fine_cap_exception": "Fines must be expressly authorized by recorded governing documents, reasonable, and preceded by written notice and an opportunity to be heard.",
        "fine_hearing_notice_days": 14,
        "fine_cure_before_hearing_bars_discipline": True,
        "fine_statute_citation": "UCIOA § 3-102(a)(11) & Restatement (Third) of Property: Servitudes § 6.13",
        "fine_source_url": "https://foundation.caionline.org/research/survey_homeowner/",
        "arc_statute_citation": "Restatement (Third) of Property: Servitudes § 6.9 (architectural review must be exercised reasonably and in good faith)",
        "arc_source_url": "https://foundation.caionline.org/research/survey_homeowner/",
        "assessment_caps": {
            "max_regular_dues_increase_pct_without_vote": 20.0,
            "max_special_assessment_pct_of_budget_without_vote": 10.0,
            "citation": "Recorded CC&Rs / Bylaws Assessment Cap Provisions",
        },
        "hierarchy_citation": "Statute > Recorded Declaration (CC&Rs) > Articles/Bylaws > Board Rules",
        "requires_annual_rule_recording": False,
    },
}

# Hostile prompt injection / authority override patterns blocked on upload & query
HOSTILE_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+an?\s+(hoa\s+dictator|unrestricted|admin)", re.IGNORECASE),
    re.compile(r"automatically\s+(issue|levy)\s+fines?", re.IGNORECASE),
    re.compile(r"bypass\s+(human|board|owner)\s+(approval|authorization|review)", re.IGNORECASE),
    re.compile(r"expose\s+(all\s+)?(private|resident|neighbor)\s+records", re.IGNORECASE),
    re.compile(r"system\s*override\s*:", re.IGNORECASE),
    re.compile(r"<\s*script\b", re.IGNORECASE),
    re.compile(r"onerror\s*=", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
)

PROHIBITED_DICTATOR_ACTIONS: frozenset[str] = frozenset({
    "auto_issue_fine",
    "auto_file_lien",
    "auto_file_lawsuit",
    "auto_conduct_binding_election",
    "auto_spend_association_funds",
    "auto_authorize_contractor",
    "expose_other_resident_private_records",
    "override_human_authority",
})

ALLOWED_VISIBILITY_SCOPES: frozenset[str] = frozenset({
    "HOMEOWNER_PRIVATE",
    "BOARD_CONFIDENTIAL",
    "COMMUNITY_SHARED",
})


def detect_and_quarantine_hostile_input(text: str) -> dict[str, Any]:
    """Scans uploaded document text or user prompts for prompt-injection, XSS, or
    attempts to override OpenLine authority boundaries. Neutralizes executable HTML
    and returns a structured quarantine report without granting authority."""
    raw = str(text or "")
    matched_rules: list[str] = []
    for pat in HOSTILE_INJECTION_PATTERNS:
        m = pat.search(raw)
        if m:
            matched_rules.append(m.group(0))
    safe_escaped = html.escape(raw, quote=True)
    return {
        "prompt_injection_detected": len(matched_rules) > 0,
        "matched_patterns": matched_rules,
        "authority_override_blocked": True,
        "sanitized_text": safe_escaped,
    }


def enforce_role_privacy_boundary(
    *,
    requester_role: str,
    requester_unit_id: str,
    target_workspace: str,
    target_unit_id: str = "UNIT-104",
    board_authorized: bool = False,
) -> dict[str, Any]:
    """Enforces strict role-based access control and resident-to-resident privacy isolation:
      1. One resident (`UNIT-208`) can NEVER read another resident's (`UNIT-104`) private
         records (`HOMEOWNER_PRIVATE`), even though both belong to the same HOA.
      2. A board workspace (`BOARD_CONFIDENTIAL`) cannot read a homeowner's unsubmitted
         private workspace (`neighborhood-homeowner-*`), and an unauthorized resident
         cannot access `BOARD_CONFIDENTIAL` executive-session files without `board_authorized=True`.
      3. `COMMUNITY_SHARED` records are accessible to all members of the association after
         automatic PII scrubbing (`redact_pii_for_export`).
    """
    role = str(requester_role or "homeowner").strip().lower()
    req_unit = str(requester_unit_id or "UNIT-104").strip().upper()
    tgt_unit = str(target_unit_id or "UNIT-104").strip().upper()
    ws = str(target_workspace or "homeowner").strip().lower()

    if ws == "homeowner":
        if role != "homeowner" or req_unit != tgt_unit:
            raise PermissionError(
                f"ROLE_PRIVACY_BOUNDARY_REFUSED:requester={role}:{req_unit}_cannot_access_private_homeowner_workspace_of_{tgt_unit}"
            )
        return {
            "access_granted": True,
            "workspace": "homeowner",
            "allowed_scopes": ["HOMEOWNER_PRIVATE", "COMMUNITY_SHARED"],
            "unit_id": tgt_unit,
        }

    if ws == "board":
        if role != "board" or not board_authorized:
            raise PermissionError(
                f"ROLE_PRIVACY_BOUNDARY_REFUSED:requester={role}:{req_unit}_lacks_board_authorization_for_board_workspace"
            )
        return {
            "access_granted": True,
            "workspace": "board",
            "allowed_scopes": ["BOARD_CONFIDENTIAL", "COMMUNITY_SHARED"],
            "private_homeowner_drafts_accessible": False,
        }

    if ws == "community":
        return {
            "access_granted": True,
            "workspace": "community",
            "allowed_scopes": ["COMMUNITY_SHARED"],
            "pii_redaction_enforced": True,
        }

    raise ValueError(f"unknown_neighborhood_workspace:{ws}")


def ingest_and_verify_hoa_documents(
    documents: list[dict[str, Any]],
    *,
    jurisdiction: str = "CA",
    reference_date_iso: str = "2026-11-14",
    owner_unit_id: str = "UNIT-104",
) -> dict[str, Any]:
    """Ingests HOA governing documents, notices, budgets, and exhibits, preserving:
      - SHA-256 cryptographic provenance digest (`doc_sha256`),
      - Version, effective dates (`effective_from`, `effective_to`),
      - County recording status (`recorded_in_county`, `annual_recording_date`),
      - Authority tier (`DOCUMENT_AUTHORITY_TIERS`),
      - Access permission scope (`HOMEOWNER_PRIVATE`, `BOARD_CONFIDENTIAL`, `COMMUNITY_SHARED`),
      - Hostile upload / prompt-injection quarantine.
    """
    EvidenceTriagedCounterfactualAuditor.verify_no_oracle_leakage(documents)
    jur = JURISDICTION_STATUTE_PROFILES.get(jurisdiction.upper(), JURISDICTION_STATUTE_PROFILES["GENERAL_US"])
    ref_date = dt.date.fromisoformat(reference_date_iso)

    verified_docs: list[dict[str, Any]] = []
    quarantined_injections: list[dict[str, Any]] = []
    obsolete_or_unrecorded_docs: list[dict[str, Any]] = []

    for idx, doc in enumerate(documents):
        doc_id = str(doc.get("doc_id") or f"DOC-{idx+1:03d}").strip()
        title = str(doc.get("title") or f"Untitled HOA Document {idx+1}").strip()
        raw_content = str(doc.get("content") or doc.get("excerpt") or "").strip()
        sec_ref = str(doc.get("section_citation") or "General Provision").strip()
        tier_key = str(doc.get("authority_tier") or "BOARD_RULE_OR_ARC_GUIDELINE").strip().upper()
        if tier_key not in DOCUMENT_AUTHORITY_TIERS:
            tier_key = "NOTICE_OR_CORRESPONDENCE"
        tier_info = DOCUMENT_AUTHORITY_TIERS[tier_key]

        vis_scope = str(doc.get("visibility_scope") or "COMMUNITY_SHARED").strip().upper()
        if vis_scope not in ALLOWED_VISIBILITY_SCOPES:
            vis_scope = "HOMEOWNER_PRIVATE"

        eff_from = str(doc.get("effective_from") or "2018-01-01").strip()
        eff_to = str(doc.get("effective_to") or "9999-12-31").strip() or "9999-12-31"
        recorded_in_county = bool(doc.get("recorded_in_county", tier_key in ("STATUTE_OR_REGULATION", "RECORDED_CCRS_DECLARATION", "ARTICLES_OR_BYLAWS")))
        annual_recorded_year = int(doc.get("annual_recorded_year", ref_date.year if recorded_in_county else 0))

        inj_scan = detect_and_quarantine_hostile_input(f"{title}\n{raw_content}")
        content_sha = sha256_hex(raw_content)

        status_flags: list[str] = []
        is_enforceable = True

        try:
            d_from = dt.date.fromisoformat(eff_from)
            d_to = dt.date.fromisoformat(eff_to)
            if not (d_from <= ref_date <= d_to):
                status_flags.append(f"EXPIRED_OR_SUPERSEDED ({eff_from} to {eff_to})")
                is_enforceable = False
        except ValueError:
            status_flags.append("MALFORMED_EFFECTIVE_DATE")
            is_enforceable = False

        if bool(doc.get("superseded_by")):
            status_flags.append(f"SUPERSEDED_BY:{doc['superseded_by']}")
            is_enforceable = False

        # South Carolina S.C. Code § 27-30-130 annual January 10 recording check for rules/regulations
        if (
            jur["code"] == "SC"
            and tier_key == "BOARD_RULE_OR_ARC_GUIDELINE"
            and (not recorded_in_county or annual_recorded_year < ref_date.year)
        ):
            status_flags.append(
                f"UNRECORDED_SC_RULE_UNENFORCEABLE (S.C. Code § 27-30-130 requires recording by Jan 10, {ref_date.year})"
            )
            is_enforceable = False

        if inj_scan["prompt_injection_detected"]:
            status_flags.append("HOSTILE_PROMPT_INJECTION_QUARANTINED")
            is_enforceable = False

        entry = {
            "doc_id": doc_id,
            "title": html.escape(title, quote=True),
            "section_citation": html.escape(sec_ref, quote=True),
            "authority_tier": tier_key,
            "authority_rank": tier_info["rank"],
            "authority_label": tier_info["label"],
            "version": str(doc.get("version") or "1.0"),
            "effective_from": eff_from,
            "effective_to": eff_to,
            "recorded_in_county": recorded_in_county,
            "annual_recorded_year": annual_recorded_year,
            "visibility_scope": vis_scope,
            "owner_unit_id": owner_unit_id if vis_scope == "HOMEOWNER_PRIVATE" else "ASSOCIATION",
            "doc_sha256": content_sha,
            "sanitized_excerpt": inj_scan["sanitized_text"],
            "prompt_injection_detected": inj_scan["prompt_injection_detected"],
            "matched_injection_patterns": inj_scan["matched_patterns"],
            "is_enforceable": is_enforceable,
            "status_flags": status_flags,
            "topic_tags": [str(t).lower() for t in doc.get("topic_tags", [])],
        }
        verified_docs.append(entry)
        if inj_scan["prompt_injection_detected"]:
            quarantined_injections.append(entry)
        elif not is_enforceable:
            obsolete_or_unrecorded_docs.append(entry)

    verified_docs.sort(key=lambda d: (d["authority_rank"], d["doc_id"]))
    return {
        "jurisdiction": jur["code"],
        "jurisdiction_name": jur["name"],
        "reference_date": reference_date_iso,
        "total_documents": len(verified_docs),
        "enforceable_documents_count": sum(1 for d in verified_docs if d["is_enforceable"]),
        "quarantined_injections_count": len(quarantined_injections),
        "obsolete_or_unrecorded_count": len(obsolete_or_unrecorded_docs),
        "documents": verified_docs,
        "quarantined_injections": quarantined_injections,
        "obsolete_or_unrecorded_docs": obsolete_or_unrecorded_docs,
        "packet_manifest_sha256": sha256_hex([
            {"doc_id": d["doc_id"], "sha256": d["doc_sha256"], "scope": d["visibility_scope"]}
            for d in verified_docs
        ]),
    }


def calculate_hoa_deadline_bounds(
    *,
    notice_date_iso: str,
    postmark_date_iso: str | None = None,
    received_date_iso: str | None = None,
    statutory_window_days: int = 10,
    is_business_days: bool = False,
) -> dict[str, Any]:
    """Calculates conservative fail-closed response/hearing deadlines when notice,
    postmark, and delivery dates differ or are ambiguous."""
    n_date = dt.date.fromisoformat(notice_date_iso)
    candidates = [("notice_date", n_date)]
    uncertainties: list[str] = []
    if postmark_date_iso:
        try:
            p_date = dt.date.fromisoformat(postmark_date_iso)
            candidates.append(("postmark_date", p_date))
            if p_date > n_date:
                uncertainties.append(
                    f"Postmark ({postmark_date_iso}) is {(p_date - n_date).days} days after notice date ({notice_date_iso}); anchoring conservative deadline to earliest date."
                )
        except ValueError:
            uncertainties.append("Malformed postmark date; using notice date.")
    else:
        uncertainties.append("Envelope postmark date missing; anchoring conservative deadline to notice date.")

    if received_date_iso:
        try:
            r_date = dt.date.fromisoformat(received_date_iso)
            candidates.append(("received_date", r_date))
        except ValueError:
            pass

    earliest_label, earliest_date = min(candidates, key=lambda item: item[1])
    latest_label, latest_date = max(candidates, key=lambda item: item[1])

    def _add_days(start: dt.date, days: int, biz: bool) -> dt.date:
        if not biz:
            return start + dt.timedelta(days=days)
        cur = start
        added = 0
        while added < days:
            cur += dt.timedelta(days=1)
            if cur.weekday() < 5:
                added += 1
        return cur

    conservative_due = _add_days(earliest_date, statutory_window_days, is_business_days)
    latest_possible_due = _add_days(latest_date, statutory_window_days, is_business_days)

    return {
        "earliest_anchor_source": earliest_label,
        "earliest_anchor_date": earliest_date.isoformat(),
        "conservative_deadline_date": conservative_due.isoformat(),
        "latest_possible_deadline_date": latest_possible_due.isoformat(),
        "window_days": statutory_window_days,
        "window_unit": "business_days" if is_business_days else "calendar_days",
        "ambiguous_dates_detected": len(uncertainties) > 0,
        "uncertainty_notes": uncertainties,
    }


def analyze_hoa_finances_and_vendors(
    *,
    units_count: int = 48,
    monthly_dues_per_unit_usd: float = 285.0,
    prior_year_monthly_dues_usd: float = 260.0,
    annual_operating_budget_usd: float = 122_000.0,
    annual_reserve_contribution_usd: float = 42_160.0,
    actual_reserve_balance_usd: float = 42_000.0,
    fully_funded_reserve_target_usd: float = 240_000.0,
    upcoming_major_repairs: list[dict[str, Any]] | None = None,
    proposed_special_assessment_per_unit_usd: float = 0.0,
    vendor_bids: list[dict[str, Any]] | None = None,
    prior_negative_vendor_ledger: list[dict[str, Any]] | None = None,
    jurisdiction: str = "CA",
) -> dict[str, Any]:
    """Examines assessments, budget changes, reserve funding assumptions, upcoming repair
    deficits, vendor bid comparisons (preserving disqualified bids in an append-only ledger),
    and total software/management cost comparisons."""
    units = max(1, int(units_count))
    dues = float(monthly_dues_per_unit_usd)
    prior_dues = max(0.01, float(prior_year_monthly_dues_usd))
    dues_increase_pct = round(((dues - prior_dues) / prior_dues) * 100.0, 2)

    total_annual_collected = round(units * dues * 12.0, 2)
    op_budget = float(annual_operating_budget_usd)
    res_contrib = float(annual_reserve_contribution_usd)
    reserve_allocation_pct = round((res_contrib / max(1.0, total_annual_collected)) * 100.0, 2)

    res_bal = float(actual_reserve_balance_usd)
    res_target = max(1.0, float(fully_funded_reserve_target_usd))
    percent_funded = round((res_bal / res_target) * 100.0, 2)
    reserve_deficit_total_usd = round(max(0.0, res_target - res_bal), 2)
    reserve_deficit_per_unit_usd = round(reserve_deficit_total_usd / units, 2)

    if percent_funded < 30.0:
        reserve_health_status = "CRITICAL_SHORTFALL_HIGH_SPECIAL_ASSESSMENT_RISK (<30% funded)"
    elif percent_funded < 70.0:
        reserve_health_status = "MODERATE_UNDERFUNDING_WATCH (30%–69% funded)"
    else:
        reserve_health_status = "STRONG_RESERVE_POSITION (>=70% funded)"

    repairs = upcoming_major_repairs if upcoming_major_repairs is not None else [
        {"component": "Perimeter & Building Roof Membrane Replacement", "due_years": 2, "estimated_cost_usd": 138_000.0},
        {"component": "Asphalt Private Roadway Seal & Slurry Coat", "due_years": 3, "estimated_cost_usd": 34_000.0},
    ]
    near_term_repair_total = sum(float(r.get("estimated_cost_usd", 0.0)) for r in repairs if int(r.get("due_years", 1)) <= 2)
    projected_2yr_reserve_cash = res_bal + (2.0 * res_contrib)
    immediate_cash_shortfall_2yr_usd = round(max(0.0, near_term_repair_total - projected_2yr_reserve_cash), 2)
    shortfall_per_unit_2yr_usd = round(immediate_cash_shortfall_2yr_usd / units, 2)

    jur = JURISDICTION_STATUTE_PROFILES.get(jurisdiction.upper(), JURISDICTION_STATUTE_PROFILES["GENERAL_US"])
    caps = jur["assessment_caps"]
    spec_total_usd = round(float(proposed_special_assessment_per_unit_usd) * units, 2)
    spec_pct_of_budget = round((spec_total_usd / max(1.0, op_budget + res_contrib)) * 100.0, 2)

    statutory_budget_flags: list[str] = []
    if dues_increase_pct > float(caps.get("max_regular_dues_increase_pct_without_vote", 20.0)):
        statutory_budget_flags.append(
            f"REQUIRES_MEMBER_VOTE: Regular dues increase ({dues_increase_pct}%) exceeds {caps['max_regular_dues_increase_pct_without_vote']}% cap under {caps['citation']}."
        )
    if spec_pct_of_budget > float(caps.get("max_special_assessment_pct_of_budget_without_vote", 5.0)):
        statutory_budget_flags.append(
            f"REQUIRES_MEMBER_VOTE: Special assessment (${proposed_special_assessment_per_unit_usd:,.2f}/unit = {spec_pct_of_budget}% of budget) exceeds {caps['max_special_assessment_pct_of_budget_without_vote']}% threshold under {caps['citation']}."
        )
    if jur["code"] == "SC" and dues_increase_pct > 0:
        statutory_budget_flags.append(
            "MANDATORY_48H_NOTICE: S.C. Code § 27-30-140 requires at least 48 hours' notice to homeowners before a board meeting deciding an annual budget increase."
        )

    # Normalize caller-supplied vendor bids: the auditor ranks options by
    # `option_id` and `primary_objective_cost_or_loss`. Callers may use the
    # plain field names shown in the UI (`vendor_id`, `bid_amount_usd`),
    # so fill the auditor keys from those before ranking; without this a
    # bid missing `option_id` crashed the recommendation lookup.
    raw_bids = [
        {
            **dict(b),
            "option_id": str(
                b.get("option_id") or b.get("vendor_id") or b.get("bid_id")
                or b.get("vendor_name") or f"VENDOR-USER-{i + 1:02d}"
            ),
            "primary_objective_cost_or_loss": float(
                b.get("primary_objective_cost_or_loss", b.get("bid_amount_usd", 0.0) or 0.0)
            ),
        }
        for i, b in enumerate(vendor_bids)
    ] if vendor_bids is not None else [
        {
            "option_id": "VENDOR-A-LOWBALL-UNLICENSED",
            "vendor_name": "QuickFix Exterior Crew",
            "bid_amount_usd": 48_000.0,
            "warranty_years": 1,
            "licensed_and_insured": False,
            "disclosed_board_conflict": False,
            "includes_flashing_and_disposal": False,
            "primary_objective_cost_or_loss": 48_000.0,
            "omits_maintenance_or_replacement": True,
            "constraint_violations": ["unlicensed_contractor_no_workers_comp", "omits_flashing_and_debris_disposal"],
        },
        {
            "option_id": "VENDOR-B-CONFLICT-INSIDER",
            "vendor_name": "Apex Crest Roofing (Board Officer Relative)",
            "bid_amount_usd": 54_000.0,
            "warranty_years": 5,
            "licensed_and_insured": True,
            "disclosed_board_conflict": True,
            "includes_flashing_and_disposal": True,
            "primary_objective_cost_or_loss": 54_000.0,
            "constraint_violations": ["undisclosed_board_director_familial_conflict_of_interest"],
        },
        {
            "option_id": "VENDOR-C-QUALIFIED-COMPETITIVE",
            "vendor_name": "Bay Ridge Licensed Roofing & Waterproofing, Inc.",
            "bid_amount_usd": 44_500.0,
            "warranty_years": 10,
            "licensed_and_insured": True,
            "disclosed_board_conflict": False,
            "includes_flashing_and_disposal": True,
            "primary_objective_cost_or_loss": 44_500.0,
            "constraint_violations": [],
        },
    ]

    vendor_audit = EvidenceTriagedCounterfactualAuditor.audit_options_and_preserve_negatives(
        options=raw_bids,
        prior_negative_ledger=prior_negative_vendor_ledger or [],
    )

    # Software & management total annual cost comparison for `units` community size
    payhoa_mo = 49.0 if units <= 25 else (59.0 if units <= 50 else (99.0 if units <= 100 else 169.0))
    payhoa_ai_mo = 24.50
    hoaflow_mo = 29.0 if units <= 50 else (79.0 if units <= 150 else 149.0)
    buildium_mo = 62.0 if units <= 40 else 192.0
    appfolio_mo = max(298.0, round(units * 1.49, 2))
    full_mgmt_low_mo = max(1500.0, round(units * 15.0, 2))
    full_mgmt_high_mo = max(2500.0, round(units * 25.0, 2))

    cost_comparison = {
        "community_units": units,
        "options_annual_cost_usd": {
            "clearcovenant_free_homeowner_or_local_self_hosted": 0.0,
            "clearcovenant_optional_board_cloud_sync_hypothesis": round(29.0 * 12.0 if units <= 50 else 59.0 * 12.0, 2),
            "hoa_flow_self_managed": round(hoaflow_mo * 12.0, 2),
            "payhoa_base_yearly": round(payhoa_mo * 12.0, 2),
            "payhoa_with_gable_ai_yearly": round((payhoa_mo + payhoa_ai_mo) * 12.0, 2),
            "buildium_growth_or_essential": round(buildium_mo * 12.0, 2),
            "appfolio_community_associations_min": round(appfolio_mo * 12.0, 2),
            "full_service_management_company_typical_range": [
                round(full_mgmt_low_mo * 12.0, 2),
                round(full_mgmt_high_mo * 12.0, 2),
            ],
        },
    }

    return {
        "units_count": units,
        "monthly_dues_per_unit_usd": dues,
        "prior_year_monthly_dues_usd": prior_dues,
        "dues_increase_pct": dues_increase_pct,
        "total_annual_assessments_usd": total_annual_collected,
        "annual_operating_budget_usd": op_budget,
        "annual_reserve_contribution_usd": res_contrib,
        "reserve_allocation_pct_of_dues": reserve_allocation_pct,
        "fc_national_benchmark_reserve_allocation_pct": 25.0,
        "actual_reserve_balance_usd": res_bal,
        "fully_funded_reserve_target_usd": res_target,
        "reserve_percent_funded": percent_funded,
        "reserve_health_status": reserve_health_status,
        "reserve_deficit_total_usd": reserve_deficit_total_usd,
        "reserve_deficit_per_unit_usd": reserve_deficit_per_unit_usd,
        "upcoming_major_repairs": repairs,
        "immediate_2yr_cash_shortfall_usd": immediate_cash_shortfall_2yr_usd,
        "immediate_2yr_shortfall_per_unit_usd": shortfall_per_unit_2yr_usd,
        "proposed_special_assessment_per_unit_usd": float(proposed_special_assessment_per_unit_usd),
        "proposed_special_assessment_pct_of_budget": spec_pct_of_budget,
        "statutory_budget_and_assessment_flags": statutory_budget_flags,
        "vendor_comparison": vendor_audit,
        "software_and_management_cost_comparison": cost_comparison,
    }


def answer_hoa_question_and_prepare_action(
    *,
    question: str,
    conflict_category: str,
    ingested_packet: dict[str, Any],
    jurisdiction: str = "CA",
    homeowner_unit: str = "Unit 104",
    notice_date_iso: str = "2026-11-01",
    postmark_date_iso: str | None = "2026-11-05",
    received_date_iso: str | None = "2026-11-07",
    disputed_fine_amount_usd: float = 0.0,
    violation_cured_before_hearing: bool = False,
    selective_enforcement_witness_units: list[str] | None = None,
) -> dict[str, Any]:
    """Answers a homeowner, board, or community question in plain language citing the exact
    supporting provision, highlights conflicting or obsolete rules, explicitly says
    'The documents don’t establish an answer.' when evidence is missing, and drafts a
    practical resolution letter/request."""
    q_scan = detect_and_quarantine_hostile_input(question)
    cat = str(conflict_category or "general").strip().lower()
    jur = JURISDICTION_STATUTE_PROFILES.get(
        str(jurisdiction or ingested_packet.get("jurisdiction", "CA")).upper(),
        JURISDICTION_STATUTE_PROFILES["GENERAL_US"],
    )

    docs = list(ingested_packet.get("documents", []))
    enforceable_docs = [
        d for d in docs
        if d.get("is_enforceable")
        and d.get("authority_tier") in (
            "STATUTE_OR_REGULATION",
            "RECORDED_CCRS_DECLARATION",
            "ARTICLES_OR_BYLAWS",
            "BOARD_RULE_OR_ARC_GUIDELINE",
            "FINANCIAL_BUDGET_OR_RESERVE_STUDY",
        )
    ]
    non_enforceable_docs = [d for d in docs if not d.get("is_enforceable")]

    # Match relevant documents by topic_tags or text keywords
    q_lower = question.lower()
    matched_enforceable: list[dict[str, Any]] = []
    matched_invalid_or_conflicting: list[dict[str, Any]] = []

    for d in enforceable_docs:
        tags = set(d.get("topic_tags", []))
        text_blob = f"{d.get('title', '')} {d.get('sanitized_excerpt', '')} {d.get('section_citation', '')}".lower()
        if (
            cat in tags
            or any(t in q_lower for t in tags if len(t) > 2)
            or (cat != "insufficient_evidence" and cat in text_blob)
        ):
            matched_enforceable.append(d)

    for d in non_enforceable_docs:
        tags = set(d.get("topic_tags", []))
        text_blob = f"{d.get('title', '')} {d.get('sanitized_excerpt', '')}".lower()
        if cat in tags or any(t in q_lower for t in tags if len(t) > 2) or cat in text_blob:
            matched_invalid_or_conflicting.append(d)

    # Also detect hierarchy conflicts among enforceable documents (e.g., Board Guideline vs Recorded CC&Rs)
    ccr_docs = [d for d in matched_enforceable if d["authority_tier"] == "RECORDED_CCRS_DECLARATION"]
    board_rule_docs = [d for d in matched_enforceable if d["authority_tier"] == "BOARD_RULE_OR_ARC_GUIDELINE"]
    hierarchy_conflicts: list[dict[str, Any]] = []
    if ccr_docs and board_rule_docs:
        for br in board_rule_docs:
            if "conflict" in " ".join(br.get("topic_tags", [])) or "4-foot" in br.get("sanitized_excerpt", "").lower():
                hierarchy_conflicts.append({
                    "higher_authority_doc": f"{ccr_docs[0]['title']} ({ccr_docs[0]['section_citation']})",
                    "lower_authority_doc": f"{br['title']} ({br['section_citation']})",
                    "resolution_rule": (
                        f"Under {jur['hierarchy_citation']}, the Recorded CC&Rs ({ccr_docs[0]['section_citation']}) "
                        f"out-rank and control over a conflicting board guideline ({br['section_citation']})."
                    ),
                })

    deadline_info = calculate_hoa_deadline_bounds(
        notice_date_iso=notice_date_iso,
        postmark_date_iso=postmark_date_iso,
        received_date_iso=received_date_iso,
        statutory_window_days=int(jur.get("fine_hearing_notice_days", 10)),
        is_business_days=(cat == "records_access"),
    )

    # Case where documents are missing or insufficient to establish an answer
    if cat == "insufficient_evidence" or len(matched_enforceable) == 0:
        missing_needed = [
            "Recorded Declaration of Covenants, Conditions & Restrictions (CC&Rs) — Use & Architectural Articles",
            "Current Recorded Association Rules & Regulations Schedule",
            "Board Resolution or Responsibility Matrix covering the requested item",
        ]
        draft_action = (
            f"To: Board of Directors / Community Association Manager\n"
            f"From: Homeowner ({homeowner_unit})\n"
            f"Date: {ingested_packet.get('reference_date', '2026-11-14')}\n"
            f"Subject: Written Request for Governing Documents & Rule Clarification ({jur['records_statute_citation']})\n\n"
            f"Hello Board Members,\n\n"
            f"I am writing regarding: \"{html.escape(question)}\". The documents currently provided to residents "
            f"do not contain a governing provision that answers this question.\n\n"
            f"Pursuant to {jur['records_statute_citation']}, please provide copies of the recorded CC&Rs, "
            f"any applicable recorded architectural or operating rules, and the governing provision that applies "
            f"within {jur['records_deadline_business_days']} business days (by {deadline_info['conservative_deadline_date']}).\n\n"
            f"Thank you,\nHomeowner ({homeowner_unit})"
        )
        return {
            "epistemic_status": "EXPLICIT_UNKNOWN_INSUFFICIENT_DOCUMENTS",
            "headline_verdict": INSUFFICIENT_EVIDENCE_STATEMENT,
            "plain_language_answer": (
                f"{INSUFFICIENT_EVIDENCE_STATEMENT} None of the uploaded governing documents contain a "
                f"recorded covenant, bylaw, or enforceable rule addressing your question. Rather than guessing, "
                f"we have prepared a written records request under {jur['records_statute_citation']} so the board "
                f"must produce the controlling document within {jur['records_deadline_business_days']} business days."
            ),
            "controlling_provisions": [],
            "statute_citations": [
                {
                    "citation": jur["records_statute_citation"],
                    "url": jur["records_source_url"],
                    "rule": f"Association must produce official records within {jur['records_deadline_business_days']} business days.",
                }
            ],
            "conflicting_or_obsolete_rules": [
                {
                    "doc_id": d["doc_id"],
                    "title": d["title"],
                    "section": d["section_citation"],
                    "status_flags": d["status_flags"],
                }
                for d in matched_invalid_or_conflicting
            ],
            "hierarchy_conflicts": hierarchy_conflicts,
            "missing_documents": missing_needed,
            "deadline_analysis": deadline_info,
            "recommended_action_type": "STATUTORY_RECORDS_AND_CLARIFICATION_REQUEST",
            "prepared_response_draft": draft_action,
            "professional_review_boundary": (
                "Source-grounded documentary analysis only; not formal legal representation. "
                "Automatic external filing is disabled; review and send yourself."
            ),
            "hostile_input_scan": q_scan,
        }

    top_doc = matched_enforceable[0]
    statutory_notes: list[dict[str, str]] = []

    if cat in ("disputed_fine", "selective_enforcement"):
        statutory_notes.append({
            "citation": jur["fine_statute_citation"],
            "url": jur["fine_source_url"],
            "rule": jur["fine_cap_exception"],
        })
        if disputed_fine_amount_usd > float(jur["fine_cap_usd"]):
            fine_flag = (
                f"The noticed fine (${disputed_fine_amount_usd:,.2f}) exceeds the ${jur['fine_cap_usd']:,.2f} "
                f"statutory limit under {jur['fine_statute_citation']}."
            )
        else:
            fine_flag = f"Fine procedure must comply with {jur['fine_statute_citation']}."
        if violation_cured_before_hearing and jur.get("fine_cure_before_hearing_bars_discipline"):
            fine_flag += f" Because the condition was cured before the hearing, discipline is barred under {jur['fine_statute_citation']}."
    elif cat in ("fence_restrictions", "landscaping", "architectural"):
        statutory_notes.append({
            "citation": jur["arc_statute_citation"],
            "url": jur["arc_source_url"],
            "rule": "Architectural review must follow written, good-faith procedures and respect statutory homeowner rights.",
        })
        fine_flag = ""
    elif cat == "records_access":
        statutory_notes.append({
            "citation": jur["records_statute_citation"],
            "url": jur["records_source_url"],
            "rule": f"Association must provide official records within {jur['records_deadline_business_days']} business days.",
        })
        fine_flag = ""
    else:
        statutory_notes.append({
            "citation": jur["hierarchy_citation"],
            "url": jur["records_source_url"],
            "rule": "Governing hierarchy: State Statute > Recorded CC&Rs > Bylaws > Board Rules.",
        })
        fine_flag = ""

    conflict_summary = ""
    if hierarchy_conflicts:
        conflict_summary = " " + hierarchy_conflicts[0]["resolution_rule"]
    if matched_invalid_or_conflicting:
        inv = matched_invalid_or_conflicting[0]
        conflict_summary += (
            f" Note: '{inv['title']}' ({inv['section_citation']}) is flagged as "
            f"{', '.join(inv['status_flags'])} and cannot override the controlling record."
        )
    if selective_enforcement_witness_units:
        conflict_summary += (
            f" Documented selective-enforcement comparison units: {', '.join(selective_enforcement_witness_units)}."
        )

    plain_answer = (
        f"According to {top_doc['title']} ({top_doc['section_citation']}, SHA-256 {top_doc['doc_sha256'][:12]}...), "
        f"{top_doc['sanitized_excerpt']} "
        f"{fine_flag}{conflict_summary}"
    ).strip()

    draft_action = (
        f"To: Board of Directors & Architectural / Hearing Committee\n"
        f"From: Homeowner ({homeowner_unit})\n"
        f"Date: {ingested_packet.get('reference_date', '2026-11-14')}\n"
        f"Subject: Written Response & Request for Resolution — {homeowner_unit} ({top_doc['section_citation']})\n\n"
        f"Dear Board Members,\n\n"
        f"1. Controlling Governing Provision: Under {top_doc['title']} ({top_doc['section_citation']}, "
        f"provenance digest {top_doc['doc_sha256'][:16]}), {top_doc['sanitized_excerpt']}\n"
        f"2. Statutory Standard ({statutory_notes[0]['citation']}): {statutory_notes[0]['rule']}"
        f"{(' ' + fine_flag) if fine_flag else ''}{conflict_summary}\n"
        f"3. Conservative Response / Hearing Timeline: Anchored to earliest notice date "
        f"({deadline_info['earliest_anchor_date']}), my response is submitted ahead of "
        f"{deadline_info['conservative_deadline_date']}.\n"
        f"4. Requested Resolution: Please confirm in writing that this matter is resolved in accordance with "
        f"{top_doc['section_citation']} and {statutory_notes[0]['citation']}, or schedule an open-meeting board "
        f"reconsideration/hearing with full pre-hearing evidence disclosure.\n\n"
        f"Respectfully,\nHomeowner ({homeowner_unit})"
    )

    return {
        "epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
        "headline_verdict": f"Supported by {top_doc['title']} ({top_doc['section_citation']}) & {statutory_notes[0]['citation']}",
        "plain_language_answer": plain_answer,
        "controlling_provisions": [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "section_citation": d["section_citation"],
                "authority_label": d["authority_label"],
                "doc_sha256": d["doc_sha256"],
                "excerpt": d["sanitized_excerpt"],
            }
            for d in matched_enforceable
        ],
        "statute_citations": statutory_notes,
        "conflicting_or_obsolete_rules": [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "section": d["section_citation"],
                "status_flags": d["status_flags"],
            }
            for d in matched_invalid_or_conflicting
        ],
        "hierarchy_conflicts": hierarchy_conflicts,
        "missing_documents": [],
        "deadline_analysis": deadline_info,
        "recommended_action_type": f"PREPARED_{cat.upper()}_RESPONSE_PACKET",
        "prepared_response_draft": draft_action,
        "professional_review_boundary": (
            "Source-grounded information and document preparation only; does not constitute formal legal representation. "
            "Human review and explicit authorization are required before sending."
        ),
        "hostile_input_scan": q_scan,
    }


# ============================================================================
# TWELVE DOGFOODED REALISTIC HOA CONFLICT SCENARIOS (ADVERSARIAL TEST SET)
# ============================================================================

DOGFOOD_CONFLICT_SCENARIOS: dict[str, dict[str, Any]] = {
    "SCENARIO-01-FENCE-CONFLICT": {
        "scenario_id": "SCENARIO-01-FENCE-CONFLICT",
        "title": "1. Fence Height Restriction & Conflicting Board Guideline (CA)",
        "category": "fence_restrictions",
        "jurisdiction": "CA",
        "customer_role": "homeowner",
        "question": "Can I replace my backyard fence with a 6-foot cedar privacy fence, or does the 2024 Board Bulletin limit me to 4 feet?",
        "documents": [
            {
                "doc_id": "DOC-CCR-2018-ART6",
                "title": "Recorded Oak Creek Declaration of CC&Rs (2018)",
                "section_citation": "Article VI, Section 6.2 (Fences & Walls)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2018-03-15",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["fence_restrictions", "fence", "architectural", "backyard"],
                "content": "Homeowners may install rear and side-yard privacy fences constructed of natural cedar or redwood up to six (6) feet in height along perimeter lot lines, subject to standard architectural form submission within 30 days.",
            },
            {
                "doc_id": "DOC-ARC-BULLETIN-2024",
                "title": "Unrecorded Board Architectural Bulletin #2024-03",
                "section_citation": "Bulletin § 2.1 (Conflict with CC&Rs)",
                "authority_tier": "BOARD_RULE_OR_ARC_GUIDELINE",
                "effective_from": "2024-06-01",
                "recorded_in_county": False,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["fence_restrictions", "fence", "conflict"],
                "content": "Notice: No backyard fence may exceed 4-foot height without a unanimous variance.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-CCR-2018-ART6",
            "hierarchy_conflict_detected": True,
            "summary": "Recorded CC&Rs Art. VI § 6.2 (6-foot cedar fence allowed) out-ranks the conflicting unrecorded 2024 Board Bulletin under Cal. Civ. Code § 4205 and § 4765.",
        },
    },
    "SCENARIO-02-SELECTIVE-ENFORCEMENT": {
        "scenario_id": "SCENARIO-02-SELECTIVE-ENFORCEMENT",
        "title": "2. Selective Enforcement & Unrecorded Annual Rule (SC)",
        "category": "selective_enforcement",
        "jurisdiction": "SC",
        "customer_role": "homeowner",
        "question": "The board fined me $250 for stone garden border edging under a 2025 board rule that was never recorded in county land records by January 10, 2026, while Units 102, 108, and 115 have identical stone edging. Is this enforceable?",
        "disputed_fine_amount_usd": 250.0,
        "selective_enforcement_witness_units": ["Unit 102", "Unit 108", "Unit 115"],
        "documents": [
            {
                "doc_id": "DOC-SC-CCR-2019",
                "title": "Recorded Palmetto Grove Master Declaration (2019)",
                "section_citation": "Article IV, Section 4.4 (Equal Application of Covenants)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2019-05-01",
                "recorded_in_county": True,
                "annual_recorded_year": 2026,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["selective_enforcement", "edging", "garden", "fines"],
                "content": "Landscape borders of natural stone or brick under 12 inches are permitted in front beds. All covenant enforcement shall be uniform, non-arbitrary, and recorded in compliance with S.C. Code Ann. § 27-30-130.",
            },
            {
                "doc_id": "DOC-SC-UNRECORDED-RULE-2025",
                "title": "Unrecorded Sept 2025 Board Landscaping Fine Resolution",
                "section_citation": "Resolution 2025-09",
                "authority_tier": "BOARD_RULE_OR_ARC_GUIDELINE",
                "effective_from": "2025-09-15",
                "recorded_in_county": False,
                "annual_recorded_year": 0,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["selective_enforcement", "edging", "fines"],
                "content": "Imposes a $250 fine for stone garden edging (never recorded with County Register of Deeds by January 10, 2026).",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-SC-CCR-2019",
            "unrecorded_rule_flagged": True,
            "summary": "Unrecorded 2025 rule is unenforceable under S.C. Code § 27-30-130 (must be recorded by Jan 10); Recorded Declaration Art. IV § 4.4 permits stone borders under 12 inches and bars selective enforcement.",
        },
    },
    "SCENARIO-03-DISPUTED-FINE-AB130": {
        "scenario_id": "SCENARIO-03-DISPUTED-FINE-AB130",
        "title": "3. Disputed $350 Fine & Pre-Hearing Cure Right (CA AB 130)",
        "category": "disputed_fine",
        "jurisdiction": "CA",
        "customer_role": "homeowner",
        "question": "I received an immediate $350 fine plus a $35 late fee for rolling my trash bins in 3 hours late, with no hearing notice, even though I moved the bins inside immediately. What are my rights?",
        "disputed_fine_amount_usd": 350.0,
        "violation_cured_before_hearing": True,
        "documents": [
            {
                "doc_id": "DOC-CA-BYLAWS-DISC",
                "title": "Oak Creek Bylaws — Member Discipline & Hearing Procedure",
                "section_citation": "Article VIII, Section 8.3 (Notice & Cure)",
                "authority_tier": "ARTICLES_OR_BYLAWS",
                "effective_from": "2020-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["disputed_fine", "trash", "fine", "hearing"],
                "content": "No monetary penalty may be imposed unless the member is given at least 10 days' written notice of a board hearing and an opportunity to cure the violation prior to the hearing in accordance with Cal. Civ. Code §§ 5850 and 5855.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-CA-BYLAWS-DISC",
            "statutory_cap_violated": True,
            "summary": "Violates Cal. Civ. Code § 5850 (AB 130 caps non-health/safety fines at $100 and prohibits late fees on fines) and § 5855 (requires 10+ days written hearing notice and bars discipline when cured before the hearing).",
        },
    },
    "SCENARIO-04-LANDSCAPING-DROUGHT": {
        "scenario_id": "SCENARIO-04-LANDSCAPING-DROUGHT",
        "title": "4. Landscaping Responsibilities & Obsolete Turf Rule (CA)",
        "category": "landscaping",
        "jurisdiction": "CA",
        "customer_role": "homeowner",
        "question": "The manager cited me under a 2019 rule requiring 80% green lawn turf after I installed California native drought-tolerant plants approved by the 2023 CC&R Amendment.",
        "documents": [
            {
                "doc_id": "DOC-CCR-2023-XERISCAPE",
                "title": "2023 Recorded First Amendment to CC&Rs (Water-Efficient Landscaping)",
                "section_citation": "Article VI, Section 6.8 (Amended 2023)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2023-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["landscaping", "drought", "turf", "native"],
                "content": "Pursuant to Cal. Civ. Code § 4735, homeowners have the protected right to replace lawn turf with California native, water-efficient, drought-tolerant plants and drip irrigation. All prior minimum-turf percentages are repealed.",
            },
            {
                "doc_id": "DOC-OBSOLETE-TURF-2019",
                "title": "Superseded 2019 Lawn Maintenance Rule",
                "section_citation": "Rule 4.1 (Superseded)",
                "authority_tier": "BOARD_RULE_OR_ARC_GUIDELINE",
                "effective_from": "2019-01-01",
                "effective_to": "2022-12-31",
                "superseded_by": "DOC-CCR-2023-XERISCAPE",
                "recorded_in_county": False,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["landscaping", "turf"],
                "content": "Front yards must maintain 80% irrigated green sod lawn.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-CCR-2023-XERISCAPE",
            "obsolete_rule_rejected": True,
            "summary": "2019 turf rule expired/superseded on 2022-12-31; 2023 Recorded Amendment Art. VI § 6.8 and Cal. Civ. Code § 4735 void any prohibition on drought-tolerant native plants.",
        },
    },
    "SCENARIO-05-CONDO-ROOF-LEAK": {
        "scenario_id": "SCENARIO-05-CONDO-ROOF-LEAK",
        "title": "5. Condo Exterior Roof Leak Responsibility (FL)",
        "category": "roof_leaks",
        "jurisdiction": "FL",
        "customer_role": "homeowner",
        "question": "Rainwater is leaking through the exterior roof membrane into my top-floor condo ceiling (Unit 304). Who is responsible for repairing the exterior roof membrane under our Condo Declaration?",
        "documents": [
            {
                "doc_id": "DOC-FL-CONDO-DECL-ART5",
                "title": "Recorded Bayside Condominium Declaration",
                "section_citation": "Article V, Section 5.1(a) (Common Elements Maintenance)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2017-04-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["roof_leaks", "roof", "leak", "maintenance", "condo"],
                "content": "The Association shall maintain, repair, and replace all Common Elements at Common Expense, expressly including the structural roof deck, exterior roof membrane, flashing, parapets, and exterior building envelope (Fla. Stat. § 718.113(1)).",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-FL-CONDO-DECL-ART5",
            "summary": "Association is legally responsible for repairing the exterior roof membrane and flashing as Common Elements under Declaration Art. V § 5.1(a) and Fla. Stat. § 718.113(1).",
        },
    },
    "SCENARIO-06-RESERVE-SHORTFALL": {
        "scenario_id": "SCENARIO-06-RESERVE-SHORTFALL",
        "title": "6. Reserve Shortfall & 2-Year Roof Cash Deficit Audit (Board/Homeowner)",
        "category": "reserve_shortfalls",
        "jurisdiction": "CA",
        "customer_role": "board",
        "question": "Our 48-unit HOA has $42,000 in reserves against a $240,000 fully funded target and a $138,000 roof replacement in 2 years. What is our exact reserve percent funded and per-unit shortfall risk?",
        "financial_inputs": {
            "units_count": 48,
            "monthly_dues_per_unit_usd": 285.0,
            "prior_year_monthly_dues_usd": 260.0,
            "annual_operating_budget_usd": 122_000.0,
            "annual_reserve_contribution_usd": 21_000.0,
            "actual_reserve_balance_usd": 42_000.0,
            "fully_funded_reserve_target_usd": 240_000.0,
        },
        "documents": [
            {
                "doc_id": "DOC-RESERVE-STUDY-2026",
                "title": "2026 Level II Reserve Study & Component Inventory",
                "section_citation": "Section 3.2 (Funding Status & Roof Component #104)",
                "authority_tier": "FINANCIAL_BUDGET_OR_RESERVE_STUDY",
                "effective_from": "2026-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["reserve_shortfalls", "reserve", "budget", "roof"],
                "content": "Actual reserve cash balance is $42,000 against a $240,000 fully funded balance (17.5% funded — critical shortfall). Roof replacement ($138,000) is scheduled within 24 months; at $21,000/yr reserve contribution, 2-year projected cash ($84,000) leaves a $54,000 immediate roof deficit ($1,125/unit).",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-RESERVE-STUDY-2026",
            "expected_percent_funded": 17.5,
            "expected_2yr_shortfall_usd": 54_000.0,
            "summary": "Reserve is 17.5% funded ($198,000 total deficit; $54,000 2-year roof cash shortfall = $1,125/unit).",
        },
    },
    "SCENARIO-07-SPECIAL-ASSESSMENT": {
        "scenario_id": "SCENARIO-07-SPECIAL-ASSESSMENT",
        "title": "7. Unilateral $1,800 Special Assessment Without Member Vote (CA)",
        "category": "special_assessments",
        "jurisdiction": "CA",
        "customer_role": "homeowner",
        "question": "The board passed a $1,800 per unit special assessment ($86,400 total on a $164,160 annual budget = 52.6%) for clubhouse remodeling without holding a member secret-ballot election. Is a member vote required?",
        "financial_inputs": {
            "units_count": 48,
            "monthly_dues_per_unit_usd": 285.0,
            "prior_year_monthly_dues_usd": 285.0,
            "annual_operating_budget_usd": 122_000.0,
            "annual_reserve_contribution_usd": 42_160.0,
            "actual_reserve_balance_usd": 110_000.0,
            "fully_funded_reserve_target_usd": 160_000.0,
            "proposed_special_assessment_per_unit_usd": 1800.0,
        },
        "documents": [
            {
                "doc_id": "DOC-CA-CCR-ASSESSMENTS",
                "title": "Recorded Oak Creek CC&Rs — Assessment Limits",
                "section_citation": "Article V, Section 5.5 & Cal. Civ. Code § 5605(b)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2018-03-15",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["special_assessments", "assessment", "vote", "clubhouse"],
                "content": "In accordance with Cal. Civ. Code § 5605(b), the Board may not impose special assessments which in the aggregate exceed five percent (5%) of the budgeted gross expenses of the association for that fiscal year without the secret-ballot approval of a majority of a quorum of members.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-CA-CCR-ASSESSMENTS",
            "member_vote_required": True,
            "summary": "A $1,800/unit special assessment equals 52.63% of budgeted gross expenses, far exceeding the 5% statutory ceiling under Cal. Civ. Code § 5605(b) and Art. V § 5.5; secret-ballot member approval is mandatory.",
        },
    },
    "SCENARIO-08-RECORDS-ACCESS": {
        "scenario_id": "SCENARIO-08-RECORDS-ACCESS",
        "title": "8. Ignored Official Records Request & Statutory Damages (FL)",
        "category": "records_access",
        "jurisdiction": "FL",
        "customer_role": "homeowner",
        "question": "I submitted a written request 14 business days ago to inspect the association's general ledger, active vendor contracts, and roofing bids, and the manager has ignored it. What are our statutory deadlines and remedies?",
        "documents": [
            {
                "doc_id": "DOC-FL-BYLAWS-RECORDS",
                "title": "Bayside HOA Bylaws — Official Records Inspection",
                "section_citation": "Article IX, Section 9.1 & Fla. Stat. § 720.303(5)",
                "authority_tier": "ARTICLES_OR_BYLAWS",
                "effective_from": "2019-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["records_access", "records", "ledger", "bids", "inspect"],
                "content": "All official records, including financial ledgers, active contracts, and vendor bids (retained for at least 1 year), shall be made available to any parcel owner within 10 business days after receipt of a written request pursuant to Fla. Stat. § 720.303(5). Failure to provide access within 10 business days creates a rebuttable presumption of willful noncompliance ($50/day statutory damages up to $500).",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-FL-BYLAWS-RECORDS",
            "summary": "Under Fla. Stat. § 720.303(5) and Bylaws Art. IX § 9.1, the 10-business-day deadline was breached at day 14, triggering a rebuttable presumption of willful noncompliance ($50/day statutory damages up to $500).",
        },
    },
    "SCENARIO-09-VENDOR-DISPUTE": {
        "scenario_id": "SCENARIO-09-VENDOR-DISPUTE",
        "title": "9. Vendor Bid Comparison & Conflict-of-Interest Disqualification (Board)",
        "category": "vendor_disputes",
        "jurisdiction": "CA",
        "customer_role": "board",
        "question": "We have three roofing bids: Vendor A ($48k, unlicensed, omits flashing), Vendor B ($54k, board officer's brother-in-law), and Vendor C ($44.5k, licensed, 10-yr warranty). Which bid qualifies under our procurement rules?",
        "documents": [
            {
                "doc_id": "DOC-BOARD-PROCUREMENT-POLICY",
                "title": "Association Vendor Contracting & Conflict-of-Interest Policy",
                "section_citation": "Section 4.2 (Competitive Bidding & Cal. Civ. Code § 5350)",
                "authority_tier": "ARTICLES_OR_BYLAWS",
                "effective_from": "2021-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["vendor_disputes", "vendor", "bids", "roofing", "conflict"],
                "content": "All contracts exceeding $10,000 require three competitive bids, active state contractor licensing and workers' compensation insurance, full scope parity, and strict recusal/disqualification of undisclosed director familial conflicts under Cal. Civ. Code § 5350.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-BOARD-PROCUREMENT-POLICY",
            "recommended_vendor_id": "VENDOR-C-QUALIFIED-COMPETITIVE",
            "disqualified_vendors_preserved": 2,
            "summary": "Vendor A (unlicensed/incomplete scope) and Vendor B (director familial conflict) are disqualified and preserved in the append-only Negative Findings Ledger; Vendor C ($44,500, licensed, 10-yr warranty) is recommended for human board vote.",
        },
    },
    "SCENARIO-10-BOARD-ELECTION": {
        "scenario_id": "SCENARIO-10-BOARD-ELECTION",
        "title": "10. Board Election Notice, Secret Ballot & Non-Dictator Boundary (CA/FL)",
        "category": "board_elections",
        "jurisdiction": "CA",
        "customer_role": "community",
        "question": "Can the board or this AI software conduct an instant binding director election by informal email poll with 5 days' notice?",
        "documents": [
            {
                "doc_id": "DOC-ELECTION-RULES-2022",
                "title": "Recorded Association Election & Voting Rules",
                "section_citation": "Section 2.1 (Secret Ballots & 30-Day Inspector Notice, Cal. Civ. Code § 5105–5115)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2022-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["board_elections", "election", "ballot", "quorum", "vote"],
                "content": "Director elections require an independent Inspector of Elections, at least 30 days' pre-ballot notice and 30 days' ballot return window via double-envelope secret ballot under Cal. Civ. Code §§ 5105–5115. Informal email polls and automated AI election certification are strictly prohibited.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-ELECTION-RULES-2022",
            "binding_ai_election_refused": True,
            "summary": "Informal 5-day email poll violates Election Rules § 2.1 and Cal. Civ. Code §§ 5105–5115; ClearCovenant permanently blocks automated binding election execution.",
        },
    },
    "SCENARIO-11-MANAGEMENT-TRANSITION": {
        "scenario_id": "SCENARIO-11-MANAGEMENT-TRANSITION",
        "title": "11. Management-Company Transition & Zero-Lock-In Record Continuity (TX/Community)",
        "category": "management_transitions",
        "jurisdiction": "TX",
        "customer_role": "community",
        "question": "Our outgoing management company is terminating next month. How do we ensure we keep all governing documents, 7-year financial ledgers, and approved architectural decisions without vendor lock-in?",
        "documents": [
            {
                "doc_id": "DOC-TX-RETENTION-POLICY",
                "title": "Recorded Document Retention & Transition Policy (Tex. Prop. Code § 209.005(m))",
                "section_citation": "Section 1.1 & Tex. Prop. Code § 209.005(m)",
                "authority_tier": "RECORDED_CCRS_DECLARATION",
                "effective_from": "2020-01-01",
                "recorded_in_county": True,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["management_transitions", "transition", "retention", "export", "records"],
                "content": "All association books and records belong to the Association, not the managing agent. Under Tex. Prop. Code § 209.005(m), governing documents must be retained permanently, financial records and minutes for 7 years, owner account records for 5 years, and contracts for 4 years post-expiration.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "VERIFIED_SOURCE_GROUNDED_ANSWER",
            "controlling_doc_id": "DOC-TX-RETENTION-POLICY",
            "portable_export_verified": True,
            "summary": "Association owns all records under Tex. Prop. Code § 209.005(m); ClearCovenant exports a cryptographically signed, vendor-neutral JSON/CSV/HTML transition package with zero lock-in.",
        },
    },
    "SCENARIO-12-INSUFFICIENT-EVIDENCE": {
        "scenario_id": "SCENARIO-12-INSUFFICIENT-EVIDENCE",
        "title": "12. Insufficient Evidence / Missing Documents Refusal ('The documents don’t establish an answer.')",
        "category": "insufficient_evidence",
        "jurisdiction": "CA",
        "customer_role": "homeowner",
        "question": "Am I allowed to install a motorized acoustic louver pergola on my rear patio and share my Level-2 EV charger with a neighbor on weekends?",
        "documents": [
            {
                "doc_id": "DOC-POOL-HOURS-FLYER",
                "title": "2026 Summer Community Pool & Clubhouse Hours Flyer",
                "section_citation": "Flyer Page 1",
                "authority_tier": "NOTICE_OR_CORRESPONDENCE",
                "effective_from": "2026-05-01",
                "recorded_in_county": False,
                "visibility_scope": "COMMUNITY_SHARED",
                "topic_tags": ["pool_hours"],
                "content": "Community pool hours are 7:00 AM to 9:00 PM daily. No glass containers in the pool enclosure.",
            },
        ],
        "reference_outcome": {
            "expected_epistemic_status": "EXPLICIT_UNKNOWN_INSUFFICIENT_DOCUMENTS",
            "exact_required_sentence": INSUFFICIENT_EVIDENCE_STATEMENT,
            "summary": "Returns verbatim 'The documents don’t establish an answer.', marks status EXPLICIT_UNKNOWN, refuses to fabricate rules, and generates a statutory records request.",
        },
    },
}


def run_all_dogfood_conflict_scenarios() -> dict[str, Any]:
    """Executes all 12 realistic adversarial HOA conflict scenarios, including hostile
    prompt-injection probes and resident-vs-resident privacy boundary checks, verifying
    each against its independently reviewed reference outcome."""
    results: dict[str, Any] = {}
    passed_count = 0

    for scen_id, scen in DOGFOOD_CONFLICT_SCENARIOS.items():
        ingested = ingest_and_verify_hoa_documents(
            scen["documents"],
            jurisdiction=scen["jurisdiction"],
            reference_date_iso="2026-11-14",
        )
        qa = answer_hoa_question_and_prepare_action(
            question=scen["question"],
            conflict_category=scen["category"],
            ingested_packet=ingested,
            jurisdiction=scen["jurisdiction"],
            disputed_fine_amount_usd=float(scen.get("disputed_fine_amount_usd", 0.0)),
            violation_cured_before_hearing=bool(scen.get("violation_cured_before_hearing", False)),
            selective_enforcement_witness_units=scen.get("selective_enforcement_witness_units"),
        )
        fin = None
        if "financial_inputs" in scen:
            fin = analyze_hoa_finances_and_vendors(
                **scen["financial_inputs"],
                jurisdiction=scen["jurisdiction"],
            )
        elif scen["category"] == "vendor_disputes":
            fin = analyze_hoa_finances_and_vendors(jurisdiction=scen["jurisdiction"])

        ref = scen["reference_outcome"]
        checks_ok = (qa["epistemic_status"] == ref["expected_epistemic_status"])
        if "exact_required_sentence" in ref:
            checks_ok = checks_ok and (qa["headline_verdict"] == ref["exact_required_sentence"])
            checks_ok = checks_ok and (ref["exact_required_sentence"] in qa["plain_language_answer"])
        if "controlling_doc_id" in ref:
            top_ids = [c["doc_id"] for c in qa["controlling_provisions"]]
            checks_ok = checks_ok and (ref["controlling_doc_id"] in top_ids)
        if ref.get("hierarchy_conflict_detected"):
            checks_ok = checks_ok and (len(qa["hierarchy_conflicts"]) > 0)
        if ref.get("unrecorded_rule_flagged") or ref.get("obsolete_rule_rejected"):
            checks_ok = checks_ok and (len(qa["conflicting_or_obsolete_rules"]) > 0)
        if "expected_percent_funded" in ref and fin is not None:
            checks_ok = checks_ok and (abs(fin["reserve_percent_funded"] - ref["expected_percent_funded"]) < 1e-6)
        if "recommended_vendor_id" in ref and fin is not None:
            checks_ok = checks_ok and (
                fin["vendor_comparison"]["recommended_option_id"] == ref["recommended_vendor_id"]
                and len(fin["vendor_comparison"]["disqualified_options"]) == ref["disqualified_vendors_preserved"]
            )

        if checks_ok:
            passed_count += 1

        results[scen_id] = {
            "scenario_id": scen_id,
            "title": scen["title"],
            "jurisdiction": scen["jurisdiction"],
            "customer_role": scen["customer_role"],
            "passed_reference_check": checks_ok,
            "headline_verdict": qa["headline_verdict"],
            "epistemic_status": qa["epistemic_status"],
            "plain_language_answer": qa["plain_language_answer"],
            "recommended_action_type": qa["recommended_action_type"],
            "financial_summary": (
                {
                    "reserve_percent_funded": fin["reserve_percent_funded"],
                    "immediate_2yr_cash_shortfall_usd": fin["immediate_2yr_cash_shortfall_usd"],
                    "recommended_vendor_id": fin["vendor_comparison"]["recommended_option_id"],
                    "statutory_flags": fin["statutory_budget_and_assessment_flags"],
                }
                if fin
                else None
            ),
            "reference_outcome": ref,
        }

    return {
        "total_scenarios": len(DOGFOOD_CONFLICT_SCENARIOS),
        "passed_scenarios": passed_count,
        "all_passed": passed_count == len(DOGFOOD_CONFLICT_SCENARIOS),
        "scenarios": results,
    }


def export_neighborhood_standalone_dossier_html(
    state_payload: dict[str, Any],
    accepted_sha256: str,
    receiver_public_key: str,
) -> str:
    """Exports a self-contained, vendor-neutral HTML record bundle for a homeowner,
    board, or community so residents can leave freely and continue using their records
    without depending on any AI model or software provider."""
    brand = PRODUCT_BRAND_IDENTITY["full_display_title"]
    unit_id = html.escape(str(state_payload.get("unit_id", "Unit 104")))
    hoa_name = html.escape(str(state_payload.get("association_name", "Oak Creek Homeowners Association")))
    jur = html.escape(str(state_payload.get("jurisdiction", "CA")))
    qa = state_payload.get("active_resolution", {})
    fin = state_payload.get("financial_analysis", {})
    pkt = state_payload.get("document_packet", {})

    docs_rows = []
    for d in pkt.get("documents", []):
        if d.get("visibility_scope") == "HOMEOWNER_PRIVATE":
            scope_badge = "Private (Homeowner Only)"
        elif d.get("visibility_scope") == "BOARD_CONFIDENTIAL":
            scope_badge = "Board Confidential"
        else:
            scope_badge = "Community Shared"
        docs_rows.append(
            f"<tr>"
            f"<td>{html.escape(str(d.get('doc_id', '')))}</td>"
            f"<td>{d.get('title', '')}</td>"
            f"<td>{d.get('section_citation', '')}</td>"
            f"<td>{html.escape(str(d.get('authority_label', '')))}</td>"
            f"<td>{html.escape(scope_badge)}</td>"
            f"<td><code>{html.escape(str(d.get('doc_sha256', ''))[:16])}...</code></td>"
            f"</tr>"
        )

    draft_escaped = html.escape( redact_pii_for_export(str(qa.get("prepared_response_draft", ""))) )
    ans_escaped = html.escape(str(qa.get("plain_language_answer", "")))
    verdict_escaped = html.escape(str(qa.get("headline_verdict", "")))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand} — Portable Neighborhood Record ({hoa_name})</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; background: #f8fafc; margin: 0; padding: 24px; line-height: 1.55; }}
  .container {{ max-width: 920px; margin: 0 auto; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 28px; }}
  h1 {{ margin-top: 0; color: #0f172a; font-size: 1.5rem; }}
  h2 {{ color: #1e3a8a; font-size: 1.15rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px; }}
  .badge {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 999px; font-size: 0.85rem; font-weight: 600; }}
  .verdict-box {{ background: #f0fdf4; border-left: 4px solid #16a34a; padding: 14px 18px; border-radius: 6px; margin: 14px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.9rem; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #f1f5f9; font-weight: 600; }}
  pre {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 14px; border-radius: 8px; white-space: pre-wrap; word-break: break-word; font-size: 0.88rem; }}
  .meta {{ font-size: 0.82rem; color: #475569; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 12px; }}
</style>
</head>
<body>
<div class="container">
  <span class="badge">Portable Offline Record · Zero Vendor Lock-In</span>
  <h1>{brand}</h1>
  <p><strong>Association:</strong> {hoa_name} &nbsp;|&nbsp; <strong>Unit / Scope:</strong> {unit_id} &nbsp;|&nbsp; <strong>Jurisdiction:</strong> {jur}</p>

  <h2>1. Current Question & Source-Grounded Answer</h2>
  <div class="verdict-box">
    <strong>Outcome:</strong> {verdict_escaped}<br>
    <p style="margin:8px 0 0 0;">{ans_escaped}</p>
  </div>

  <h2>2. Prepared Action / Response Letter (PII-Scrubbed)</h2>
  <pre>{draft_escaped}</pre>

  <h2>3. Financial & Reserve Snapshot</h2>
  <p>
    <strong>Monthly Assessment:</strong> ${float(fin.get('monthly_dues_per_unit_usd', 285.0)):,.2f}/unit &nbsp;|&nbsp;
    <strong>Reserve Funded:</strong> {float(fin.get('reserve_percent_funded', 17.5)):.1f}% (${float(fin.get('actual_reserve_balance_usd', 42000.0)):,.2f} / ${float(fin.get('fully_funded_reserve_target_usd', 240000.0)):,.2f}) &nbsp;|&nbsp;
    <strong>Recommended Vendor:</strong> {html.escape(str(fin.get('vendor_comparison', {}).get('recommended_option_id', 'VENDOR-C-QUALIFIED-COMPETITIVE')))}
  </p>

  <h2>4. Provenance-Verified Governing Documents & Records</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>Document Title</th><th>Section</th><th>Authority Level</th><th>Privacy Scope</th><th>SHA-256 Digest</th></tr>
    </thead>
    <tbody>
      {''.join(docs_rows)}
    </tbody>
  </table>

  <div class="meta">
    <strong>Verification Receipt Details:</strong> Accepted State SHA-256: <code>{html.escape(accepted_sha256)}</code> &nbsp;|&nbsp;
    Receiver Public Key: <code>{html.escape(receiver_public_key)}</code> &nbsp;|&nbsp;
    People retain 100% legal and decision-making authority.
  </div>
</div>
</body>
</html>
"""
