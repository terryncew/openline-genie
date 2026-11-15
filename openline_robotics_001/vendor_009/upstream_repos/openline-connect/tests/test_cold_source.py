"""A checkout with no installed OpenLine package must work outside its cwd."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class ColdSource(unittest.TestCase):
    def test_cli_from_unrelated_directory_with_absolute_source_path(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONPATH=str(root / "src"))
            result = subprocess.run(
                [sys.executable, "-B", "-m", "openline_connect.cli", "demo", "--output", str(Path(tmp) / "demo")],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["verified"])
