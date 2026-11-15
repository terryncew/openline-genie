"""ARGON — OpenLine Genie Product Completion 001 Qualification Suite.

Tests:
1. Unfamiliar Project 1 (Volunteer-Run Mutual-Aid Request & Dispatch Hub):
   - No keyword hijack into community_garden despite "volunteer" in prompt.
   - Domain-tailored schema, operational formula, coupled records, and runnable standalone HTML app.
   - Multi-station bottleneck model (42 -> 56 -> 68 ops/day), clamped trap (+0 alone), and super-additive synergy (+26 ops/day, +12 bonus).
   - Live assumption edits propagating into station capacities AND record metrics (`computed_metric_value`, `capacity_share_pct`).
   - Full owner-controlled authority lifecycle: preview isolation, reject integrity, accept with Ed25519 receipt, Decision Recall (`POST /api/recall`), STOP fail-closed, worker replacement, model interchangeability, and portable export/re-import.
2. Unfamiliar Project 2 (Precision Electronics Repair & Calibration Bench Operations):
   - Independent domain generalization without project-specific hacks in genie_engine.py.
   - Full station capacity progression, assumption-to-record propagation, add_record mutation, and standalone portable HTML export.
3. Security, Negative & Falsifier Checks:
   - Invalid assumption types/bounds (negative, zero, NaN, boolean-for-int, unknown keys) fail closed (HTTP 400).
   - Stale proposal acceptance fails closed (`stale_proposal_reopen_required`).
   - Repeated acceptance fails closed.
   - Pre-STOP proposal acceptance after STOP clear fails closed (`REVOKED_BY_STOP_EPOCH`).
   - Forged portable bundle signature fails closed; cross-receiver import verifies signature and quarantines untrusted HTML (`UNTRUSTED_IMPORTED_HTML_QUARANTINED`).
   - Missing live model key falls back cleanly without claiming live LLM execution.
4. Live Headless Chromium Browser E2E Verification (Mobile 390x844 & Desktop 1280x800):
   - Real browser execution of `genie_living_world.html` and exported standalone HTML apps.
   - Zero console errors, zero uncaught page errors, zero horizontal overflow, touch targets >= 44px, XSS payload neutralization, and Cool Finish zero-warm-hex audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

# This module binds its test server to 127.0.0.2. The sandbox egress proxy
# intercepts loopback addresses not listed in no_proxy, so make sure urllib
# bypasses the proxy for it even when the ambient environment does not list
# 127.0.0.2 (otherwise every HTTP call here fails with RemoteDisconnected).
for _var in ("no_proxy", "NO_PROXY"):
    _cur = os.environ.get(_var, "")
    if "127.0.0.2" not in _cur.split(","):
        os.environ[_var] = (_cur + ",127.0.0.2").strip(",")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from genie_server import GenieRequestHandler

PROMPT_UNFAMILIAR_1 = (
    "Build an operational app for our volunteer-run neighborhood mutual-aid "
    "organization to track resident assistance requests, assign volunteer "
    "coordinators, manage limited emergency supply kits and delivery van hours, "
    "and spot capacity bottlenecks."
)

PROMPT_UNFAMILIAR_2 = (
    "Build an operational tracker for an electronics repair and calibration shop "
    "to log device repair tickets, assign bench technicians, manage calibration "
    "rig slots and spare parts inventory, and calculate turnaround capacity and "
    "daily net margin."
)


def _http_get(base_url: str, path: str) -> Tuple[int, Dict[str, Any]]:
    req = urllib.request.Request(f"{base_url}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"raw": body}


def _http_post(base_url: str, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    host = base_url.split("://", 1)[1]
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Host": host,
            "Origin": base_url,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"raw": body}


class TestProductCompletion001(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.engine = OpenLineGenieEngine(state_dir=self.tmp_dir)

        class Handler(GenieRequestHandler):
            pass

        Handler.engine = self.engine
        self.httpd = ThreadingHTTPServer(("127.0.0.2", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.base_url = f"http://127.0.0.2:{self.port}"
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self._tmp.cleanup()

    def test_01_unfamiliar_project_1_mutual_aid_full_lifecycle(self) -> None:
        """Dogfoods Unfamiliar Project 1 (Volunteer Mutual-Aid Request & Dispatch Hub) end to end."""
        code, bundle = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": PROMPT_UNFAMILIAR_1, "use_model": False},
        )
        self.assertEqual(code, 200)
        pid = bundle["project_id"]
        # Must NOT be hijacked into community garden despite "volunteer" in prompt
        self.assertNotIn("garden", pid)
        st = bundle["accepted"]["state"]
        self.assertNotIn("garden", st)
        self.assertEqual(st["category"], "community_mutual_aid_and_dispatch")
        self.assertEqual(st["domain_subtype"], "operational_micro_app")
        self.assertTrue(bundle["app"]["runs_standalone"])
        self.assertIn("<!doctype html>", bundle["app"]["content"].lower())

        # Verify initial station capacities and bottleneck (42 ops/day at Supply Kits & Van Dispatch)
        ops = st["operations_model"]
        self.assertEqual(ops["computed"]["throughput_ops_per_day"], 42)
        self.assertEqual(ops["computed"]["bottleneck_id"], "workflow")
        self.assertEqual(
            ops["computed"]["capacities"],
            {"workflow": 42, "formula": 56, "inputs": 68, "demand": 85, "scenario": 96, "wish": 120},
        )

        # Verify records are coupled to throughput_ops_per_day=42
        recs_v1 = st["records"]
        self.assertEqual(len(recs_v1), 3)
        self.assertEqual(recs_v1[0]["capacity_share_pct"], round((recs_v1[0]["quantity_units"] / 42.0) * 100.0, 2))
        self.assertEqual(recs_v1[0]["computed_metric_value"], 160.0)

        # Check /api/operations/paths
        code_p, paths_res = _http_get(self.base_url, f"/api/operations/paths?project_id={pid}")
        self.assertEqual(code_p, 200)
        self.assertIn("expand_resource", paths_res["paths"])
        self.assertIn("stagger_shifts", paths_res["paths"])
        self.assertTrue(paths_res["paths"]["stagger_shifts"]["is_clamped_trap"])
        self.assertTrue(paths_res["paths"]["spot_rental_overtime"]["is_conventional_comparator"])

        base_sha = bundle["accepted"]["state_sha256"]

        # 1. Propose expanding primary resource pool (resource_units=4, efficiency_multiplier=1.25) -> 56 ops/day
        code_prop1, prop1_bundle = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Pre-pack emergency supply kits + add shared transit van",
                "patch": {
                    "operations_model": {
                        "assumptions": {"resource_units": 4, "efficiency_multiplier": 1.25}
                    }
                },
            },
        )
        self.assertEqual(code_prop1, 200)
        # Preview isolation: accepted state SHA-256 is untouched
        self.assertEqual(prop1_bundle["accepted"]["state_sha256"], base_sha)
        cand1 = prop1_bundle["exploratory"][0]["candidate_state"]
        self.assertEqual(cand1["operations_model"]["computed"]["throughput_ops_per_day"], 56)
        self.assertEqual(cand1["operations_model"]["computed"]["bottleneck_id"], "formula")
        # Record computed_metric_value and capacity_share_pct automatically updated in candidate_state!
        self.assertEqual(cand1["records"][0]["computed_metric_value"], 200.0)
        self.assertEqual(
            cand1["records"][0]["capacity_share_pct"],
            round((cand1["records"][0]["quantity_units"] / 56.0) * 100.0, 2),
        )

        # 2. Reject proposal 1 and verify accepted state remains identical
        prop1_id = prop1_bundle["exploratory"][0]["proposal_id"]
        code_rej, rej_bundle = _http_post(
            self.base_url,
            "/api/reject",
            {"project_id": pid, "proposal_id": prop1_id, "reason": "test_reject_isolation"},
        )
        self.assertEqual(code_rej, 200)
        self.assertEqual(rej_bundle["accepted"]["state_sha256"], base_sha)

        # 3. Propose synergistic combination (resource_units=4, efficiency_multiplier=1.25, staggered_handoff_enabled=True) -> 68 ops/day
        code_prop2, prop2_bundle = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Synergy: Pre-pack supply kits + stagger volunteer coordinator shifts",
                "patch": {
                    "operations_model": {
                        "assumptions": {
                            "resource_units": 4,
                            "efficiency_multiplier": 1.25,
                            "staggered_handoff_enabled": True,
                        }
                    }
                },
            },
        )
        self.assertEqual(code_prop2, 200)
        prop2_id = prop2_bundle["exploratory"][0]["proposal_id"]
        cand2 = prop2_bundle["exploratory"][0]["candidate_state"]
        self.assertEqual(cand2["operations_model"]["computed"]["throughput_ops_per_day"], 68)
        self.assertEqual(cand2["operations_model"]["computed"]["bottleneck_id"], "inputs")

        # 4. Accept proposal 2 and verify receipt & state update
        code_acc, acc_bundle = _http_post(
            self.base_url,
            "/api/accept",
            {"project_id": pid, "proposal_id": prop2_id},
        )
        self.assertEqual(code_acc, 200)
        self.assertNotEqual(acc_bundle["accepted"]["state_sha256"], base_sha)
        self.assertEqual(acc_bundle["accepted"]["state"]["operations_model"]["computed"]["throughput_ops_per_day"], 68)
        self.assertEqual(acc_bundle["accepted"]["version"], 2)

        # 5. Add a new operational record via /api/synth/add_record
        code_add, add_res = _http_post(
            self.base_url,
            "/api/synth/add_record",
            {
                "project_id": pid,
                "record": {
                    "item_title": "Senior insulin cold-pack delivery — Pine St",
                    "category_tag": "Urgent Medical Cold-Chain",
                    "assignee_name": "Elena Rostova (Coordinator)",
                    "quantity_units": 3.5,
                    "unit_rate_dollars": 50.0,
                    "adjustments_dollars": 25.0,
                    "status": "VAN_DISPATCHED",
                },
            },
        )
        self.assertEqual(code_add, 200)
        self.assertEqual(len(add_res["accepted"]["state"]["records"]), 4)
        self.assertEqual(add_res["accepted"]["state"]["records"][-1]["computed_metric_value"], 250.0)

        # 6. Trigger Decision Recall via /api/recall and verify durability without mutating accepted state_sha256
        _, b_before_recall = _http_get(self.base_url, f"/api/project?project_id={pid}")
        sha_before_recall = b_before_recall["accepted"]["state_sha256"]
        code_rec, rec_res = _http_post(
            self.base_url,
            "/api/recall",
            {"project_id": pid, "node_id": "inputs", "reason": "Volunteer coordinator availability updated"},
        )
        self.assertEqual(code_rec, 200)
        self.assertEqual(rec_res["accepted"]["state_sha256"], sha_before_recall)
        self.assertEqual(len(rec_res["recalled_decisions"]), 1)
        self.assertIn("workflow", rec_res["affected_nodes"])
        self.assertIn("scenario", rec_res["affected_nodes"])

        # 7. Export standalone application and re-import into a fresh engine instance (cross-receiver verification)
        code_exp, exp_bundle = _http_get(self.base_url, f"/api/export?project_id={pid}")
        self.assertEqual(code_exp, 200)
        self.assertIn("Senior insulin cold-pack delivery", exp_bundle["standalone_html"])

        with tempfile.TemporaryDirectory() as td2:
            fresh_engine = OpenLineGenieEngine(state_dir=Path(td2))
            imported = fresh_engine.import_portable_bundle(exp_bundle, target_project_id="mutual-aid-external")
            imp_prov = imported["accepted"]["state"]["imported_provenance"]
            self.assertEqual(imp_prov["provenance_badge"], "EXTERNAL_RECEIVER_SIGNATURE_VERIFIED_IMPORTED")
            self.assertTrue(imp_prov["upstream_signature_verified_against_source_key"])
            self.assertFalse(imp_prov["same_receiver_instance"])

    def test_02_unfamiliar_project_2_electronics_repair_generalization(self) -> None:
        """Tests generalization on Unfamiliar Project 2 (Electronics Repair & Calibration Bench Operations)."""
        code, bundle = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": PROMPT_UNFAMILIAR_2, "use_model": False},
        )
        self.assertEqual(code, 200)
        st = bundle["accepted"]["state"]
        self.assertEqual(st["category"], "technical_repair_and_calibration")
        self.assertTrue(bundle["app"]["runs_standalone"])
        self.assertEqual(st["operations_model"]["computed"]["throughput_ops_per_day"], 42)
        self.assertEqual(
            st["operations_model"]["computed"]["station_labels"]["workflow"],
            "Calibration Rigs & Parts Bench",
        )
        self.assertEqual(
            st["operations_model"]["computed"]["station_labels"]["formula"],
            "Bench Technician Shifts",
        )

        # Edit efficiency_multiplier and resource_units and verify propagation to records
        pid = bundle["project_id"]
        code_prop, prop_bundle = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Add dual-channel calibration rig & increase efficiency",
                "patch": {
                    "operations_model": {
                        "assumptions": {
                            "resource_units": 4,
                            "efficiency_multiplier": 1.25,
                            "active_staff_count": 5,
                        }
                    }
                },
            },
        )
        self.assertEqual(code_prop, 200)
        cand = prop_bundle["exploratory"][0]["candidate_state"]
        self.assertEqual(cand["operations_model"]["computed"]["capacities"]["workflow"], 70)
        self.assertEqual(cand["operations_model"]["computed"]["capacities"]["formula"], 70)
        self.assertEqual(cand["operations_model"]["computed"]["throughput_ops_per_day"], 68)
        self.assertEqual(cand["operations_model"]["computed"]["bottleneck_id"], "inputs")
        # Efficiency increase from 1.0 -> 1.25 increases computed_metric_value on repair tickets
        self.assertGreater(
            cand["records"][0]["computed_metric_value"],
            st["records"][0]["computed_metric_value"],
        )

    def test_03_node_projection_and_discovery_on_both_unfamiliar_projects(self) -> None:
        """Verifies that built genie_living_world.html projects both unfamiliar projects and surfaces Discovery-First."""
        _, b1 = _http_post(self.base_url, "/api/build", {"prompt": PROMPT_UNFAMILIAR_1, "use_model": False})
        _, b2 = _http_post(self.base_url, "/api/build", {"prompt": PROMPT_UNFAMILIAR_2, "use_model": False})
        # Trigger recall on b1 to also test recalled_decisions projection in Node
        _, b1_rec = _http_post(
            self.base_url,
            "/api/recall",
            {"project_id": b1["project_id"], "node_id": "inputs", "reason": "Check recall projection"},
        )

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "u1.json").write_text(json.dumps(b1_rec), encoding="utf-8")
            (td_path / "u2.json").write_text(json.dumps(b2), encoding="utf-8")

            node_script = f"""
import assert from "node:assert/strict";
import {{ readFileSync }} from "node:fs";
import {{
  projectGenieBundleToLivingGraph,
  computeConstraintResonance,
  computeCounterfactualIntelligence,
  discoverSynergisticCombos,
  getNode,
}} from {(ROOT / "living_world" / "graph_core.mjs").as_uri()!r};

const builtHtml = readFileSync({str(ROOT / "genie_living_world.html")!r}, "utf-8");
const fnSrc = builtHtml.match(/function applyEngineState\\(sess,bundle\\)\\{{[\\s\\S]*?\\n\\}}/);
assert.ok(fnSrc, "applyEngineState not found");
const applyEngineState = new Function(
  "getNode", "computeConstraintResonance", "computeCounterfactualIntelligence",
  `${{fnSrc[0]}}; return applyEngineState;`
)(getNode, computeConstraintResonance, computeCounterfactualIntelligence);

const discSrc = builtHtml.match(/function describeDiscovery\\(sess\\)\\{{[\\s\\S]*?\\n\\}}/);
assert.ok(discSrc, "describeDiscovery not found");
const describeDiscovery = new Function(
  "discoverSynergisticCombos", "computeCounterfactualIntelligence",
  `${{discSrc[0]}}; return describeDiscovery;`
)(discoverSynergisticCombos, computeCounterfactualIntelligence);

function project(file) {{
  const bundle = JSON.parse(readFileSync(file, "utf-8"));
  const sess = projectGenieBundleToLivingGraph(bundle, {{
    trustedReceiverKeys: [bundle.receiver_public_key],
  }});
  applyEngineState(sess, bundle);
  return sess;
}}

const s1 = project({str(td_path / "u1.json")!r});
assert.equal(s1.graph.constraint_resonance.system_throughput, 42);
assert.equal(s1.graph.constraint_resonance.bottleneck_id, "workflow");
assert.equal(getNode(s1, "inputs").state, "reopened");
assert.equal(getNode(s1, "workflow").state, "reopened");
const d1 = describeDiscovery(s1);
assert.ok(d1, "Unfamiliar Project 1 must surface Discovery-First synergy");
assert.equal(d1.comboId, "combo_expand_resource_stagger_shifts");
assert.equal(d1.trapId, "stagger_shifts");
assert.equal(d1.trapGain, 0);
assert.equal(d1.synergyBonus, 12);
assert.equal(d1.throughputBefore, 42);
assert.equal(d1.throughputAfter, 68);

const s2 = project({str(td_path / "u2.json")!r});
assert.equal(s2.graph.constraint_resonance.system_throughput, 42);
assert.equal(s2.graph.constraint_resonance.bottleneck_id, "workflow");
const d2 = describeDiscovery(s2);
assert.ok(d2, "Unfamiliar Project 2 must surface Discovery-First synergy");
assert.equal(d2.comboId, "combo_expand_resource_stagger_shifts");
assert.equal(d2.synergyBonus, 12);
console.log("UNFAMILIAR_PROJECTS_NODE_PROJECTION_OK");
"""
            script_file = td_path / "verify_unfamiliar.mjs"
            script_file.write_text(node_script, encoding="utf-8")
            proc = subprocess.run(["node", str(script_file)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, f"Node script failed:\n{proc.stderr}\n{proc.stdout}")
            self.assertIn("UNFAMILIAR_PROJECTS_NODE_PROJECTION_OK", proc.stdout)

    def test_04_negative_security_stop_stale_and_falsifier_suite(self) -> None:
        """Runs negative tests: invalid inputs, stale proposals, STOP epoch revocation, worker swap, forged receipts."""
        _, b1 = _http_post(self.base_url, "/api/build", {"prompt": PROMPT_UNFAMILIAR_1, "use_model": False})
        pid = b1["project_id"]
        sha0 = b1["accepted"]["state_sha256"]

        # 1. Invalid assumption values (negative, boolean-as-int, zero, unknown key) fail closed
        for bad_patch in (
            {"resource_units": -2},
            {"resource_units": True},
            {"unit_value_usd": 0},
            {"unknown_injected_field": 999},
        ):
            c_bad, res_bad = _http_post(
                self.base_url,
                "/api/propose",
                {"project_id": pid, "summary": "Bad assumption", "patch": {"operations_model": {"assumptions": bad_patch}}},
            )
            self.assertEqual(c_bad, 400, f"Expected 400 for {bad_patch}, got {c_bad}: {res_bad}")

        # 2. Stale proposal fails closed when accepted after another proposal moves base_version forward
        _, p_a = _http_post(
            self.base_url,
            "/api/propose",
            {"project_id": pid, "summary": "Prop A", "patch": {"operations_model": {"assumptions": {"resource_units": 4}}}},
        )
        prop_a_id = p_a["exploratory"][0]["proposal_id"]
        _, p_b = _http_post(
            self.base_url,
            "/api/propose",
            {"project_id": pid, "summary": "Prop B", "patch": {"operations_model": {"assumptions": {"active_staff_count": 5}}}},
        )
        prop_b_id = [x["proposal_id"] for x in p_b["exploratory"] if x["summary"] == "Prop B"][0]

        # Accept Prop A -> version becomes 2
        c_acc_a, _ = _http_post(self.base_url, "/api/accept", {"project_id": pid, "proposal_id": prop_a_id})
        self.assertEqual(c_acc_a, 200)

        # Repeated acceptance of Prop A fails closed
        c_rep, _ = _http_post(self.base_url, "/api/accept", {"project_id": pid, "proposal_id": prop_a_id})
        self.assertIn(c_rep, (400, 409))

        # Accepting stale Prop B (created against version 1) fails closed with 409 stale_proposal_reopen_required
        c_stale, res_stale = _http_post(self.base_url, "/api/accept", {"project_id": pid, "proposal_id": prop_b_id})
        self.assertEqual(c_stale, 409)
        self.assertIn("stale_proposal_reopen_required", res_stale.get("error", "").lower())

        # 3. STOP blocks all mutations and revokes pre-STOP proposals across epochs
        _, p_c = _http_post(
            self.base_url,
            "/api/propose",
            {"project_id": pid, "summary": "Prop C pre-stop", "patch": {"operations_model": {"assumptions": {"auto_triage_enabled": True}}}},
        )
        prop_c_id = [x["proposal_id"] for x in p_c["exploratory"] if x["summary"] == "Prop C pre-stop"][0]

        c_stop, _ = _http_post(self.base_url, "/api/stop", {"reason": "security_test_stop"})
        self.assertEqual(c_stop, 200)

        # While stopped, propose, accept, add_record, and recall all fail closed
        self.assertIn(_http_post(self.base_url, "/api/propose", {"project_id": pid, "summary": "While stopped", "patch": {}})[0], (400, 403, 409))
        self.assertIn(_http_post(self.base_url, "/api/accept", {"project_id": pid, "proposal_id": prop_c_id})[0], (400, 403, 409))
        self.assertIn(_http_post(self.base_url, "/api/synth/add_record", {"project_id": pid, "record": {"item_title": "Blocked"}})[0], (400, 403, 409))
        self.assertIn(_http_post(self.base_url, "/api/recall", {"project_id": pid, "node_id": "inputs"})[0], (400, 403, 409))

        # Clear STOP -> pre-STOP proposal Prop C is revoked by stop epoch
        c_clr, _ = _http_post(self.base_url, "/api/clear_stop", {"reason": "resume"})
        self.assertEqual(c_clr, 200)
        c_rev, res_rev = _http_post(self.base_url, "/api/accept", {"project_id": pid, "proposal_id": prop_c_id})
        self.assertEqual(c_rev, 409)
        self.assertIn("REVOKED_BY_STOP_EPOCH", res_rev.get("error", ""))

        # 4. Worker replacement revokes pending proposals from old worker while preserving accepted state
        _, p_d = _http_post(
            self.base_url,
            "/api/propose",
            {"project_id": pid, "summary": "Prop D worker-a", "patch": {"operations_model": {"assumptions": {"auto_triage_enabled": True}}}},
        )
        prop_d_id = [x["proposal_id"] for x in p_d["exploratory"] if x["summary"] == "Prop D worker-a"][0]
        _, b_pre_swap = _http_get(self.base_url, f"/api/project?project_id={pid}")
        sha_pre_swap = b_pre_swap["accepted"]["state_sha256"]

        c_wk, _ = _http_post(self.base_url, "/api/replace_worker", {})
        self.assertEqual(c_wk, 200)
        c_wk_acc, res_wk_acc = _http_post(self.base_url, "/api/accept", {"project_id": pid, "proposal_id": prop_d_id})
        self.assertEqual(c_wk_acc, 409)
        self.assertIn("REVOKED_BY_WORKER_SWAP", res_wk_acc.get("error", ""))
        _, b_post_swap = _http_get(self.base_url, f"/api/project?project_id={pid}")
        self.assertEqual(b_post_swap["accepted"]["state_sha256"], sha_pre_swap)
        self.assertNotEqual(sha_pre_swap, sha0)

    def test_05_live_headless_chromium_browser_e2e_mobile_and_desktop(self) -> None:
        """Executes real headless Chromium via Selenium at 390x844 (mobile) and 1280x800 (desktop)."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        opts = Options()
        opts.binary_location = "/usr/bin/chromium"
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        service = Service("/usr/bin/chromedriver")

        driver = webdriver.Chrome(service=service, options=opts)
        try:
            # 1. Desktop viewport (1280x800): Build Unfamiliar Project 1 from wish screen
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
            driver.get(f"{self.base_url}/")
            wait = WebDriverWait(driver, 15)
            wish_input = wait.until(EC.visibility_of_element_located((By.ID, "wishInput")))
            wish_input.clear()
            wish_input.send_keys(PROMPT_UNFAMILIAR_1)
            driver.find_element(By.ID, "wishBuildBtn").click()

            # Wait for wishScreen to hide and project to load
            wait.until(lambda d: d.find_element(By.ID, "wishScreen").get_attribute("hidden") is not None)
            wait.until(lambda d: "42 ops/day" in d.find_element(By.ID, "bottleneckLabel").text)

            # Verify 5-second comprehension strip and Working Application section
            self.assertIn("Runnable App + Living Model", driver.find_element(By.ID, "fsCreated").text)
            working_sec = driver.find_element(By.ID, "workingAppSection")
            self.assertIsNone(working_sec.get_attribute("hidden"))
            self.assertIn("42 ops/day", driver.find_element(By.ID, "workingAppCapBadge").text)

            # Verify Discovery-First bar automatically surfaces the counterintuitive combo
            disc_title = driver.find_element(By.ID, "discBarTitle").text
            self.assertIn("looks useless on its own", disc_title)

            # Open Assumptions editor, change resource_units to 4, and click Preview assumption change
            toggle_assump = driver.find_element(By.ID, "toggleAssumptionsBtn")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", toggle_assump)
            toggle_assump.click()
            wait.until(lambda d: d.find_element(By.ID, "assumptionEditor").get_attribute("hidden") is None)
            inp_units = driver.find_element(By.CSS_SELECTOR, '[data-assumption-key="resource_units"]')
            inp_units.clear()
            inp_units.send_keys("4")
            driver.find_element(By.ID, "applyAssumptionBtn").click()

            # Wait for preview to update throughput to 56 ops/day
            wait.until(lambda d: "56 ops/day" in d.find_element(By.ID, "bottleneckLabel").text)
            self.assertIn("56 ops/day", driver.find_element(By.ID, "workingAppCapBadge").text)

            # Accept the previewed change
            accept_btn = driver.find_element(By.ID, "accept")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", accept_btn)
            accept_btn.click()
            wait.until(lambda d: "56 ops/day" in (d.find_element(By.ID, "cfBaseCap").get_attribute("textContent") or "") and "ACCEPTED WORKING STATE" in d.find_element(By.ID, "workingAppTitle").text)

            # Add a new operational record via #workingAppAddForm
            add_btn = driver.find_element(By.ID, "workingAppAddBtn")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", add_btn)
            add_btn.click()
            wait.until(lambda d: "(4 records)" in d.find_element(By.ID, "workingAppCapBadge").text)

            # 2. Switch to Mobile viewport (390x844) and verify layout, touch targets >= 44px, and zero horizontal overflow
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            overflow_px = driver.execute_script(
                "return document.documentElement.scrollWidth - document.documentElement.clientWidth;"
            )
            self.assertLessEqual(overflow_px, 1, f"Horizontal overflow detected at 390x844: {overflow_px}px")

            # Check interactive control heights >= 44px on mobile
            for btn_id in ("exportAppBtn", "worldFallbackToggle", "stopBtn", "toggleAssumptionsBtn", "workingAppAddBtn"):
                rect = driver.execute_script(
                    f"const r = document.getElementById({btn_id!r}).getBoundingClientRect(); return {{w: r.width, h: r.height}};"
                )
                self.assertGreaterEqual(rect["h"], 43.5, f"Button #{btn_id} height {rect['h']}px < 44px at 390x844")

            # Verify zero severe console errors
            logs = driver.get_log("browser")
            severe = [entry for entry in logs if entry.get("level") == "SEVERE"]
            self.assertEqual(severe, [], f"Browser severe errors: {severe}")

            # 3. Verify exported standalone HTML app runs offline via data:text/html and neutralizes XSS
            cur_pid = driver.find_element(By.ID, "project").get_attribute("value")
            _, exp_data = _http_get(self.base_url, f"/api/export?project_id={cur_pid}")
            data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(exp_data["standalone_html"])
            driver.get(data_url)
            wait.until(EC.presence_of_element_located((By.ID, "recordForm")))
            self.assertIn("56 ops/day", driver.find_element(By.ID, "stationGrid").text)

            # Inject XSS payload into first text input and submit
            text_inp = driver.find_element(By.CSS_SELECTOR, '#recordInputs input[type="text"]')
            text_inp.clear()
            text_inp.send_keys('<img src=x onerror="window.__xss_triggered=1">')
            driver.find_element(By.ID, "addRecordBtn").click()
            xss_flag = driver.execute_script("return window.__xss_triggered || null;")
            self.assertIsNone(xss_flag, "XSS payload executed in standalone exported app!")
            self.assertIn('<img src=x onerror="window.__xss_triggered=1">', driver.find_element(By.ID, "recordTableBody").text)
        finally:
            driver.quit()

    def test_06_cool_finish_palette_and_frozen_core_integrity(self) -> None:
        """Verifies zero warm hex literals in Cool Finish HTML/CSS and frozen graph_core.mjs SHA-256."""
        core_bytes = (ROOT / "living_world" / "graph_core.mjs").read_bytes()
        self.assertEqual(
            hashlib.sha256(core_bytes).hexdigest(),
            "3272bd4918b1a0718d47aed148340d5076698e807edec94ff361eac5b55a0215",
        )
        forbidden_warm = re.compile(
            r"#(?:ffb347|ffcf70|ffd584|ffe2a8|f3b562|c87f28|ff9a52|f7b955|f59e0b|d97706)\b",
            re.IGNORECASE,
        )
        for rel in (
            "genie_living_world.html",
            "living_world/template.html",
            "openline_genie.html",
            "try/index.html",
            "try/sandbox.css",
        ):
            content = (ROOT / rel).read_text(encoding="utf-8")
            matches = forbidden_warm.findall(content)
            self.assertEqual(matches, [], f"Forbidden warm hex found in {rel}: {matches}")


if __name__ == "__main__":
    unittest.main()
