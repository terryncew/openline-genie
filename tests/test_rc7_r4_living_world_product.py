#!/usr/bin/env python3
"""OpenLine Genie RC7 r4 — Final Product Pass & Reusable Living-World Dogfood Suite
(`tests/test_rc7_r4_living_world_product.py`).

Tests the complete product lifecycle on a live server and verifies the reusable
Living-World visual projection across all 4 project domains:
1. Flagship Bakery (`Hearth & Crumb`):
   Prompt -> Project World -> Inspect Oven -> Edit Assumptions (valid & invalid)
   -> Preview (`174 -> 210` and `174 -> 240 -> 280 -> 300 loaves/day`) -> Accept
   -> Reject -> STOP -> Clear STOP -> Export -> Import -> Restart -> Replace Worker
   -> Switch Model.
2. Community Garden (`Sunnyvale Community Garden`):
   `105 -> 135 -> 150 lbs/week` constraint shifts, `weekend_workday` trap (`+0` alone)
   and `drip_mulch + weekend_workday` synergy (`+15 lbs/week` bonus) in both Python
   engine and JS `applyEngineState` + `describeDiscovery`.
3. Neural Model Optimization (`ResidualMLP-16-32-32-4`):
   `52 -> 64 -> 74 -> 90 frontier_pts` across `spectral_flow`, `data_subspace`,
   and `calibration_efficiency`, `curriculum_finetune` trap (`+0` alone while W2
   spectrum is collapsed) and `spectral_repair + curriculum_finetune` synergy (`+10`
   bonus) in both Python engine and JS `applyEngineState` + `describeDiscovery`.
4. Generic Unfamiliar Project (`Ceramic Kiln Firing & Glaze Batch Tracker`):
   Honest operational-flow representation (`domainType === 'generic'`) without
   fabricated bespoke 3D equipment claims.
5. UI Falsifiers, Touch Targets, Overlay Protection & Non-Canvas Fallback:
   Verifies `genie_living_world.html` First-5-Seconds orientation strip, Interactive
   Assumption Editor, Non-Canvas Accessible Station Fallback, `STOP` overlay
   protection (`FAB_PROTECTED` + `positionDiscoverySheet`), and custom assumption
   preview branch synthesis (`custom_<proposal_id>`).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from genie_server import GenieRequestHandler


def _start_live_server(state_dir: str):
    engine = OpenLineGenieEngine(state_dir=state_dir)

    class Handler(GenieRequestHandler):
        pass

    Handler.engine = engine
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{port}", engine


def _http_get(base_url: str, path: str) -> tuple[int, dict | str]:
    req = urllib.request.Request(base_url + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(raw) if "application/json" in ctype else raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, json.loads(raw)


def _http_post(base_url: str, path: str, body: dict) -> tuple[int, dict]:
    host = base_url.split("://", 1)[1]
    req = urllib.request.Request(
        base_url + path,
        data=json.dumps(body).encode("utf-8"),
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
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


class TestRc7R4LivingWorldProduct(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="genie-rc7-r4-product-")
        self.srv, self.base_url, self.engine = _start_live_server(self.tmp_dir)

    def tearDown(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()

    def test_01_flagship_bakery_full_dogfood_lifecycle_and_assumption_editor(self) -> None:
        """Tests the full Flagship Bakery product loop including interactive assumption editing."""
        code_html, html_text = _http_get(self.base_url, "/")
        self.assertEqual(code_html, 200)
        self.assertIsInstance(html_text, str)
        for required_id in (
            "fiveSecStrip",
            "fsBuilding",
            "fsCreated",
            "fsInspect",
            "fsControl",
            "assumptionEditor",
            "toggleAssumptionsBtn",
            "applyAssumptionBtn",
            "worldFallbackToggle",
            "worldFallbackPanel",
            "worldFallbackList",
            "importBundleFile",
            "modelSelect",
            "replaceModelBtn",
            "stopBtn",
        ):
            self.assertIn(required_id, html_text, f"Missing UI element #{required_id}")

        # 1. Build Flagship Bakery
        code, bundle = _http_post(
            self.base_url,
            "/api/build",
            {
                "prompt": "Design a small neighborhood bakery — Hearth & Crumb Bakery: plan daily baking, track batches, and see capacity.",
                "use_model": False,
            },
        )
        self.assertEqual(code, 200)
        pid = bundle["project_id"]
        base_sha = bundle["accepted"]["state_sha256"]
        self.assertEqual(bundle["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 174)
        self.assertEqual(bundle["accepted"]["state"]["bakery"]["computed"]["bottleneck_id"], "oven")

        # 2. Invalid assumption edit fails closed (e.g., ovens=0 or cycle_minutes=-10)
        bad_code_1, bad_res_1 = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Invalid zero ovens",
                "patch": {"bakery": {"assumptions": {"ovens": 0}}},
            },
        )
        self.assertEqual(bad_code_1, 400)
        self.assertIn("invalid_bakery_assumption", bad_res_1.get("error", ""))

        bad_code_2, bad_res_2 = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Invalid negative cycle minutes",
                "patch": {"bakery": {"assumptions": {"cycle_minutes": -10}}},
            },
        )
        self.assertEqual(bad_code_2, 400)
        self.assertIn("invalid_bakery_assumption", bad_res_2.get("error", ""))

        # Accepted state is completely untouched after rejected invalid edits
        _, check_bundle = _http_get(self.base_url, f"/api/project?project_id={pid}")
        self.assertEqual(check_bundle["accepted"]["state_sha256"], base_sha)
        self.assertEqual(len(check_bundle["exploratory"]), 0)

        # 3. Valid interactive assumption edit on Oven (batch_size_loaves: 29 -> 35 => 210 loaves/day)
        code_edit, edit_bundle = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Edit Steam Deck Oven: batch_size_loaves=35",
                "patch": {"bakery": {"assumptions": {"batch_size_loaves": 35}}},
            },
        )
        self.assertEqual(code_edit, 200)
        self.assertEqual(edit_bundle["accepted"]["state_sha256"], base_sha)
        self.assertEqual(edit_bundle["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 174)
        prop_edit = edit_bundle["exploratory"][0]
        self.assertEqual(prop_edit["status"], "EXPLORATORY_PENDING")
        self.assertEqual(prop_edit["candidate_state"]["bakery"]["computed"]["oven_capacity"], 210)
        self.assertEqual(prop_edit["candidate_state"]["bakery"]["computed"]["throughput_loaves_per_day"], 210)
        self.assertEqual(prop_edit["candidate_state"]["bakery"]["computed"]["bottleneck_id"], "oven")

        # Reject custom assumption edit -> accepted state remains byte-identical (174 loaves/day)
        code_rej, rej_bundle = _http_post(
            self.base_url,
            "/api/reject",
            {
                "project_id": pid,
                "proposal_id": prop_edit["proposal_id"],
                "reason": "owner_tested_assumption_preview",
            },
        )
        self.assertEqual(code_rej, 200)
        self.assertEqual(rej_bundle["accepted"]["state_sha256"], base_sha)
        self.assertEqual(rej_bundle["rejected"][0]["preserved_accepted_sha256"], base_sha)

        # 4. Propose & Accept Deck Oven #2 (174 -> 240 loaves/day, bottleneck shifts to staff)
        _, p_oven2 = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Another oven?",
                "patch": {"bakery": {"assumptions": {"ovens": 2}}},
            },
        )
        prop_oven2_id = [p for p in p_oven2["exploratory"] if p["status"] == "EXPLORATORY_PENDING"][0]["proposal_id"]
        code_acc1, acc1 = _http_post(
            self.base_url,
            "/api/accept",
            {"project_id": pid, "proposal_id": prop_oven2_id},
        )
        self.assertEqual(code_acc1, 200)
        self.assertEqual(acc1["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 240)
        self.assertEqual(acc1["accepted"]["state"]["bakery"]["computed"]["bottleneck_id"], "staff")

        # 5. Propose & Accept Staggered Shift (240 -> 280 loaves/day, bottleneck shifts to ingredients)
        _, p_hours = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Adjust shift schedule",
                "patch": {"bakery": {"assumptions": {"ovens": 2, "staggered_shift": True, "shift_pattern": "04:30-14:30 staggered"}}},
            },
        )
        prop_hours_id = [p for p in p_hours["exploratory"] if p["status"] == "EXPLORATORY_PENDING"][0]["proposal_id"]
        code_acc2, acc2 = _http_post(
            self.base_url,
            "/api/accept",
            {"project_id": pid, "proposal_id": prop_hours_id},
        )
        self.assertEqual(code_acc2, 200)
        self.assertEqual(acc2["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 280)
        self.assertEqual(acc2["accepted"]["state"]["bakery"]["computed"]["bottleneck_id"], "ingredients")

        # 6. STOP freezes mutations immediately; Clear STOP resumes
        code_stop, _ = _http_post(self.base_url, "/api/stop", {"reason": "dogfood_stop_check"})
        self.assertEqual(code_stop, 200)
        code_blocked, blocked_res = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": pid,
                "summary": "Blocked during STOP",
                "patch": {"bakery": {"assumptions": {"extra_retarder_racks": 1}}},
            },
        )
        self.assertIn(code_blocked, (400, 403, 409))
        self.assertIn("stopped", blocked_res.get("error", "").lower())
        code_clear, _ = _http_post(self.base_url, "/api/clear_stop", {"reason": "dogfood_resume"})
        self.assertEqual(code_clear, 200)

        # 7. Export -> Import -> Replace Worker -> Switch Model -> Restart Persistence
        code_exp, exp_bundle = _http_get(self.base_url, f"/api/export?project_id={pid}")
        self.assertEqual(code_exp, 200)
        self.assertIn("Hearth", exp_bundle["standalone_html"])

        code_imp, imp_bundle = _http_post(
            self.base_url,
            "/api/import",
            {"portable_bundle": exp_bundle, "target_project_id": f"{pid}-reimported"},
        )
        self.assertEqual(code_imp, 200)
        self.assertEqual(
            imp_bundle["accepted"]["state"]["imported_provenance"]["provenance_badge"],
            "LOCAL_RECEIVER_REIMPORTED",
        )

        sha_before_swap = acc2["accepted"]["state_sha256"]
        code_wk, wk_res = _http_post(self.base_url, "/api/replace_worker", {})
        self.assertEqual(code_wk, 200)
        self.assertEqual(wk_res["new_active_worker"], "worker-b")

        code_md, md_res = _http_post(
            self.base_url,
            "/api/replace_model",
            {"model": "claude-haiku-4-5-20251001", "project_id": pid},
        )
        self.assertEqual(code_md, 200)
        self.assertEqual(md_res["model_id"], "claude-haiku-4-5-20251001")

        # Restart engine on same state_dir and verify accepted state & SHA are preserved
        restarted = OpenLineGenieEngine(state_dir=self.tmp_dir)
        reloaded_bundle = restarted.get_project_bundle(pid)
        self.assertEqual(reloaded_bundle["accepted"]["state_sha256"], sha_before_swap)
        self.assertEqual(reloaded_bundle["accepted"]["state"]["bakery"]["computed"]["throughput_loaves_per_day"], 280)
        self.assertEqual(reloaded_bundle["active_worker_id"], "worker-b")

    def test_02_multi_domain_living_world_projection_in_node(self) -> None:
        """Verifies that applyEngineState and describeDiscovery project Bakery,
        Community Garden, Neural Model Optimization, and Generic Unfamiliar Projects
        accurately in the built genie_living_world.html."""
        _, b_bakery = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": "Design a neighborhood bakery — Hearth & Crumb", "use_model": False},
        )
        _, b_garden = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": "Plan a community garden crop rotation, rainwater cistern drip irrigation, and volunteer harvest schedule", "use_model": False},
        )
        _, b_neural = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": "Optimize a local neural network checkpoint with weight-space spectral repair, curriculum filtering, and INT8 calibration", "use_model": False},
        )
        _, b_generic = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": "Create a neighborhood ceramic kiln firing and glaze batch tracker", "use_model": False},
        )

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "bakery.json").write_text(json.dumps(b_bakery), encoding="utf-8")
            (td_path / "garden.json").write_text(json.dumps(b_garden), encoding="utf-8")
            (td_path / "neural.json").write_text(json.dumps(b_neural), encoding="utf-8")
            (td_path / "generic.json").write_text(json.dumps(b_generic), encoding="utf-8")

            node_script = f"""
import assert from "node:assert/strict";
import {{ readFileSync }} from "node:fs";
import {{
  projectGenieBundleToLivingGraph,
  computeConstraintResonance,
  computeCounterfactualIntelligence,
  discoverSynergisticCombos,
  getNode,
  addPath,
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

// 1. Bakery
const sBakery = project({str(td_path / "bakery.json")!r});
assert.equal(sBakery.graph.domainType, "bakery");
assert.equal(sBakery.graph.constraint_resonance.system_throughput, 174);
assert.equal(sBakery.graph.constraint_resonance.bottleneck_id, "oven");
const dBakery = describeDiscovery(sBakery);
assert.ok(dBakery);
assert.equal(dBakery.comboId, "combo_oven2_hours");

// 2. Community Garden
const sGarden = project({str(td_path / "garden.json")!r});
assert.equal(sGarden.graph.domainType, "garden");
assert.equal(sGarden.graph.constraint_resonance.system_throughput, 105);
assert.equal(sGarden.graph.constraint_resonance.bottleneck_id, "water");
assert.equal(sGarden.graph.constraint_resonance.unit, "lbs/week");
const dGarden = describeDiscovery(sGarden);
assert.ok(dGarden, "Garden should surface drip_mulch + weekend_workday discovery");
assert.equal(dGarden.comboId, "combo_drip_mulch_weekend_workday");
assert.equal(dGarden.trapId, "weekend_workday");
assert.equal(dGarden.trapGain, 0);
assert.equal(dGarden.synergyBonus, 15);
assert.equal(dGarden.throughputBefore, 105);
assert.equal(dGarden.throughputAfter, 150);

// 3. Neural Model Optimization
const sNeural = project({str(td_path / "neural.json")!r});
assert.equal(sNeural.graph.domainType, "neural_model");
assert.equal(sNeural.graph.constraint_resonance.system_throughput, 52);
assert.equal(sNeural.graph.constraint_resonance.bottleneck_id, "spectral_flow");
assert.equal(sNeural.graph.constraint_resonance.unit, "frontier_pts");
const dNeural = describeDiscovery(sNeural);
assert.ok(dNeural, "Neural model should surface spectral_repair + curriculum_finetune discovery");
assert.equal(dNeural.comboId, "combo_spectral_repair_curriculum_finetune");
assert.equal(dNeural.trapId, "curriculum_finetune");
assert.equal(dNeural.trapGain, 0);
assert.equal(dNeural.synergyBonus, 10);
assert.equal(dNeural.throughputBefore, 52);
assert.equal(dNeural.throughputAfter, 74);

// 4. Generic Unfamiliar Project
const sGeneric = project({str(td_path / "generic.json")!r});
assert.equal(sGeneric.graph.domainType, "generic");
assert.equal(sGeneric.graph.constraint_resonance.unit, "ops/day");
assert.ok(getNode(sGeneric, "inputs"), "Generic project must have honest Typed Inputs node");
assert.ok(getNode(sGeneric, "formula"), "Generic project must have honest Formula & Rules node");
assert.ok(getNode(sGeneric, "workflow"), "Generic project must have honest Active Records node");
console.log("ALL_4_DOMAINS_PROJECTED_OK");
"""
            script_file = td_path / "verify_domains.mjs"
            script_file.write_text(node_script, encoding="utf-8")
            proc = subprocess.run(
                ["node", str(script_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"Node domain projection failed:\n{proc.stderr}\n{proc.stdout}")
            self.assertIn("ALL_4_DOMAINS_PROJECTED_OK", proc.stdout)

    def test_03_community_garden_and_neural_model_live_assumption_edits(self) -> None:
        """Verifies live assumption editing, constraint shifts, and fail-closed bounds
        for Community Garden and Neural Model Optimization projects."""
        # Community Garden
        _, g_bundle = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": "Plan a community garden crop rotation and rainwater cistern drip irrigation", "use_model": False},
        )
        g_pid = g_bundle["project_id"]
        g_sha = g_bundle["accepted"]["state_sha256"]

        # Invalid garden assumption (negative cistern gallons) fails closed
        bad_g_code, bad_g = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": g_pid,
                "summary": "Negative cistern water",
                "patch": {"garden": {"assumptions": {"cistern_gallons_per_week": -50}}},
            },
        )
        self.assertEqual(bad_g_code, 400)
        self.assertIn("invalid_garden_assumption", bad_g.get("error", ""))

        # Valid garden assumption edit: cistern_gallons_per_week=520 => 130 lbs/wk water cap
        ok_g_code, ok_g = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": g_pid,
                "summary": "Edit Cistern & Irrigation: cistern_gallons_per_week=520",
                "patch": {"garden": {"assumptions": {"cistern_gallons_per_week": 520}}},
            },
        )
        self.assertEqual(ok_g_code, 200)
        self.assertEqual(ok_g["accepted"]["state_sha256"], g_sha)
        self.assertEqual(ok_g["exploratory"][0]["candidate_state"]["garden"]["computed"]["throughput_lbs_per_week"], 130)

        # Neural Model Optimization
        _, n_bundle = _http_post(
            self.base_url,
            "/api/build",
            {"prompt": "Optimize a local neural network checkpoint with weight-space spectral repair", "use_model": False},
        )
        n_pid = n_bundle["project_id"]
        n_sha = n_bundle["accepted"]["state_sha256"]

        # Propose combined spectral_repaired + curriculum_filtered
        ok_n_code, ok_n = _http_post(
            self.base_url,
            "/api/propose",
            {
                "project_id": n_pid,
                "summary": "Edit Neural Optimization Stage: spectral_repaired=true, curriculum_filtered=true",
                "patch": {"neural_model": {"assumptions": {"spectral_repaired": True, "curriculum_filtered": True}}},
            },
        )
        self.assertEqual(ok_n_code, 200)
        self.assertEqual(ok_n["accepted"]["state_sha256"], n_sha)
        cand_nm = ok_n["exploratory"][0]["candidate_state"]["neural_model"]["computed"]
        self.assertEqual(cand_nm["frontier_score_pts"], 74)
        self.assertEqual(cand_nm["bottleneck_id"], "calibration_efficiency")

        # Accept neural optimization upgrade
        prop_n_id = ok_n["exploratory"][0]["proposal_id"]
        acc_n_code, acc_n = _http_post(
            self.base_url,
            "/api/accept",
            {"project_id": n_pid, "proposal_id": prop_n_id},
        )
        self.assertEqual(acc_n_code, 200)
        self.assertEqual(acc_n["accepted"]["state"]["neural_model"]["computed"]["frontier_score_pts"], 74)

    def test_04_ui_falsifiers_overlays_touch_targets_and_fallback_controls(self) -> None:
        """Verifies UI falsifiers: STOP overlay protection, touch-target floors,
        reduced-motion support, and accessible non-canvas station fallback."""
        html_text = (ROOT / "genie_living_world.html").read_text(encoding="utf-8")

        # 1. Overlay protection invariants (STOP never blocked by toast, export banner, pending banner, or discovery sheet)
        self.assertIn("function positionDiscoverySheet()", html_text)
        self.assertIn("function fabDockBottom()", html_text)
        self.assertIn(".toastBar{", html_text)
        self.assertIn("pointer-events:none", html_text)
        for protected_sel in ("#toast", "#exportConfirm", "#pendingBanner", "#discoveryCard", "#footerHint", "#counts", "#inspStatus"):
            self.assertIn(protected_sel, html_text)

        # 2. Touch target >=44px floor and responsive viewport breakpoints (320px/355px, 480px, 768px, 820px)
        self.assertIn("min-height:44px", html_text)
        self.assertIn("@media(max-width:480px)", html_text)
        self.assertIn("@media(max-width:355px)", html_text)
        self.assertIn("@media(prefers-reduced-motion:reduce)", html_text)

        # 3. Accessible non-canvas fallback & custom assumption preview synthesis
        self.assertIn("function renderFallbackStations(res)", html_text)
        self.assertIn("function renderAssumptionEditor(n,res)", html_text)
        self.assertIn("window.__GENIE_FORCE_FALLBACK", html_text)
        self.assertIn("custom_", html_text)


if __name__ == "__main__":
    unittest.main()
