#!/usr/bin/env python3
"""Local HTTP Server & REST API for OpenLine Genie (`genie_server.py`).

Security & Authority Scope:
- Binds strictly to loopback (`127.0.0.1` / `localhost`) with Host and Origin
  CSRF checks on all mutating `POST` endpoints.
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


class GenieRequestHandler(BaseHTTPRequestHandler):
    engine: OpenLineGenieEngine

    def setup(self) -> None:
        super().setup()
        # The application engine belongs to the *server instance*, not a global
        # class variable shared by concurrent clean-install acceptance servers.
        self.engine = getattr(self.server, "genie_engine", None)
        if self.engine is None:
            self.engine = getattr(type(self), "engine", None)
        if self.engine is None:
            raise RuntimeError("server_engine_not_initialized")

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _living_engine(self) -> LivingProjectEngine:
        if isinstance(self.engine, LivingProjectEngine):
            return self.engine
        self.engine = LivingProjectEngine(
            state_dir=self.engine.state_dir,
            model_adapter=self.engine.model_adapter,
        )
        self.server.genie_engine = self.engine
        return self.engine

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _trusted_local_request(self) -> bool:
        """Reject DNS-rebinding Hosts on *all* routes, including read-only GETs.

        This is a single-user local preview, not a multi-tenant or network server.
        """
        import re
        host = self.headers.get("Host", "")
        match = re.fullmatch(r"(localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?", host, re.IGNORECASE)
        if not match or (match.group(2) and int(match.group(2)) != self.server.server_port):
            self._send_json(403, {"error": "loopback_host_required"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin.lower() != f"http://{host}".lower():
            self._send_json(403, {"error": "cross_origin_request_refused"})
            return False
        return True

    def _neighborhood_identity(self) -> tuple[str, str, bool]:
        """Immutable identity configured by the owner at local server startup.

        Browser-provided requester_role, requester_unit_id and board_authorized
        never constitute credentials. Board access needs owner configuration.
        """
        role = getattr(self.server, "neighborhood_role", "homeowner")
        unit = getattr(self.server, "neighborhood_unit", "UNIT-104")
        return role, unit, role == "board"

    def _check_neighborhood_workspace(self, workspace: str) -> bool:
        role, _, _ = self._neighborhood_identity()
        if workspace != role:
            self._send_json(403, {"error": "neighborhood_workspace_requires_server_owner_identity"})
            return False
        return True

    def _safe_neighborhood_state(self) -> dict[str, Any]:
        role, unit, board = self._neighborhood_identity()
        state = self._living_engine().get_neighborhood_state(
            requester_role=role, requester_unit_id=unit, board_authorized=board)
        state["workspaces"] = {
            role: state["workspaces"][role]
        } if role in state["workspaces"] else {}
        state["server_owned_identity"] = {"role": role, "unit_id": unit}
        return state

    def _check_project_visibility(self, project_id: str) -> bool:
        role, _, _ = self._neighborhood_identity()
        specs = self._living_engine().NEIGHBORHOOD_WORKSPACE_SPECS
        for wkey, info in specs.items():
            if project_id == info["project_id"] and wkey != role:
                self._send_json(403, {"error": "neighborhood_project_requires_server_owner_identity"})
                return False
        return True

    def do_OPTIONS(self) -> None:
        self.send_response(403)
        self.end_headers()

    def do_GET(self) -> None:
        if not self._trusted_local_request():
            return
        parsed = urlparse(self.path)
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
        if parsed.path in ("/semantic", "/openline_semantic_authority_workbench.html"):
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
            try:
                from run_semantic_authority_001 import run_all_semantic_authority_001
                rcpt_file = HERE / "SEMANTIC_AUTHORITY_001_RECEIPTS.json"
                if rcpt_file.exists():
                    import json as _json
                    data = _json.loads(rcpt_file.read_text(encoding="utf-8"))
                else:
                    # Never launch an expensive research runner on an HTTP cache miss.
                    self._send_json(503, {"error": "semantic_receipt_not_precomputed", "remedy": "run python3 run_semantic_authority_001.py offline"})
                    return
                self._send_json(200, data)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
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
        if parsed.path in ("/neighborhood", "/be_neighborly", "/clearcovenant", "/openline_neighborhood.html"):
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
                self._send_json(200, self._safe_neighborhood_state())
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/neighborhood/dossier":
            try:
                qs = parse_qs(parsed.query)
                wkey = qs.get("workspace", qs.get("workspace_key", ["homeowner"]))[0]
                if not self._check_neighborhood_workspace(wkey):
                    return
                role, unit, board = self._neighborhood_identity()
                res = self._living_engine().execute_neighborhood_action(wkey, "export_dossier", {
                    "requester_role": role, "requester_unit_id": unit, "target_unit_id": unit,
                    "board_authorized": board})
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
            return
        if parsed.path in ("/robotics", "/openline_robotics_studio.html"):
            r_html = HERE / "openline_robotics_studio.html"
            if not r_html.exists():
                self._send_json(404, {"error": "openline_robotics_studio.html not found"})
                return
            raw = r_html.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/seven_applications/state":
            try:
                self._send_json(200, self._living_engine().get_seven_applications_state())
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
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
            role, _, _ = self._neighborhood_identity()
            forbidden = {v["project_id"] for k, v in
                         self._living_engine().NEIGHBORHOOD_WORKSPACE_SPECS.items()
                         if k != role}
            self._send_json(200, {"projects": [p for p in self.engine.list_projects()
                                                if p.get("project_id") not in forbidden]})
            return
        if parsed.path == "/api/project":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", ["demo-a-service-quoting"])[0]
            if not self._check_project_visibility(pid):
                return
            try:
                self._send_json(200, self.engine.get_project_bundle(pid))
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/export":
            qs = parse_qs(parsed.query)
            pid = qs.get("project_id", ["demo-a-service-quoting"])[0]
            if not self._check_project_visibility(pid):
                return
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
            if not self._check_project_visibility(pid):
                return
            try:
                self._send_json(
                    200,
                    self.engine.get_app_version(pid, int(version) if version is not None else None),
                )
            except Exception as exc:
                self._send_json(404, {"error": str(exc)})
            return
        if parsed.path == "/api/status":
            stop = self.engine.guard.read_stop_state()
            self._send_json(200, {**self.engine.get_status(),
                                  "stopped":bool(stop.get("stopped", False)),
                                  "stop_epoch":int(stop.get("epoch", 0))})
            return
        self._send_json(404, {"error": f"Unknown endpoint {parsed.path}"})

    def do_POST(self) -> None:
        if not self._trusted_local_request():
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
        if parsed.path not in ("/api/neighborhood/stage", "/api/neighborhood/action"):
            for field in ("project_id", "target_project_id"):
                if field in body and not self._check_project_visibility(str(body[field])):
                    return
        try:
            if parsed.path == "/api/neighborhood/stage":
                wkey = str(body.get("workspace_key", "homeowner"))
                if not self._check_neighborhood_workspace(wkey):
                    return
                payload = dict(body.get("payload", body))
                role, unit, board = self._neighborhood_identity()
                payload.update(requester_role=role, requester_unit_id=unit,
                               target_unit_id=unit, board_authorized=board)
                self._send_json(200, self._living_engine().stage_neighborhood_proposal(wkey, payload))
                return
            if parsed.path == "/api/neighborhood/action":
                wkey = str(body.get("workspace_key", "homeowner"))
                action = str(body.get("action", ""))
                if not self._check_neighborhood_workspace(wkey):
                    return
                payload = dict(body.get("payload", body))
                role, unit, board = self._neighborhood_identity()
                payload.update(requester_role=role, requester_unit_id=unit,
                               target_unit_id=unit, board_authorized=board)
                result = self._living_engine().execute_neighborhood_action(wkey, action, payload)
                if "neighborhood_state" in result:
                    result["neighborhood_state"] = self._safe_neighborhood_state()
                self._send_json(200, result)
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
            if parsed.path == "/api/build":
                prompt = str(body.get("prompt", "Build a free quoting and invoicing tool for my small service business."))
                use_model = bool(body.get("use_model", True))
                self._send_json(200, self.engine.build_from_prompt(prompt, use_model=use_model))
                return
            if parsed.path == "/api/import":
                payload = body.get("portable_bundle", body)
                target_pid = body.get("target_project_id")
                allow_overwrite = bool(body.get("allow_overwrite", False))
                orig = payload
                if isinstance(orig, dict) and isinstance(orig.get("portable_json"), str):
                    orig = json.loads(orig["portable_json"])
                dest = str(target_pid or (orig.get("project_id") if isinstance(orig, dict) else "") or "")
                if dest and not self._check_project_visibility(dest):
                    return
                self._send_json(
                    200,
                    self._living_engine().import_portable_bundle(
                        payload,
                        target_project_id=str(target_pid) if target_pid else None,
                        allow_overwrite=allow_overwrite,
                        expected_base_version=body.get("expected_base_version"),
                        expected_base_sha256=body.get("expected_base_sha256"),
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
                requested_epoch = body.get("expected_epoch")
                if type(requested_epoch) is not int or requested_epoch < 1:
                    raise ValueError("invalid_expected_epoch")
                self._send_json(200, self.engine.clear_stop(
                    str(body.get("reason", "owner_clear")), expected_epoch=requested_epoch
                ))
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
                or "stale_owner_intent" in msg
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
    """
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("non_loopback_binding_refused")
    adapter = AnthropicAdapter(sub_budget_usd=TOTAL_CAP_USD) if use_model else None
    GenieRequestHandler.engine = LivingProjectEngine(state_dir=state_dir, model_adapter=adapter)
    srv = ThreadingHTTPServer((host, port), GenieRequestHandler)
    srv.genie_engine = GenieRequestHandler.engine
    # Server-owned single-user identity. This is not a multi-user auth system.
    role = os.environ.get("GENIE_NEIGHBORHOOD_OWNER_ROLE", "homeowner").strip().lower()
    if role not in {"homeowner", "board", "community"}:
        srv.server_close()
        raise ValueError("invalid_server_neighborhood_owner_role")
    srv.neighborhood_role = role
    srv.neighborhood_unit = (os.environ.get("GENIE_NEIGHBORHOOD_OWNER_UNIT", "UNIT-104")
                             .strip().upper() if role == "homeowner" else
                             ("BOARD-OAK-CREEK" if role == "board" else "COMMUNITY-OAK-CREEK"))
    return srv


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
