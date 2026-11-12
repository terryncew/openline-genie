"""GPT-6 independent RC7 r1 falsifiers. Run on a clean extracted RC7 source.

Expect FAIL on RC7 r1; repaired implementations must PASS, without payment or external APIs.
All state lives in disposable TemporaryDirectory objects.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SRC = os.environ.get('GENIE_RC7_SRC', str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, SRC)
from genie_engine import OpenLineGenieEngine, sha256_hex
from genie_server import start_genie_server


def acc(engine, pid):
    return engine.get_project_bundle(pid)['accepted']


def portable(engine, pid):
    return json.loads(engine.export_portable_bundle(pid)['portable_json'])


class RC7FreshFalsifiers(unittest.TestCase):
    def setUp(self):
        self.d1 = tempfile.TemporaryDirectory()
        self.d2 = tempfile.TemporaryDirectory()
        self.sender = OpenLineGenieEngine(state_dir=self.d1.name, model_adapter=None)
        self.receiver = OpenLineGenieEngine(state_dir=self.d2.name, model_adapter=None)
        self.pid = self.sender.list_projects()[0]['project_id']

    def tearDown(self):
        self.d1.cleanup(); self.d2.cleanup()

    def test_01_stale_import_cannot_overwrite_newer_accepted_without_explicit_receiver_admission(self):
        old = portable(self.receiver, self.pid)
        before = acc(self.receiver, self.pid)
        b = self.receiver.propose_exploratory_change(self.pid, 'accepted improvement', {'title':'NEW OWNER-ACCEPTED TITLE'})
        proposal = next(p['proposal_id'] for p in b['exploratory'] if p['status']=='EXPLORATORY_PENDING')
        self.receiver.accept_exploratory_change(self.pid,proposal)
        approved = acc(self.receiver, self.pid)
        self.assertNotEqual(approved['state_sha256'], before['state_sha256'])
        with self.assertRaises((ValueError, PermissionError)):
            self.receiver.import_portable_bundle(old)
        self.assertEqual(acc(self.receiver, self.pid)['state_sha256'], approved['state_sha256'])

    def test_02_receipt_signature_must_bind_imported_state_not_merely_signer_key(self):
        doc = portable(self.sender, self.pid)
        doc['accepted']['state']['title'] = 'MUTATED CONTENT WITH ORIGINAL SIGNATURE'
        doc['accepted']['state_sha256'] = sha256_hex(doc['accepted']['state'])
        prior = acc(self.receiver, self.pid)
        # We require outright refusal of a forged signed export, not a 'verified' badge on changed bytes.
        with self.assertRaises((ValueError, PermissionError)):
            self.receiver.import_portable_bundle(doc)
        self.assertEqual(acc(self.receiver,self.pid)['state_sha256'], prior['state_sha256'])

    def test_03_imported_executable_app_must_match_claimed_hash_and_signed_export_authority(self):
        doc = portable(self.sender, self.pid)
        doc['app'] = {'filename':'unsigned.html', 'content':'<html>UNSIGNED EXECUTABLE</html>',
                      'sha256':'0'*64, 'version':1, 'runs_standalone':True}
        with self.assertRaises((ValueError, PermissionError)):
            self.receiver.import_portable_bundle(doc)
        with sqlite3.connect(self.receiver.db_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM genie_app_versions WHERE project_id=?',(self.pid,)).fetchone()[0],0)

    def test_04_stop_refusal_must_not_leave_any_accepted_app_version(self):
        doc = portable(self.sender, self.pid)
        doc['app'] = {'filename':'injected.html', 'content':'<html>BEFORE_RECEIVER_APPROVAL</html>',
                      'sha256':sha256_hex('<html>BEFORE_RECEIVER_APPROVAL</html>'),
                      'version':1, 'runs_standalone':True}
        self.receiver.trigger_stop('audit stop')
        prior = acc(self.receiver,self.pid)['state_sha256']
        with self.assertRaises(Exception):
            self.receiver.import_portable_bundle(doc)
        self.assertEqual(acc(self.receiver,self.pid)['state_sha256'],prior)
        with sqlite3.connect(self.receiver.db_path) as db:
            rows=db.execute('SELECT version,status FROM genie_app_versions WHERE project_id=?',(self.pid,)).fetchall()
        self.assertEqual(rows, [], f'Import left app_versions side effect after STOP denial: {rows}')

    def test_05_http_import_must_not_promote_tampered_signed_export(self):
        doc=portable(self.sender,self.pid)
        doc['accepted']['state']['title']='HTTP-FORGED-TITLE'
        doc['accepted']['state_sha256']=sha256_hex(doc['accepted']['state'])
        server=start_genie_server(port=0,state_dir=self.d2.name,use_model=False)
        t=threading.Thread(target=server.serve_forever,daemon=True)
        t.start()
        try:
            base=f'http://127.0.0.1:{server.server_address[1]}'
            req=urllib.request.Request(base+'/api/import',
                data=json.dumps({'portable_bundle':doc}).encode('utf-8'),
                headers={'Host':'127.0.0.1','Content-Type':'application/json'},method='POST')
            try:
                with urllib.request.urlopen(req,timeout=10) as r:
                    status=r.status
            except urllib.error.HTTPError as e:
                status=e.code
            self.assertIn(status,(400,403,409,422),f'tampered signed import accepted over HTTP: {status}')
        finally:
            server.shutdown();server.server_close();t.join(timeout=3)

if __name__ == '__main__':
    unittest.main(verbosity=2)
