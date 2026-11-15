#!/usr/bin/env python3
"""OpenLine Genie — One-Command Local Launcher (`launch_genie.py`).

Starts OpenLine Genie in free local mode ($0.00 cost, no API keys required),
initializes sample projects for all five applications, and serves the local
browser interface strictly on loopback (`127.0.0.1`).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import webbrowser

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from genie_server import start_genie_server
from openline_009_living_project import LivingProjectEngine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch OpenLine Genie locally (Free Local Mode, $0 cost, no API keys needed)."
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Loopback bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8795, help="Local port (default: 8795)")
    parser.add_argument(
        "--state-dir",
        type=str,
        default=str(HERE / "genie_local_data"),
        help="Directory for persistent local SQLite project records",
    )
    parser.add_argument("--open-browser", action="store_true", help="Automatically open the default web browser")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Initialize sample projects, verify integrity of all 5 applications, and exit 0",
    )
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost"):
        sys.stderr.write("Security Error: OpenLine Genie binds strictly to 127.0.0.1 / localhost by default.\n")
        return 2

    state_path = Path(args.state_dir).resolve()
    state_path.mkdir(parents=True, exist_ok=True)

    eng = LivingProjectEngine(state_dir=state_path)
    st = eng.get_five_products_state()
    products = st.get("products", {})
    if len(products) != 5:
        sys.stderr.write(f"Initialization Error: expected 5 applications, found {len(products)}.\n")
        return 1

    if args.verify_only:
        print(json.dumps({
            "status": "READY",
            "mode": "FREE_LOCAL_MODE_NO_API_KEYS",
            "state_dir": str(state_path),
            "applications_ready": list(products.keys()),
            "community_projects_ready": [p["project_id"] for p in st.get("commons_library", {}).get("projects", [])],
        }, indent=2))
        return 0

    srv = start_genie_server(port=args.port, state_dir=state_path, use_model=False)
    actual_port = srv.server_port
    url_products = f"http://{args.host}:{actual_port}/products"
    url_builder = f"http://{args.host}:{actual_port}/openline_genie.html"
    url_map = f"http://{args.host}:{actual_port}/"

    print("=" * 72)
    print("  OPENLINE GENIE — LOCAL APPLICATION SUITE (v1.0.0-RC1)")
    print("=" * 72)
    print(f"  Mode:               Free Local Mode ($0.00 cost • No API keys needed)")
    print(f"  Saved Data Folder:  {state_path}")
    print(f"  Five Applications:  {url_products}")
    print(f"  Custom App Builder: {url_builder}")
    print(f"  Project Map View:   {url_map}")
    print("-" * 72)
    print("  Included Applications:")
    print("    1. Energy Commons     — Plan affordable community energy")
    print("    2. Advocate           — Organize evidence & prepare challenges")
    print("    3. Capability Commons — Build & share reusable community projects")
    print("    4. Science            — Run reproducible research & keep findings")
    print("    5. Civic              — Compare public projects & track decisions")
    print("-" * 72)
    print("  Press Ctrl+C at any time to stop the local server. Your work is saved.")
    print("=" * 72, flush=True)

    if args.open_browser:
        try:
            webbrowser.open(url_products)
        except Exception:
            pass

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping OpenLine Genie server. All accepted work is saved.")
    finally:
        srv.shutdown()
        srv.server_close()
    return 0


if __name__ == "__main__":
    import json
    raise SystemExit(main())
