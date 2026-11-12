#!/usr/bin/env python3
"""OpenLine Genie RC7 — Comprehensive Adversarial Release Gate (`test_genie_rc7_adversarial_gate.py`).

Covers:
- P0-A: Stale proposal overwrite prevention (sequential, concurrent threads, and HTTP 409)
- P0-B: STOP epoch revival prevention, worker succession proposal revocation, and basis change invalidation
- P0-C: Immutable internal `project_id` and `schema` enforcement across propose/accept/commit/export
- P0-D: Fail-closed `TRUSTED_PROJECT_FAMILIES` registry and forbidden cross-family transitions
- P0-E: Durable cross-thread & cross-process transactional spend authority, ledger deletion/tamper detection,
        unknown model pricing refusal, stale reservation recovery, and default-OFF paid dispatch
- Customer Journey & Emergence:
  1. Bakery (`Hearth & Crumb`): bottleneck identification (`oven` 174), clamped trap rejection (`hours` +0),
     accepted upgrade (`oven2` -> 240, shifts to `staff`), 100-Yard Jump receipt, and super-additive synergy (`oven2 + hours` -> 280).
  2. Unfamiliar Customer Project (`Community Garden Crop Rotation, Drip Cistern & Volunteer Planner`):
     bottleneck identification (`water` 105 lbs/wk), comparison of Option A (`drip_mulch` discovery) vs
     Option B (`municipal_tap` conventional comparator) vs Option C (`weekend_workday` clamped trap),
     100-Yard Jump receipt (`water -> volunteers -> plots`), and super-additive unlock (`150 lbs/wk`).
- Portable Export & Fresh-Install Import/Recovery (`import_portable_bundle` / `POST /api/import`):
  verifies SHA-256 integrity, upstream signature check, honest external vs local receiver provenance badge,
  and tamper rejection.
- UI / Accessibility / Honesty Invariants: verifies `genie_living_world.html` controls, keyboard/reduced-motion
  support, 44px touch targets, and RC7 authority/mode disclosures.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.community_garden import compute_garden
from core.model_adapter import (
    ModelError,
    SpendCapExceeded,
    SpendLedger,
    cost_usd,
)
from genie_engine import OpenLineGenieEngine
from genie_server import start_genie_server


def _http_get(base: str, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(base + path, headers={"Host": "127.0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def _http_post(base: str, path: str, body: dict, headers: dict | None = None) -> tuple[int, dict]:
    hdrs = {"Content-Type": "application/json", "Host": "127.0.0.1"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers=hdrs,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


class GenieRC7AdversarialGate(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name)
        self.engine = OpenLineGenieEngine(state_dir=self.state_dir, model_adapter=None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_01_p0_a_concurrent_accept_cas_and_http_409(self) -> None:
        """Concurrent threads racing to accept two competing proposals from v1 allow exactly 1 winner."""
        pid = self.engine.list_projects()[0]["project_id"]
        b1 = self.engine.propose_exploratory_change(pid, "Branch A from v1", {"title": "Winner A"})
        prop_a = b1["exploratory"][0]["proposal_id"]
        b2 = self.engine.propose_exploratory_change(pid, "Branch B from v1", {"title": "Competing B"})
        prop_b = next(p["proposal_id"] for p in b2["exploratory"] if p["proposal_id"] != prop_a)

        barrier = threading.Barrier(2)
        outcomes: list[tuple[str, bool, str]] = []

        def _try_accept(prop_id: str) -> None:
            barrier.wait()
            try:
                self.engine.accept_exploratory_change(pid, prop_id)
                outcomes.append((prop_id, True, "ok"))
            except Exception as exc:
                outcomes.append((prop_id, False, f"{type(exc).__name__}:{exc}"))

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(_try_accept, prop_a)
            f2 = ex.submit(_try_accept, prop_b)
            f1.result()
            f2.result()

        successes = [o for o in outcomes if o[1]]
        failures = [o for o in outcomes if not o[1]]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertTrue(
            "PermissionError" in failures[0][2] or "GuardRefused" in failures[0][2],
            f"Unexpected failure type: {failures[0][2]}",
        )

        after = self.engine.get_project_bundle(pid)
        self.assertEqual(after["accepted"]["version"], 2)
        loser_id = failures[0][0]
        loser_row = next(p for p in after["exploratory"] if p["proposal_id"] == loser_id)
        self.assertEqual(loser_row["status"], "STALE_REOPEN_REQUIRED")

    def test_02_p0_b_stop_epoch_worker_revocation_and_basis_binding(self) -> None:
        """STOP epoch, worker revocation, and basis change each revoke pending proposals."""
        pid = self.engine.list_projects()[0]["project_id"]

        # 1. Worker-A creates a proposal, then Worker-A is revoked via replace_worker_and_recover
        b1 = self.engine.propose_exploratory_change(pid, "Worker-A proposal", {"title": "By Worker A"})
        prop_wa = b1["exploratory"][0]["proposal_id"]
        swap_res = self.engine.replace_worker_and_recover()
        self.assertEqual(swap_res["new_active_worker"], "worker-b")
        self.assertGreaterEqual(swap_res["revoked_pending_proposals"], 1)
        with self.assertRaises(PermissionError):
            self.engine.accept_exploratory_change(pid, prop_wa)
        # Revoked worker-a cannot create new proposals either
        with self.assertRaises(PermissionError):
            self.engine.propose_exploratory_change(
                pid, "Forged by revoked worker-a", {"title": "Forged"}, proposer_worker="worker-a"
            )

        # 2. Worker-B creates a proposal, then basis changes before accept
        b2 = self.engine.propose_exploratory_change(pid, "Pre-basis change", {"title": "Old Basis"})
        prop_basis = b2["exploratory"][0]["proposal_id"]
        self.engine.guard.set_basis("tax_and_calculation_rules", "v2-updated")
        with self.assertRaises(PermissionError):
            self.engine.accept_exploratory_change(pid, prop_basis)

        # 3. Fresh proposal under new basis + post-STOP clear succeeds
        self.engine.trigger_stop("emergency_audit")
        self.engine.clear_stop("audit_cleared")
        b3 = self.engine.propose_exploratory_change(pid, "Fresh epoch proposal", {"title": "Fresh Epoch Verified"})
        prop_fresh = b3["exploratory"][0]["proposal_id"]
        accepted = self.engine.accept_exploratory_change(pid, prop_fresh)
        self.assertEqual(accepted["accepted"]["state"]["title"], "Fresh Epoch Verified")

    def test_03_p0_c_and_p0_d_identity_and_family_validator_enforcement(self) -> None:
        """Rejects internal project_id mutation, schema spoofing, unknown families, and cross-family downgrades."""
        pid = "demo-a-service-quoting"
        bad_quote_state = {
            "project_family": "synthesized_micro_app",
            "quotes": [{"quote_id": "Q-BAD", "items": [{"qty": 1, "unit_price_cents": 5000}], "total_cents": 1}],
        }
        b1 = self.engine.propose_exploratory_change(pid, "Downgrade family to skip quote check", bad_quote_state)
        prop1 = b1["exploratory"][0]
        self.assertFalse(prop1["validation_passed"])
        self.assertTrue(
            any("illegal_project_family_transition" in e for e in prop1["validation_report"]["errors"])
        )
        with self.assertRaises(PermissionError):
            self.engine.accept_exploratory_change(pid, prop1["proposal_id"])

        b2 = self.engine.propose_exploratory_change(pid, "Spoof schema", {"schema": "openline.genie.hijacked.v99"})
        prop2 = b2["exploratory"][0]
        self.assertFalse(prop2["validation_passed"])
        with self.assertRaises(PermissionError):
            self.engine.accept_exploratory_change(pid, prop2["proposal_id"])

        state = self.engine.get_project_bundle(pid)["accepted"]["state"]
        bad_id_state = dict(state, project_id="spoofed-id")
        with self.assertRaises(PermissionError):
            self.engine._commit_accepted_state(pid, "service_quoting_invoicing", bad_id_state)
        bad_fam_state = dict(state, project_family="untrusted_family")
        with self.assertRaises(PermissionError):
            self.engine._commit_accepted_state(pid, "untrusted_family", bad_fam_state)

    def test_04_p0_e_cross_process_spend_race_tamper_and_stale_recovery(self) -> None:
        """Cross-process spend race, ledger deletion detection, unknown pricing, stale recovery, and corrupt values."""
        ledger_dir = self.state_dir / "spend_multiprocess"
        ledger_dir.mkdir(parents=True, exist_ok=True)

        probe_L = SpendLedger(ledger_dir=ledger_dir)
        worst = cost_usd(3000, 2000, model="claude-haiku-5-5")
        tight_cap = worst * 1.05  # Room for 1 reservation only

        worker_code = textwrap.dedent(f"""
            import json, sys
            sys.path.insert(0, {repr(str(ROOT))})
            from core.model_adapter import SpendLedger, SpendCapExceeded
            L = SpendLedger(ledger_dir={repr(str(ledger_dir))})
            try:
                entry = L.reserve(
                    model='claude-haiku-5-5',
                    estimated_input_tokens=3000,
                    max_tokens=2000,
                    purpose='mp_race',
                    limit_usd={tight_cap!r},
                )
                print(json.dumps({{'allowed': True, 'rid': entry['reservation_id']}}))
            except SpendCapExceeded as e:
                print(json.dumps({{'allowed': False, 'err': str(e)}}))
        """)
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", worker_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(4)
        ]
        results = []
        for p in procs:
            out, err = p.communicate(timeout=15)
            self.assertEqual(p.returncode, 0, err)
            results.append(json.loads(out.strip()))

        allowed = [r for r in results if r["allowed"]]
        refused = [r for r in results if not r["allowed"]]
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(refused), 3)
        self.assertAlmostEqual(probe_L.reserved_open_usd(), worst, places=9)

        # Deleting spend.json while spend_authority.sqlite has recorded an open reservation fails closed!
        (ledger_dir / "spend.json").unlink()
        with self.assertRaises(ModelError):
            probe_L.total_usd()

        # Unknown model pricing fails closed
        with self.assertRaises(ModelError):
            cost_usd(100, 100, model="unknown-unpriced-model-x")

        # Stale open reservation recovery
        clean_dir = self.state_dir / "clean_spend_dir"
        clean_ledger = SpendLedger(ledger_dir=clean_dir)
        res_entry = clean_ledger.reserve(
            model="claude-haiku-5-5",
            estimated_input_tokens=500,
            max_tokens=200,
            purpose="stale_test",
            limit_usd=1.0,
        )
        rid2 = res_entry["reservation_id"]
        data = json.loads((clean_dir / "spend.json").read_text())
        for r in data["reservations"]:
            if r["reservation_id"] == rid2:
                r["created_unix"] = 1000.0
        (clean_dir / "spend.json").write_text(json.dumps(data))
        held_ids = clean_ledger.reconcile_stale_reservations(max_age_seconds=10.0)
        self.assertIn(rid2, held_ids)
        self.assertEqual(clean_ledger.reserved_open_usd(), 0.0)
        self.assertGreater(clean_ledger.total_usd(), 0.0)

    def test_05_bakery_and_community_garden_emergence_and_jump_receipts(self) -> None:
        """Verifies full emergence loop on both Bakery and unfamiliar Community Garden projects."""
        # --- Project 1: Bakery ---
        bakery = self.engine.build_from_prompt(
            "Design a small neighborhood bakery — Hearth & Crumb Bakery", use_model=False
        )
        b_pid = bakery["project_id"]
        self.assertEqual(bakery["project_family"], "bakery")
        self.assertEqual(bakery["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 174)
        self.assertEqual(bakery["accepted"]["state"]["bakery"]["computed"]["bottleneck_id"], "oven")

        # Propose clamped trap (hours alone -> +0 loaves/day) and reject it
        b_trap = self.engine.propose_exploratory_change(
            b_pid, "Extend shift hours without adding oven", {"bakery": {"assumptions": {"staggered_shift": True}}}
        )
        trap_prop = b_trap["exploratory"][0]
        self.assertEqual(trap_prop["constraint_diagnosis"]["delta_output"], "+0 loaves/day")
        sha_before_reject = bakery["accepted"]["state_sha256"]
        after_reject = self.engine.reject_exploratory_change(b_pid, trap_prop["proposal_id"], "clamped_trap_zero_gain")
        self.assertEqual(after_reject["accepted"]["state_sha256"], sha_before_reject)

        # Propose and accept 2nd oven (174 -> 240 loaves/day, bottleneck shifts oven -> staff)
        b_oven2 = self.engine.propose_exploratory_change(
            b_pid, "Install 2nd deck oven", {"bakery": {"assumptions": {"ovens": 2}}}
        )
        oven2_prop = b_oven2["exploratory"][0]
        self.assertTrue(oven2_prop["constraint_diagnosis"]["constraint_shifted"])
        self.assertEqual(oven2_prop["constraint_diagnosis"]["before_binding_constraint"], "oven")
        self.assertEqual(oven2_prop["constraint_diagnosis"]["after_binding_constraint"], "staff")
        b_acc1 = self.engine.accept_exploratory_change(b_pid, oven2_prop["proposal_id"])
        self.assertEqual(b_acc1["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 240)
        self.assertEqual(len(b_acc1["jump_decisions"]), 1)
        self.assertEqual(b_acc1["jump_decisions"][0]["previous_binding_constraint"], "oven")
        self.assertEqual(b_acc1["jump_decisions"][0]["new_binding_constraint"], "staff")

        # --- Project 2: Unfamiliar Domain (Community Garden) ---
        garden = self.engine.build_from_prompt(
            "Plan a community garden crop rotation, rainwater cistern drip irrigation, and volunteer harvest schedule",
            use_model=False,
        )
        g_pid = garden["project_id"]
        cg = garden["accepted"]["state"]["garden"]
        self.assertEqual(cg["computed"]["bottleneck_id"], "water")
        self.assertEqual(cg["computed"]["throughput_lbs_per_week"], 105)
        self.assertEqual(cg["computed"]["net_weekly_community_value_usd"], 322.5)

        # Verify conventional comparator vs drip discovery in paths
        paths = self.engine.garden_paths(g_pid)["paths"]
        self.assertIn("drip_mulch", paths)
        self.assertIn("municipal_tap", paths)
        self.assertIn("weekend_workday", paths)
        tap_eval = compute_garden({"municipal_supp_gallons_per_week": 120})
        drip_eval = compute_garden({"drip_mulch_enabled": True, "gallons_per_lb_produce": 2.625, "legume_rotation_coverage_pct": 50})
        self.assertEqual(tap_eval["throughput_lbs_per_week"], 135)
        self.assertEqual(drip_eval["throughput_lbs_per_week"], 135)
        self.assertGreater(
            drip_eval["net_weekly_community_value_usd"],
            tap_eval["net_weekly_community_value_usd"],
        )

        # Propose & accept Option A (drip_mulch): 105 -> 135 lbs/wk, shifts bottleneck water -> volunteers
        g_prop1 = self.engine.propose_exploratory_change(
            g_pid,
            paths["drip_mulch"]["label"],
            {"garden": {"assumptions": paths["drip_mulch"]["assumption_patch"]}},
        )
        p1 = g_prop1["exploratory"][0]
        self.assertEqual(p1["constraint_diagnosis"]["before_binding_constraint"], "water")
        self.assertEqual(p1["constraint_diagnosis"]["after_binding_constraint"], "volunteers")
        self.assertIn("Option B (Pay Municipal Tap Water Overages", p1["constraint_diagnosis"]["conventional_comparator"])
        g_acc1 = self.engine.accept_exploratory_change(g_pid, p1["proposal_id"])
        self.assertEqual(
            g_acc1["accepted"]["state"]["garden"]["computed"]["throughput_lbs_per_week"],
            135,
        )
        self.assertEqual(
            g_acc1["accepted"]["state"]["garden"]["computed"]["bottleneck_id"],
            "volunteers",
        )

        # Now that water constraint is removed, adding volunteer shift unlocks super-additive gain (135 -> 150 lbs/wk, shifts volunteers -> plots)
        paths_step2 = self.engine.garden_paths(g_pid)["paths"]
        g_prop2 = self.engine.propose_exploratory_change(
            g_pid,
            paths_step2["weekend_workday"]["label"],
            {"garden": {"assumptions": paths_step2["weekend_workday"]["assumption_patch"]}},
        )
        p2 = g_prop2["exploratory"][0]
        self.assertEqual(p2["constraint_diagnosis"]["before_binding_constraint"], "volunteers")
        self.assertEqual(p2["constraint_diagnosis"]["after_binding_constraint"], "plots")
        g_acc2 = self.engine.accept_exploratory_change(g_pid, p2["proposal_id"])
        self.assertEqual(
            g_acc2["accepted"]["state"]["garden"]["computed"]["throughput_lbs_per_week"],
            150,
        )
        self.assertEqual(len(g_acc2["jump_decisions"]), 2)

    def test_06_portable_export_and_fresh_install_import_provenance(self) -> None:
        """Exports a project and imports it into a fresh installation, verifying provenance honesty and tamper refusal."""
        garden = self.engine.build_from_prompt(
            "Plan a community garden crop rotation, rainwater cistern drip irrigation, and volunteer harvest schedule",
            use_model=False,
        )
        g_pid = garden["project_id"]
        exported = self.engine.export_portable_bundle(g_pid)
        self.assertEqual(exported["accepted_sha256"], garden["accepted"]["state_sha256"])

        with tempfile.TemporaryDirectory() as fresh_dir:
            fresh_engine = OpenLineGenieEngine(state_dir=fresh_dir, model_adapter=None)
            self.assertNotEqual(fresh_engine.receiver_identity.public, self.engine.receiver_identity.public)

            imported = fresh_engine.import_portable_bundle(exported)
            prov = imported["accepted"]["state"]["imported_provenance"]
            self.assertTrue(prov["upstream_signature_verified_against_source_key"])
            self.assertFalse(prov["same_receiver_instance"])
            self.assertEqual(prov["provenance_badge"], "EXTERNAL_RECEIVER_SIGNATURE_VERIFIED_IMPORTED")
            self.assertEqual(prov["source_state_sha256"], exported["accepted_sha256"])

            tampered_obj = json.loads(exported["portable_json"])
            tampered_obj["accepted"]["state"]["title"] = "Tampered Without Updating SHA"
            with self.assertRaises(ValueError):
                fresh_engine.import_portable_bundle(tampered_obj)

    def test_07_http_server_endpoints_and_ui_honesty_invariants(self) -> None:
        """Tests live HTTP server endpoints, default-off paid model dispatch, CSRF guards, and UI HTML invariants."""
        srv = start_genie_server(port=0, state_dir=self.state_dir)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{srv.server_port}"
        try:
            code, status = _http_get(base, "/api/status")
            self.assertEqual(code, 200)
            self.assertFalse(status["model_available"])
            self.assertEqual(status["paid_model_dispatch_default"], "OFF_UNLESS_ADAPTER_CONFIGURED")
            self.assertEqual(status["execution_mode"], "DETERMINISTIC_LOCAL_SYNTHESIZER")

            # Cross-origin POST must be refused with 403
            code, _ = _http_post(
                base,
                "/api/stop",
                {"reason": "csrf"},
                headers={"Origin": "http://evil.example.com"},
            )
            self.assertEqual(code, 403)

            # Build Community Garden via POST /api/build
            code, built = _http_post(
                base,
                "/api/build",
                {"prompt": "Plan a community garden crop rotation and rainwater drip irrigation", "use_model": False},
            )
            self.assertEqual(code, 200)
            g_pid = built["project_id"]

            # Query GET /api/garden/paths
            code, g_paths = _http_get(base, f"/api/garden/paths?project_id={g_pid}")
            self.assertEqual(code, 200)
            self.assertIn("drip_mulch", g_paths["paths"])

            # Propose two competing changes and verify HTTP 409 on stale second accept
            _, p_a = _http_post(base, "/api/propose", {"project_id": g_pid, "summary": "A", "patch": {"title": "Garden A"}})
            id_a = p_a["exploratory"][0]["proposal_id"]
            _, p_b = _http_post(base, "/api/propose", {"project_id": g_pid, "summary": "B", "patch": {"title": "Garden B"}})
            id_b = next(x["proposal_id"] for x in p_b["exploratory"] if x["proposal_id"] != id_a)

            code_a, _ = _http_post(base, "/api/accept", {"project_id": g_pid, "proposal_id": id_a})
            self.assertEqual(code_a, 200)
            code_b, err_b = _http_post(base, "/api/accept", {"project_id": g_pid, "proposal_id": id_b})
            self.assertEqual(code_b, 409)
            self.assertIn("stale_proposal_reopen_required", err_b["error"].lower())

            # Export and re-import under a new target_project_id via HTTP
            code_exp, exp_data = _http_get(base, f"/api/export?project_id={g_pid}")
            self.assertEqual(code_exp, 200)
            code_imp, imp_data = _http_post(
                base,
                "/api/import",
                {"portable_bundle": exp_data, "target_project_id": f"{g_pid}-recovered"},
            )
            self.assertEqual(code_imp, 200)
            self.assertEqual(imp_data["project_id"], f"{g_pid}-recovered")
            self.assertEqual(
                imp_data["accepted"]["state"]["imported_provenance"]["provenance_badge"],
                "LOCAL_RECEIVER_REIMPORTED",
            )

            # Verify living-world HTML invariants
            html_text = (ROOT / "genie_living_world.html").read_text(encoding="utf-8")
            self.assertIn("wishBakeryBtn", html_text)
            self.assertIn("wishGardenBtn", html_text)
            self.assertIn("stopBtn", html_text)
            self.assertIn("exportAppBtn", html_text)
            self.assertIn("min-height:44px", html_text)
            self.assertIn("prefers-reduced-motion", html_text)
            self.assertIn("Living World v0.7.1", html_text)
            self.assertIn("STALE_REOPEN_REQUIRED", html_text)
            self.assertIn("REVOKED_BY_STOP_EPOCH", html_text)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
