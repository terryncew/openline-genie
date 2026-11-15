#!/usr/bin/env bash
# OpenLine Robotics Studio — local loopback-only launcher.
# Serves the Robotics Studio workbench at http://127.0.0.1:8796/robotics
# and the studio API at http://127.0.0.1:8796/api/robotics/*.
# Binds loopback only; any other --host is refused by the server.
# Requires: Python 3.11+, numpy, onnxruntime
#   (pip install --user onnxruntime, or inside the repo venv).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"
exec python3 -m openline_robotics_001.robotics_studio_server --host 127.0.0.1 --port "${PORT:-8796}" --state-dir "${STATE_DIR:-./state_robotics_001}" "$@"
