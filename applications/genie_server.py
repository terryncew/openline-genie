#!/usr/bin/env python3
"""Local HTTP Server & REST API for OpenLine Genie (`genie_server.py`).

Security & Authority Scope (local single-operator tool):
- Binds strictly to loopback (`127.0.0.1` / `localhost`, normalized to
  `127.0.0.1`); any other host is refused at startup. The server never
  listens on a public interface.
- Host and Origin checks apply to mutating `POST` endpoints AND to `GET`
  `/api/*` read/export endpoints, so a web page on another site cannot
  read this computer's records through the browser.
- There is no login, password, session, or token. Anyone who can reach
  this port on this computer IS the operator, with full access to every
  workspace. The server therefore takes no identity or authority from
  the request: role, unit, and board-authorization values sent by a
  client are ignored, and every request is served as the local operator.
  Do not expose this port beyond this computer. Multi-household
  separation is NOT a supported deployment.
- The role-privacy boundary in the engine (`enforce_role_privacy_boundary`)
  still filters records for in-process callers that supply a role, but it
  is not an authentication boundary: it cannot distinguish callers over
  HTTP, because HTTP callers supply their own identity.
- Local authority boundary is within the local trusted OS user process; same-UID
  processes share filesystem access unless isolated by OS user/container.
- Paid model dispatch is OFF by default (`use_model=False`) unless explicitly
  enabled via `--enable-paid-model` or `GENIE_ENABLE_PAID_MODEL=1`.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from genie_engine import OpenLineGenieEngine
from openline_009_living_project import LivingProjectEngine
from core.model_adapter import TOTAL_CAP_USD, AnthropicAdapter

HERE = Path(__file__).resolve().parent
HTML_PATH = HERE / "openline_genie.html"
LIVING_WORLD_PATH = HERE / "genie_living_world.html"
FIVE_PRODUCTS_PATH = HERE / "openline_five_products.html"
NEIGHBORHOOD_PATH = HERE / "openline_neighborhood.html"

# Local single-operator identity, keyed by workspace. The HTTP layer takes
# no identity from the client: any role/unit/board-authorization fields in
# a request body are discarded and replaced with the operator identity for
# the requested workspace. There is no second user to impersonate over
# HTTP; anyone who reaches this loopback port is the operator.
_OPERATOR_IDENTITY: dict[str, dict[str, Any]] = {
    "homeowner": {
        "requester_role": "homeowner",
        "requester_unit_id": "UNIT-104",
        "target_unit_id": "UNIT-104",
        "board_authorized": True,
    },
    "board": {
        "requester_role": "board",
        "requester_unit_id": "BOARD-OAK-CREEK",
        "target_unit_id": "UNIT-104",
        "board_authorized": True,
    },
    "community": {
        "requester_role": "homeowner",
        "requester_unit_id": "UNIT-104",
        "target_unit_id": "UNIT-104",
        "board_authorized": True,
    },
}


def _force_operator_identity(workspace_key: str, payload: dict[str, Any]) -> None:
    """Discards client-supplied identity/authority and forces the local
    operator identity for `workspace_key`. Mutates `payload` in place."""
    for key in ("requester_role", "requester_unit_id", "target_unit_id", "board_authorized"):
        payload.pop(key, None)
    identity = _OPERATOR_IDENTITY.get(str(workspace_key or "homeowner").strip().lower())
    if identity is not None:
        payload.update(identity)




class GenieRequestHandler(BaseHTTPRequestHandler):
    engine: OpenLineGenieEngine

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _loopback_check(self) -> tuple[bool, str]:
        """Host/Origin check shared by POST and GET /api/* endpoints.

        Returns (True, "") when the request is a same-loopback request,
        otherwise (False, <plain error code for logs>).
        """
        host = self.headers.get("Host", "").split(":")[0].lower()
        if host not in {"localhost", "127.0.0.1", "127.0.0.2"}:
            return False, "loopback_host_required"
        origin = self.headers.get("Origin")
        if origin:
            expected = f"http://{self.headers.get('Host', '')}"
            if origin != expected:
                return False, "cross_origin_request_refused"
        return True, ""

    def _living_engine(self) -> LivingProjectEngine:
        if isinstance(self.engine, LivingProjectEngine):
            return self.engine
        GenieRequestHandler.engine = LivingProjectEngine(
            state_dir=self.engine.state_dir,
            model_adapter=self.engine.model_adapter,
        )
        return GenieRequestHandler.engine

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(403)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            ok, err = self._loopback_check()
            if not ok:
                self._send_json(403, {"error": err})
                return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path in ("/", "/index.html"):
            target = LIVING_WORLD_PATH if LIVING_WORLD_PATH.exists() else HTML_PATH
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path in ("/products", "/five_products", "/openline_five_products.html"):
            if not FIVE_PRODUCTS_PATH.exists():
                self._send_json(404, {"error": "openline_five_products.html not found"})
                return
            raw = FIVE_PRODUCTS_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path in ("/neighborhood", "/clearcovenant", "/openline_neighborhood.html"):
            if not NEIGHBORHOOD_PATH.exists():
                self._send_json(404, {"error": "openline_neighborhood.html not found"})
                return
            raw = NEIGHBORHOOD_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/neighborhood/state":
            try:
                # Local single-operator model: role, unit, and board
                # authorization sent by the client are ignored. Every
                # caller that reaches this loopback port is the operator,
                # so the state is always the operator's full view.
                self._send_json(
                    200,
                    self._living_engine().get_neighborhood_state(
                        requester_role="homeowner",
                        requester_unit_id="UNIT-104",
                        board_authorized=True,
                    ),
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/neighborhood/dossier":
            try:
                qs = parse_qs(parsed.query)
                wkey = qs.get("workspace", ["homeowner"])[0]
                res = self._living_engine().execute_neighborhood_action(wkey, "export_dossier", {})
                if qs.get("format", [""])[0] == "json":
                    self._send_json(200, res)
                    return
                raw = res["html"].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/advocate/case_packets":
            try:
                self._send_json(200, self._living_engine().get_advocate_case_packets_state())
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/advocate/case_packet/export":
            qs = parse_qs(parsed.query)
            cid = qs.get("case_id", ["CASE-001-BENEFITS-MISSING-DOC"])[0]
            redact = qs.get("redact_pii", ["0"])[0] in ("1", "true", "yes")
            try:
                self._send_json(200, self._living_engine().export_advocate_case_packet_bundle(cid, redact_pii_in_html=redact))
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
        if parsed.path == "/robotics":
            # Launcher entry for the Robotics Studio, which runs as its own
            # loopback-only server on port 8796 (see run_robotics_studio.sh
            # at the repository root). This route only links to it; it does
            # not proxy API calls or share Genie state.
            page = (
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<title>Robotics Studio — OpenLine Genie</title></head>"
                "<body style=\"font-family:system-ui,sans-serif;max-width:640px;margin:48px auto;padding:0 16px;line-height:1.5\">"
                "<h1>Robotics Studio</h1>"
                "<p>Design, simulate, evaluate, and transfer robot capabilities with explicit safety and authorization controls.</p>"
                "<p><strong>Simulation only.</strong> Results here are verified in simulation; they never establish physical hardware safety.</p>"
                "<p>Start the studio first, then open it:</p>"
                "<pre>./run_robotics_studio.sh</pre>"
                "<p><a href=\"http://127.0.0.1:8796/robotics\">Open the Robotics Studio on http://127.0.0.1:8796/robotics</a></p>"
                "<p><a href=\"/products\">Back to the applications launcher</a></p>"
                "</body></html>"
            )
            raw = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path in ("/ratchet", "/openline_ratchet_workbench_001.html"):
            r_path = HERE / "openline_ratchet_workbench_001.html"
            if not r_path.exists():
                self._send_json(404, {"error": "openline_ratchet_workbench_001.html not found"})
                return
            raw = r_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path in ("/semantic", "/openline_semantic_authority_workbench.html"):
            # Semantic Authority Bridge workbench (v1.2.0-rc1). Serves the
            # static workbench page only; it performs no computation.
            s_path = HERE / "openline_semantic_authority_workbench.html"
            if not s_path.exists():
                self._send_json(404, {"error": "openline_semantic_authority_workbench.html not found"})
                return
            raw = s_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/semantic/state":
            # Read-only: serves the precomputed receipts file shipped with
            # the release. A GET must not run the full suite or write
            # files; if the receipts have not been computed, the route
            # says so instead of computing them. (The candidate's
            # cache-miss path ran the suite and wrote the receipts JSON
            # from inside a GET; that write side effect is removed here.)
            # ?probe=recompile runs the local, read-only Boundary B
            # recompilation simulation against the shipped Energy Commons
            # ontology fixture and reports which default FK join edge was
            # selected. No files are written and no live service is used.
            try:
                qs = parse_qs(parsed.query)
                if qs.get("probe", [""])[0] == "recompile":
                    from core.semantic_authority_bridge import (
                        SemanticOntologyModel,
                        parse_ontology_yaml_or_json,
                        simulate_nvidia_semantic_recompilation,
                    )

                    fixture = HERE / "examples" / "ontologies" / "energy_commons_ossie.yaml"
                    if not fixture.exists():
                        self._send_json(404, {"error": "energy_commons_ossie.yaml fixture not found"})
                        return
                    before = SemanticOntologyModel(
                        parse_ontology_yaml_or_json(fixture.read_text(encoding="utf-8"))
                    )
                    after = simulate_nvidia_semantic_recompilation(before)
                    # Pair by relationship id: the recompiled model is built
                    # from the exported dict, whose relationships are sorted
                    # by id, so positional pairing would mismatch.
                    before_by_id = {rel["id"]: rel for rel in before.relationships}
                    changed = [
                        {
                            "relationship_id": rel["id"],
                            "source_table": rel["source_table"],
                            "target_table": rel["target_table"],
                            "source_column": rel["source_column"],
                            "is_default_before": before_by_id[rel["id"]]["is_default"],
                            "is_default_after": rel["is_default"],
                        }
                        for rel in after.relationships
                        if before_by_id[rel["id"]].get("is_default") != rel.get("is_default")
                    ]
                    self._send_json(
                        200,
                        {
                            "probe": "recompile",
                            "boundary": "B",
                            "fixture": "examples/ontologies/energy_commons_ossie.yaml",
                            "simulation": "local-only; no live NVIDIA service, no file writes",
                            "default_join_edges_changed": changed,
                        },
                    )
                    return
                rcpt_file = HERE / "SEMANTIC_AUTHORITY_001_RECEIPTS.json"
                if not rcpt_file.exists():
                    self._send_json(
                        503,
                        {
                            "status": "not_computed",
                            "error": (
                                "Semantic authority receipts have not been computed for "
                                "this install. Run `python3 run_semantic_authority_001.py` "
                                "inside applications/ to generate "
                                "SEMANTIC_AUTHORITY_001_RECEIPTS.json."
                            ),
                        },
                    )
                    return
                data = json.loads(rcpt_file.read_text(encoding="utf-8"))
                self._send_json(200, data)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/openline_genie.html":
            if not HTML_PATH.exists():
                self._send_json(404, {"error": "openline_genie.html not found"})
                return
            raw = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/five_products/state":
            try:
                self._send_json(200, self._living_engine().get_five_products_state())
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/five_products/civic/dossier":
            try:
                res = self._living_engine().execute_five_product_action("civic", "export_dossier", {})
                qs = parse_qs(parsed.query)
                if qs.get("format", [""])[0] == "json":
                    self._send_json(200, res)
                    return
                raw = res["html"].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/bakery/paths":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", [None])[0]
            try:
                self._send_json(200, self.engine.bakery_paths(pid))
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/garden/paths":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", [None])[0]
            try:
                self._send_json(200, self.engine.garden_paths(pid))
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/model_opt/paths":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", [None])[0]
            try:
                self._send_json(200, self.engine.model_optimization_paths(pid))
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/operations/paths":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", [None])[0]
            try:
                self._send_json(200, self.engine.operations_paths(pid))
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/projects":
            self._send_json(200, {"projects": self.engine.list_projects()})
            return
        if parsed.path == "/api/project":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", ["demo-a-service-quoting"])[0]
            try:
                self._send_json(200, self.engine.get_project_bundle(pid))
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/export":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", ["demo-a-service-quoting"])[0]
            try:
                out = self.engine.export_portable_bundle(pid)
                out = {
                    **out,
                    "content": out.get("standalone_html", ""),
                    "html": out.get("standalone_html", ""),
                    "filename": out.get("app_filename") or f"openline-genie-{pid}.html",
                }
                self._send_json(200, out)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/destinations":
            self._send_json(200, {"destinations": self.engine.list_destinations()})
            return
        if parsed.path == "/api/artifact":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", ["demo-a-service-quoting"])[0]
            version = qs.get("version", [None])[0]
            try:
                self._send_json(
                    200,
                    self.engine.get_app_version(pid, int(version) if version is not None else None),
                )
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/status":
            self._send_json(200, self.engine.get_status())
            return
        self._send_json(404, {"error": f"Unknown endpoint {parsed.path}"})

    def do_POST(self) -> None:
        # Local development only; prevent browser-origin CSRF from unrelated sites.
        ok, err = self._loopback_check()
        if not ok:
            self._send_json(403, {"error": err})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._send_json(415, {"error": "application_json_required"})
            return
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return
        if length < 0 or length > 1024 * 1024:
            self._send_json(413, {"error": "request_too_large"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            if not isinstance(body, dict):
                raise ValueError("object_required")
        except (ValueError, UnicodeError):
            self._send_json(400, {"error": "invalid_json_object"})
            return
        try:
            if parsed.path == "/api/five_products/stage":
                pkey = str(body.get("product_key", "energy"))
                payload = dict(body.get("payload", body))
                self._send_json(200, self._living_engine().stage_five_product_proposal(pkey, payload))
                return
            if parsed.path == "/api/five_products/action":
                pkey = str(body.get("product_key", "energy"))
                action = str(body.get("action", ""))
                payload = dict(body.get("payload", body))
                self._send_json(200, self._living_engine().execute_five_product_action(pkey, action, payload))
                return
            if parsed.path == "/api/neighborhood/stage":
                wkey = str(body.get("workspace_key", "homeowner"))
                payload = dict(body.get("payload", body))
                _force_operator_identity(wkey, payload)
                self._send_json(200, self._living_engine().stage_neighborhood_proposal(wkey, payload))
                return
            if parsed.path == "/api/neighborhood/action":
                wkey = str(body.get("workspace_key", "homeowner"))
                action = str(body.get("action", ""))
                payload = dict(body.get("payload", body))
                _force_operator_identity(wkey, payload)
                self._send_json(200, self._living_engine().execute_neighborhood_action(wkey, action, payload))
                return
            if parsed.path == "/api/advocate/case_packet/stage":
                cid = str(body.get("case_id", "CASE-001-BENEFITS-MISSING-DOC"))
                payload = dict(body.get("payload", body))
                self._send_json(200, self._living_engine().stage_advocate_case_packet_update(cid, payload))
                return
            if parsed.path == "/api/advocate/case_packet/import":
                zip_b64 = str(body.get("zip_base64", ""))
                target_pid = body.get("target_project_id")
                self._send_json(
                    200,
                    self._living_engine().import_advocate_case_packet_bundle(
                        zip_b64,
                        target_project_id=str(target_pid) if target_pid else None,
                    ),
                )
                return
            if parsed.path == "/api/build":
                prompt = str(body.get("prompt", "Build a free quoting and invoicing tool for my small service business."))
                use_model = bool(body.get("use_model", True))
                self._send_json(200, self.engine.build_from_prompt(prompt, use_model=use_model))
                return
            if parsed.path == "/api/import":
                payload = body.get("portable_bundle", body)
                target_pid = body.get("target_project_id")
                allow_overwrite = bool(body.get("allow_overwrite", False))
                self._send_json(
                    200,
                    self._living_engine().import_portable_bundle(
                        payload,
                        target_project_id=str(target_pid) if target_pid else None,
                        allow_overwrite=allow_overwrite,
                    ),
                )
                return
            if parsed.path == "/api/replace_model":
                model = str(body["model"])
                pid = body.get("project_id")
                res = self.engine.replace_model(model, project_id=str(pid) if pid else None)
                res = {
                    **res,
                    "model_id": res["model"],
                    "model_available": bool(
                        self.engine.model_adapter is not None
                        and getattr(self.engine.model_adapter, "available", False)
                    ),
                }
                self._send_json(200, res)
                return
            if parsed.path == "/api/register_destination":
                self._send_json(
                    200,
                    self.engine.register_destination(
                        str(body["destination"]), str(body["public_key"])
                    ),
                )
                return
            if parsed.path == "/api/close":
                closed = self.engine.close_project(str(body["project_id"]))
                bundle = self.engine.get_project_bundle(str(body["project_id"]))
                self._send_json(200, {**bundle, **closed})
                return
            if parsed.path == "/api/reopen":
                self._send_json(200, self.engine.reopen_project(str(body["project_id"])))
                return
            if parsed.path == "/api/propose":
                pid = str(body["project_id"])
                summary = str(body.get("summary", "Proposed interface or logic update"))
                patch = dict(body.get("patch", {}))
                self._send_json(200, self.engine.propose_exploratory_change(pid, summary, patch))
                return
            if parsed.path == "/api/reject":
                pid = str(body["project_id"])
                prop_id = str(body["proposal_id"])
                reason = str(body.get("reason", "user_rejected_proposal"))
                self._send_json(200, self._living_engine().reject_exploratory_change(pid, prop_id, reason))
                return
            if parsed.path == "/api/accept":
                pid = str(body["project_id"])
                prop_id = str(body["proposal_id"])
                self._send_json(200, self._living_engine().accept_exploratory_change(pid, prop_id))
                return
            if parsed.path == "/api/recall":
                pid = str(body["project_id"])
                node_id = str(body.get("node_id", "workflow"))
                reason = str(body.get("reason", "owner_decision_recall"))
                self._send_json(200, self._living_engine().recall_decision(pid, node_id, reason))
                return
            if parsed.path == "/api/demo_a/quote":
                self._send_json(
                    200,
                    self.engine.demo_a_add_or_update_quote(
                        customer_id=str(body.get("customer_id", "CUST-101")),
                        customer_name=str(body.get("customer_name", "Maria Chen")),
                        items=list(body.get("items", [])),
                        discount_pct=float(body.get("discount_pct", 0.0)),
                        tax_rate_pct=float(body.get("tax_rate_pct", 8.25)),
                        deposit_pct=float(body.get("deposit_pct", 25.0)),
                        notes=str(body.get("notes", "")),
                        quote_id=body.get("quote_id"),
                    ),
                )
                return
            if parsed.path == "/api/demo_a/convert_invoice":
                self._send_json(
                    200,
                    self.engine.demo_a_convert_quote_to_invoice(
                        quote_id=str(body["quote_id"]),
                        payment_terms=str(body.get("payment_terms", "Net 15")),
                    ),
                )
                return
            if parsed.path == "/api/demo_b/run":
                self._send_json(
                    200,
                    self.engine.demo_b_run_program(
                        level_num=int(body.get("level", 1)),
                        blocks=list(body.get("blocks", [])),
                        speed_mps=float(body.get("speed_mps", 0.55)),
                    ),
                )
                return
            if parsed.path == "/api/synth/add_record":
                self._send_json(
                    200,
                    self.engine.synthesized_app_add_record(
                        project_id=str(body["project_id"]),
                        record=dict(body.get("record", {})),
                    ),
                )
                return
            if parsed.path == "/api/stop":
                self._send_json(200, self.engine.trigger_stop(str(body.get("reason", "owner_stop"))))
                return
            if parsed.path == "/api/clear_stop":
                self._send_json(200, self.engine.clear_stop(str(body.get("reason", "owner_clear"))))
                return
            if parsed.path == "/api/replace_worker":
                res = self.engine.replace_worker_and_recover()
                res = {
                    **res,
                    "active_worker": res["new_active_worker"],
                    "accepted_preserved": True,
                }
                self._send_json(200, res)
                return
            self._send_json(404, {"error": f"Unknown POST endpoint {parsed.path}"})
        except Exception as exc:
            msg = str(exc)
            if (
                "stopped_at_epoch" in msg
                or "old_authority_dead" in msg
                or "REVOKED_BY_STOP_EPOCH" in msg
                or "REVOKED_BY_WORKER_SWAP" in msg
                or "STALE_REOPEN_REQUIRED" in msg
                or "stale_proposal" in msg
                or "GuardRefused" in type(exc).__name__
            ):
                self._send_json(409, {"error": msg})
            else:
                self._send_json(400, {"error": msg})


def start_genie_server(
    port: int = 8795,
    state_dir: str | Path | None = None,
    use_model: bool = False,
    host: str = "127.0.0.1",
) -> ThreadingHTTPServer:
    """Starts the local Genie HTTP server.

    Paid model dispatch (`use_model`) defaults to False ($0 local deterministic
    synthesizer) unless explicitly opted in by the owner.

    `host` must be a loopback address ("127.0.0.1" or "localhost", normalized
    to 127.0.0.1); any other value is refused. Previously this function
    ignored its caller's host and always bound 0.0.0.0.
    """
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"refusing_non_loopback_host:{host}")
    adapter = AnthropicAdapter(sub_budget_usd=TOTAL_CAP_USD) if use_model else None
    GenieRequestHandler.engine = LivingProjectEngine(state_dir=state_dir, model_adapter=adapter)
    return ThreadingHTTPServer(("127.0.0.1", port), GenieRequestHandler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenLine Genie Local Server")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8795)
    parser.add_argument("--state-dir", type=str, default=None)
    parser.add_argument(
        "--enable-paid-model",
        action="store_true",
        help="Explicitly opt in to paid model dispatch (default: OFF)",
    )
    parser.add_argument(
        "--no-model",
        action="store_true",
        help="Run without a model adapter (default deterministic behavior)",
    )
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("Refusing to bind non-loopback host without explicit owner authorization.")
    env_opt_in = os.environ.get("GENIE_ENABLE_PAID_MODEL", "").strip() in ("1", "true", "yes")
    enable_model = bool((args.enable_paid_model or env_opt_in) and not args.no_model)
    srv = start_genie_server(port=args.port, state_dir=args.state_dir, use_model=enable_model, host=args.host)
    print(f"OpenLine Genie listening on http://{args.host}:{args.port} (paid_model={enable_model})", flush=True)
    srv.serve_forever()
