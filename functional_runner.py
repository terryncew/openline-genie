#!/usr/bin/env python3
"""Functional & Real Selenium/Chromium Browser Acceptance Runner (`functional_runner.py`).

Closes Blocker 2.B:
- Removes the legacy mock `sys.modules['selenium']` shim.
- Verifies that real `selenium` + `/usr/bin/chromium` + `/usr/bin/chromedriver` are
  present and executes both `tests/test_openline_genie_001.py` and the live mobile
  browser journey `tests/test_06_living_world_journey.py`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

import selenium  # Fail closed if real Selenium is not installed


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()

    for rel_path in ("tests/test_openline_genie_001.py", "tests/test_06_living_world_journey.py"):
        mod_path = root / rel_path
        mod_name = rel_path[:-3].replace("/", ".")
        spec = importlib.util.spec_from_file_location(mod_name, str(mod_path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load test module: {mod_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        suite.addTests(loader.loadTestsFromModule(mod))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        print(f"FAIL: Browser or functional tests were skipped: {result.skipped}", file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
