#!/usr/bin/env python3
"""OpenLine Robotics Breakthrough 001 — HTTP Server & CLI Runner (`robotics_studio_server.py`).

Provides:
1. Loopback-only HTTP server (`127.0.0.1:8796`) with CSRF Host/Origin/Content-Type guards
   serving `openline_robotics_studio.html` and JSON APIs (`/api/robotics/state`, `/api/robotics/simulate`,
   `/api/robotics/diagnose_repair`, `/api/robotics/accept`, `/api/robotics/reject`, `/api/robotics/recall`,
   `/api/robotics/stop`, `/api/robotics/hardware_frame`, `/api/robotics/export`, `/api/robotics/import`).
2. One-command CLI verification (`--verify-all`) running the Product Hypothesis Tournament,
   Unfamiliar Dogfood Suite, and Independent Hidden-Seed Acceptance Evaluator and saving
   signed JSON evidence receipts.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import tempfile
from typing import Any
from urllib.parse import urlparse

from openline_robotics_001.robotics_studio_engine import OpenLineRoboticsProductEngine
from openline_robotics_001.hardware_safety_adapter import HardwareSafetyRefused
from openline_robotics_001.unfamiliar_dogfood_suite import run_unfamiliar_dogfood_suite
from openline_robotics_001.independent_evaluator import run_independent_acceptance_evaluation

HERE = Path(__file__).resolve().parent
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def make_handler(engine: OpenLineRoboticsProductEngine, html_path: Path):
    class RoboticsStudioHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send_json(self, code: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _check_loopback_and_csrf(self, is_post: bool = False) -> bool:
            host_hdr = (self.headers.get("Host") or "").split(":")[0].strip().lower()
            if host_hdr not in ALLOWED_HOSTS:
                self._send_json(403, {"error": "loopback_host_required"})
                return False
            if is_post:
                origin = (self.headers.get("Origin") or "").strip().lower()
                if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
                    self._send_json(403, {"error": "cross_origin_request_refused"})
                    return False
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/json":
                    self._send_json(415, {"error": "application_json_required"})
                    return False
            return True

        def do_GET(self) -> None:
            if not self._check_loopback_and_csrf(is_post=False):
                return
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/robotics", "/openline_robotics_studio.html"):
                raw = html_path.read_bytes() if html_path.is_file() else b"<h1>OpenLine Robotics Studio</h1>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if parsed.path == "/api/robotics/state":
                projs = engine.list_robot_projects()
                details = {p["project_id"]: engine.get_project_detail(p["project_id"]) for p in projs}
                self._send_json(200, {
                    "projects": projs,
                    "details": details,
                    "stopped": engine.living_engine.guard.read_stop_state()["stopped"],
                })
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if not self._check_loopback_and_csrf(is_post=True):
                return
            length = int(self.headers.get("Content-Length") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self._send_json(400, {"error": "invalid_json"})
                return

            parsed = urlparse(self.path)
            try:
                pid = str(body.get("project_id") or "proj-open-duck-mini-v2")
                if parsed.path == "/api/robotics/create_project":
                    res = engine.create_robot_project(
                        project_id=str(body["project_id"]),
                        title=str(body["title"]),
                        robot_id=str(body["robot_id"]),
                        goal=body.get("goal"),
                        environment=body.get("environment"),
                    )
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/simulate":
                    res = engine.execute_simulation(
                        pid,
                        controller_mode=body.get("controller_mode"),
                        use_onnx_policy=bool(body.get("use_onnx_policy", False)),
                        emergency_stop_at_s=body.get("emergency_stop_at_s"),
                    )
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/diagnose_repair":
                    res = engine.diagnose_and_repair(pid, inherited_capsule=body.get("inherited_capsule"))
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/accept":
                    res = engine.accept_proposal(pid)
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/reject":
                    res = engine.reject_proposal(pid, reason=str(body.get("reason", "Rejected by user")))
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/recall":
                    res = engine.trigger_assumption_change_recall(
                        pid,
                        node_id=str(body.get("node_id", "demand")),
                        reason=str(body.get("reason", "Calibration changed")),
                    )
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/stop":
                    if body.get("clear"):
                        res = engine.clear_emergency_stop(str(body.get("reason", "Operator cleared STOP")))
                    else:
                        res = engine.engage_emergency_stop(str(body.get("reason", "Operator engaged STOP")))
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/hardware_frame":
                    res = engine.test_hardware_safety_dispatch(
                        pid,
                        operator_authorized=bool(body.get("operator_authorized", True)),
                        command_age_ms=float(body.get("command_age_ms", 15.0)),
                        manufacturer_limits_enabled=bool(body.get("manufacturer_limits_enabled", True)),
                    )
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/export":
                    res = engine.export_skill_bundle(pid)
                    self._send_json(200, res)
                elif parsed.path == "/api/robotics/import":
                    res = engine.import_skill_bundle(
                        body["bundle"],
                        target_project_id=body.get("target_project_id"),
                    )
                    self._send_json(200, res)
                else:
                    self._send_json(404, {"error": "unknown_endpoint"})
            except HardwareSafetyRefused as exc:
                self._send_json(403, {"error": "hardware_safety_refused", "detail": str(exc)})
            except PermissionError as exc:
                self._send_json(409, {"error": "authority_or_stop_refused", "detail": str(exc)})
            except Exception as exc:
                self._send_json(400, {"error": type(exc).__name__, "detail": str(exc)})

    return RoboticsStudioHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenLine Robotics Studio Server & Verifier")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8796)
    parser.add_argument("--state-dir", default="./state_robotics_001")
    parser.add_argument("--verify-all", action="store_true", help="Run dogfood + independent acceptance suite and exit")
    parser.add_argument("--receipts-out", default="")
    args = parser.parse_args()

    if args.verify_all:
        dogfood = run_unfamiliar_dogfood_suite()
        acceptance = run_independent_acceptance_evaluation()
        combined = {
            "unfamiliar_dogfood": dogfood,
            "independent_acceptance": acceptance,
        }
        if args.receipts_out:
            out_p = Path(args.receipts_out)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(combined, indent=2), encoding="utf-8")
        print(json.dumps({
            "dogfood_scoreboard": dogfood["controller_scoreboard"],
            "acceptance_passed": acceptance["overall_acceptance_passed"],
            "verdict_software": acceptance["verdict_simulation_and_software"],
            "verdict_hardware": acceptance["verdict_physical_hardware"],
        }, indent=2))
        sys.exit(0 if acceptance["overall_acceptance_passed"] else 1)

    eng = OpenLineRoboticsProductEngine(args.state_dir)
    html_file = HERE / "openline_robotics_studio.html"
    server = HTTPServer((args.host, args.port), make_handler(eng, html_file))
    print(f"OpenLine Argon Robotics Studio listening on http://{args.host}:{args.port}/robotics")
    server.serve_forever()


if __name__ == "__main__":
    main()
