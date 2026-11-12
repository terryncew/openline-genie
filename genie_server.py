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
from core.model_adapter import TOTAL_CAP_USD, AnthropicAdapter

HERE = Path(__file__).resolve().parent
HTML_PATH = HERE / "openline_genie.html"
LIVING_WORLD_PATH = HERE / "genie_living_world.html"


class GenieRequestHandler(BaseHTTPRequestHandler):
    engine: OpenLineGenieEngine

    def log_message(self, fmt: str, *args: Any) -> None:
        return

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
        host = self.headers.get("Host", "").split(":")[0].lower()
        origin = self.headers.get("Origin")
        if host not in {"localhost", "127.0.0.1"}:
            self._send_json(403, {"error": "loopback_host_required"})
            return
        if origin:
            expected = f"http://{self.headers.get('Host', '')}"
            if origin != expected:
                self._send_json(403, {"error": "cross_origin_request_refused"})
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
            if parsed.path == "/api/build":
                prompt = str(body.get("prompt", "Build a free quoting and invoicing tool for my small service business."))
                use_model = bool(body.get("use_model", True))
                self._send_json(200, self.engine.build_from_prompt(prompt, use_model=use_model))
                return
            if parsed.path == "/api/import":
                payload = body.get("portable_bundle", body)
                target_pid = body.get("target_project_id")
                self._send_json(
                    200,
                    self.engine.import_portable_bundle(
                        payload,
                        target_project_id=str(target_pid) if target_pid else None,
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
                self._send_json(200, self.engine.reject_exploratory_change(pid, prop_id, reason))
                return
            if parsed.path == "/api/accept":
                pid = str(body["project_id"])
                prop_id = str(body["proposal_id"])
                self._send_json(200, self.engine.accept_exploratory_change(pid, prop_id))
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
) -> ThreadingHTTPServer:
    """Starts the local Genie HTTP server.

    Paid model dispatch (`use_model`) defaults to False ($0 local deterministic
    synthesizer) unless explicitly opted in by the owner.
    """
    adapter = AnthropicAdapter(sub_budget_usd=TOTAL_CAP_USD) if use_model else None
    GenieRequestHandler.engine = OpenLineGenieEngine(state_dir=state_dir, model_adapter=adapter)
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
    srv = start_genie_server(port=args.port, state_dir=args.state_dir, use_model=enable_model)
    print(f"OpenLine Genie listening on http://{args.host}:{args.port} (paid_model={enable_model})", flush=True)
    srv.serve_forever()
