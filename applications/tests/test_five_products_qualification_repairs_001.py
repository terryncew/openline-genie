#!/usr/bin/env python3
"""Regression tests for the five-app qualification repairs (FINAL SHIP & CLOSEOUT 001).

Covers, with fresh unfamiliar inputs:
1. Advocate: a missed deadline is flagged (not silently passed) when the live
   stage path evaluates it against today's date.
2. Advocate: a user-typed statement labelled VERIFIED_FACT is downgraded to an
   allegation because no document backs it (no self-certification by hashing
   the statement itself).
3. Advocate: a plausible-looking invented legal citation is rejected as a rule
   because it is not in the pinned, independently checked set.
4. Civic: a proposal whose P10/P50/P90 costs are out of order is disqualified
   and cannot be recommended.
5. Energy: every NPC also matches an independent recompute from the option's
   own reported flows (within rounding of the 2-decimal intermediates).
6. Server: the loopback bind is honoured and /api read endpoints refuse a
   foreign Host.
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
import sys

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core.civilization_applications import (
    compute_appeal_deadlines_fail_closed,
    evaluate_public_benefits_appeal,
    evaluate_community_energy_cooperative,
    evaluate_public_infrastructure_accountability,
)
from genie_server import start_genie_server


def _http(base: str, method: str, path: str, body: dict | None = None, headers: dict | None = None):
    hdrs = dict(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        hdrs.setdefault("Content-Type", "application/json")
        hdrs.setdefault("Origin", base)
    req = urllib.request.Request(base + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


class TestQualificationRepairs001(unittest.TestCase):
    def test_01_missed_deadline_flagged_not_silently_passed(self) -> None:
        dl = compute_appeal_deadlines_fail_closed(
            "2026-10-01", "2026-10-05", "2026-10-06", as_of_date_iso="2026-11-14"
        )
        self.assertEqual(dl["status"], "DEADLINE_PASSED_FAIL_CLOSED")
        self.assertTrue(dl["conservative_standard_appeal_deadline_passed"])
        self.assertTrue(dl["requires_human_date_verification"])
        ev = evaluate_public_benefits_appeal(
            include_missing_medical_cert=True,
            custom_notice_date="2026-10-01",
            override_postmark_date="2026-10-05",
            custom_receipt_date="2026-10-06",
            as_of_date_iso="2026-11-14",
        )
        self.assertFalse(ev["filing_gate"]["ready_for_human_authorized_filing"])
        self.assertTrue(
            any("deadline_passed" in r for r in ev["filing_gate"]["blocking_reasons"])
        )

    def test_02_future_deadline_still_ready(self) -> None:
        ev = evaluate_public_benefits_appeal(
            include_missing_medical_cert=True,
            custom_notice_date="2026-11-01",
            override_postmark_date="2026-11-04",
            custom_receipt_date="2026-11-06",
            as_of_date_iso="2026-11-14",
        )
        self.assertEqual(ev["deadline_analysis"]["status"], "DEADLINE_VERIFIED_DETERMINISTIC")
        self.assertTrue(ev["filing_gate"]["ready_for_human_authorized_filing"])

    def test_03_plausible_invented_rule_rejected(self) -> None:
        ev = evaluate_public_benefits_appeal(
            include_missing_medical_cert=True,
            extra_rules=[{
                "rule_id": "RULE-RESTORE-2026",
                "title": "Emergency Benefit Restoration Authority",
                "source_citation": "42 CFR 999.99 / Cal. Welf. & Inst. Code 11999.1",
                "effective_from": "2024-01-01",
                "effective_to": "2028-12-31",
                "applies_to_reason": "REASON-1-MEDICAL-DEVICE-ACTIVE",
            }],
        )
        valid = [r["rule_id"] for r in ev["epistemic_triage"]["valid_rules"]]
        self.assertNotIn("RULE-RESTORE-2026", valid)
        invalid = [r["rule_id"] for r in ev["epistemic_triage"]["invalid_rules"]]
        self.assertIn("RULE-RESTORE-2026", invalid)

    def test_04_inverted_civic_percentiles_disqualified(self) -> None:
        ev = evaluate_public_infrastructure_accountability(extra_proposals=[{
            "option_id": "PROP-USER-BAD-ORDER",
            "title": "Unfamiliar test proposal with inverted cost percentiles",
            "capex_musd": 1.1,
            "npc_p10_musd": 1.9,
            "npc_p50_musd": 1.2,
            "npc_p90_musd": 1.0,
            "school_zone_setback_m": 120.0,
            "property_line_noise_dba": 44.0,
            "co2_10yr_tonnes": 12.0,
            "blackout_72h_outage_hours": 0.0,
            "blackout_120h_outage_hours": 0.0,
            "low_income_bill_delta_usd_mo": 1.25,
            "max_turbidity_rating_ntu": 55.0,
        }])
        self.assertNotEqual(ev["recommended_proposal_id"], "PROP-USER-BAD-ORDER")
        disq = {d["option_id"]: d["violations"] for d in ev["disqualified_proposals"]}
        self.assertIn("PROP-USER-BAD-ORDER", disq)
        self.assertTrue(any("ordering_invalid" in v for v in disq["PROP-USER-BAD-ORDER"]))

    def test_05_energy_npc_crosscheck_from_reported_flows(self) -> None:
        ev = evaluate_community_energy_cooperative(custom_inputs={
            "household_units": 7,
            "monthly_elec_kwh": 913.0,
            "peak_tariff_usd_kwh": 0.61,
            "offpeak_tariff_usd_kwh": 0.19,
            "solar_array_kw_ac": 3.7,
            "discount_rate_pct": 6.54321,
            "monthly_hot_water_thermal_kwh": 311.0,
        })
        par = ev["conventional_calculator_parity"]
        self.assertLessEqual(par["reported_flows_crosscheck_max_diff_usd"], 0.05)
        self.assertIn("same implementation", par["independent_calculator"])

    def test_06_self_certified_claim_downgraded_via_live_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv = start_genie_server(port=0, state_dir=tmp, use_model=False)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_port}"
            try:
                code, _ = _http(base, "GET", "/api/five_products/state")
                self.assertEqual(code, 200)
                code, raw = _http(base, "POST", "/api/five_products/stage", {
                    "product_key": "advocate",
                    "payload": {"new_claim": {
                        "statement": "The agency director personally promised full restoration in a phone call nobody recorded.",
                        "category": "VERIFIED_FACT",
                        "source_doc_id": "NO-DOCUMENT-EXISTS.txt",
                    }},
                })
                self.assertEqual(code, 200, raw[:300])
                resp = json.loads(raw)
                ev = resp["proposal"]["candidate_state"]["civilization_app"]["evaluation"]
                tri = ev["epistemic_triage"]
                mine_v = [c for c in tri["verified_facts"] if "personally promised" in c.get("statement", "")]
                mine_a = [c for c in tri["unverified_allegations"] if "personally promised" in c.get("statement", "")]
                self.assertEqual(mine_v, [])
                self.assertEqual(len(mine_a), 1)
                self.assertEqual(mine_a[0].get("effective_category"), "DOWNGRADED_TO_ALLEGATION")
                self.assertFalse(tri["can_promote_to_accepted"])
            finally:
                srv.shutdown()

    def test_07_missed_deadline_flagged_via_live_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv = start_genie_server(port=0, state_dir=tmp, use_model=False)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_port}"
            try:
                code, _ = _http(base, "GET", "/api/five_products/state")
                self.assertEqual(code, 200)
                code, raw = _http(base, "POST", "/api/five_products/stage", {
                    "product_key": "advocate",
                    "payload": {
                        "notice_date": "2026-10-01",
                        "postmark_date": "2026-10-05",
                        "receipt_date": "2026-10-06",
                        "custom_notice_text": "Notice dated 2026-10-01. Benefits termination effective 2026-10-20.",
                        "include_missing_medical_cert": True,
                    },
                })
                self.assertEqual(code, 200, raw[:300])
                resp = json.loads(raw)
                ev = resp["proposal"]["candidate_state"]["civilization_app"]["evaluation"]
                self.assertEqual(ev["deadline_analysis"]["status"], "DEADLINE_PASSED_FAIL_CLOSED")
                self.assertFalse(ev["filing_gate"]["ready_for_human_authorized_filing"])
            finally:
                srv.shutdown()

    def test_08_server_binds_loopback_and_refuses_foreign_host_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv = start_genie_server(port=0, state_dir=tmp, use_model=False, host="127.0.0.1")
            self.assertEqual(srv.server_address[0], "127.0.0.1")
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_port}"
            try:
                code, _ = _http(base, "GET", "/api/five_products/state")
                self.assertEqual(code, 200)
                code, raw = _http(base, "GET", "/api/five_products/state",
                                  headers={"Host": "evil.example:9999"})
                self.assertEqual(code, 403, raw[:200])
                code, raw = _http(base, "GET", "/api/export?project_id=product-1-energy-commons",
                                  headers={"Host": "evil.example:9999"})
                self.assertEqual(code, 403, raw[:200])
            finally:
                srv.shutdown()
        with self.assertRaises(ValueError):
            start_genie_server(port=0, host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
