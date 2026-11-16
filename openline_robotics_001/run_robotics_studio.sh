#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PARENT_DIR}"
exec python3 -m openline_robotics_001.robotics_studio_server --host 127.0.0.1 --port "${PORT:-8796}" --state-dir "${STATE_DIR:-./state_robotics_001}" "$@"
