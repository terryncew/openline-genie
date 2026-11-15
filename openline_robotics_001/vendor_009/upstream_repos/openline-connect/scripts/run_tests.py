#!/usr/bin/env python3
"""Run source tests without installing the package; preserve imports in children."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    env = dict(os.environ)
    paths = [str(ROOT / "src")]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    raise SystemExit(subprocess.call(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        cwd=ROOT, env=env,
    ))
