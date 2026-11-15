"""Regression for CLI branch-local import shadowing discovered in final technical gate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class CliEntrypoints(unittest.TestCase):
    def test_actual_init_then_serve_stdio_and_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'receiver'
            cmd = [sys.executable, '-m', 'openline_connect.cli']
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
            created = subprocess.run(cmd + ['init', '--home', str(home)], text=True,
                                     capture_output=True, check=True, timeout=10, env=env)
            self.assertEqual(json.loads(created.stdout)['authorized_operations'], 0)
            request = json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list'})+'\n'
            server = subprocess.run(cmd + ['serve','--home',str(home),'--fallback-stdio'],
                                    input=request, text=True, capture_output=True, timeout=10, check=True, env=env)
            parsed=json.loads(server.stdout.strip())
            names={t['name'] for t in parsed['result']['tools']}
            self.assertIn('openline_execute_protected_action', names)
            self.assertNotIn('raw_execute', names)
            demo = subprocess.run(cmd + ['demo','--output',str(Path(tmp)/'demo')],
                                  text=True,capture_output=True,check=True,timeout=10,env=env)
            self.assertTrue(json.loads(demo.stdout)['verified'])

if __name__=='__main__':unittest.main()
