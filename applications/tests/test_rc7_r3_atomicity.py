"""Independent receiver transaction consistency tests, $0 model calls.

These fail at RC7 r2's split app/accepted/receipt commits. All tests use
throwaway local state. Use both Python and `python -O`.
"""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genie_engine import OpenLineGenieEngine, sha256_hex
from core.openline_guard import GuardRefused, verify_receipt_offline


class AtomicAcceptedArtifactTests(unittest.TestCase):
    def make_portable(self):
        src = tempfile.TemporaryDirectory()
        sender = OpenLineGenieEngine(state_dir=src.name, model_adapter=None)
        pid = sender.list_projects()[0]['project_id']
        html = '<html><body><h1>Portable artifact</h1></body></html>'
        version = sender.store_app_version(pid, 'portable.html', html, status='exploratory')
        state = copy.deepcopy(sender.get_project_bundle(pid)['accepted']['state'])
        state.update(app_sha256=sha256_hex(html), app_version=version, app_filename='portable.html')
        sender._commit_accepted_state(pid, state['project_family'], state,
                                      promote_staged_app_version=version)
        portable = sender.get_project_bundle(pid)
        portable['app'] = dict(filename='portable.html', content=html,
                               sha256=sha256_hex(html), version=version,
                               runs_standalone=True)
        return src, portable, pid + '-receiving-instance'

    def rows(self, eng, pid):
        with sqlite3.connect(eng.db_path) as db:
            a = db.execute('SELECT state_json, receipt_json FROM genie_accepted WHERE project_id=?', (pid,)).fetchone()
            apps = db.execute('SELECT version, sha256, status FROM genie_app_versions WHERE project_id=?', (pid,)).fetchall()
        return a, apps

    def test_promotion_failure_rollback_new_import(self):
        source, bundle, pid = self.make_portable()
        with source, tempfile.TemporaryDirectory() as target:
            eng = OpenLineGenieEngine(state_dir=target, model_adapter=None)
            with patch.object(eng, 'promote_app_version', side_effect=RuntimeError('simulated_promote_crash')):
                with self.assertRaisesRegex(GuardRefused, 'simulated_promote_crash'):
                    eng.import_portable_bundle(bundle, target_project_id=pid)
            row, apps = self.rows(eng, pid)
            self.assertIsNone(row)
            self.assertFalse(any(a[2]=='accepted' for a in apps))

    def test_after_commit_caller_crash_preserves_accepted_app_and_receipt(self):
        source, bundle, pid = self.make_portable()
        with source, tempfile.TemporaryDirectory() as target:
            eng = OpenLineGenieEngine(state_dir=target, model_adapter=None)
            original = eng.guard.execute
            def fail_after_commit(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError('simulated_caller_crash_after_durable_commit')
            with patch.object(eng.guard, 'execute', side_effect=fail_after_commit):
                with self.assertRaisesRegex(RuntimeError, 'simulated_caller_crash'):
                    eng.import_portable_bundle(bundle, target_project_id=pid)
            row, apps = self.rows(eng, pid)
            self.assertIsNotNone(row, 'Committed state must not be lost after caller crash')
            self.assertEqual(len([a for a in apps if a[2]=='accepted']), 1)
            state = json.loads(row[0]); receipt = json.loads(row[1])
            self.assertEqual(state['app_sha256'], apps[0][1])
            self.assertEqual(receipt['status'], 'COMMITTED')
            self.assertEqual(verify_receipt_offline(receipt['receipt'], pinned_receiver_pub=eng.receiver_identity.public)['crypto'],'VERIFIED')
            # Reopen another engine; ensure it sees the same accepted app.
            restarted = OpenLineGenieEngine(state_dir=target, model_adapter=None)
            self.assertEqual(restarted.get_app_version(pid)['status'], 'accepted')
            self.assertEqual(restarted.get_project_bundle(pid)['accepted']['state_sha256'], sha256_hex(state))

    def test_receipt_write_failure_rolls_back_artifact_and_state(self):
        source, bundle, pid = self.make_portable()
        with source, tempfile.TemporaryDirectory() as target:
            eng = OpenLineGenieEngine(state_dir=target, model_adapter=None)
            original = eng.guard.execute
            def fail_receipt_storage(*args, **kwargs):
                hook = kwargs['post_receipt_hook']
                def injected(db, signed_receipt):
                    hook(db, signed_receipt)
                    raise RuntimeError('simulated_receipt_storage_failure_before_commit')
                kwargs['post_receipt_hook'] = injected
                return original(*args, **kwargs)
            with patch.object(eng.guard, 'execute', side_effect=fail_receipt_storage):
                with self.assertRaisesRegex(GuardRefused, 'simulated_receipt_storage_failure'):
                    eng.import_portable_bundle(bundle, target_project_id=pid)
            row, apps = self.rows(eng, pid)
            self.assertIsNone(row)
            self.assertFalse(any(a[2]=='accepted' for a in apps))

    def test_successful_import_one_complete_accepted_bundle(self):
        source, bundle, pid = self.make_portable()
        with source, tempfile.TemporaryDirectory() as target:
            eng = OpenLineGenieEngine(state_dir=target, model_adapter=None)
            result = eng.import_portable_bundle(bundle, target_project_id=pid)
            row, apps = self.rows(eng, pid)
            self.assertIsNotNone(row)
            self.assertEqual(len([a for a in apps if a[2]=='accepted']), 1)
            self.assertEqual(result['accepted']['state_sha256'], sha256_hex(json.loads(row[0])))
            self.assertEqual(json.loads(row[1])['status'], 'COMMITTED')

    def test_exploratory_accept_promotion_failure_preserves_old_accepted_sha(self):
        with tempfile.TemporaryDirectory() as d:
            eng = OpenLineGenieEngine(state_dir=d, model_adapter=None)
            pid = eng.list_projects()[0]['project_id']
            prior = eng.get_project_bundle(pid)['accepted']['state_sha256']
            proposal = eng.propose_exploratory_change(pid, 'Change HTML',
                                {'app_content':'<html><body>new app</body></html>'})
            prop_id = proposal['exploratory'][0]['proposal_id']
            with patch.object(eng,'promote_app_version', side_effect=RuntimeError('simulated_proposal_promote_crash')):
                with self.assertRaisesRegex(GuardRefused, 'simulated_proposal_promote_crash'):
                    eng.accept_exploratory_change(pid, prop_id)
            self.assertEqual(eng.get_project_bundle(pid)['accepted']['state_sha256'], prior)
            with sqlite3.connect(eng.db_path) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM genie_app_versions WHERE project_id=? AND status='accepted'",(pid,)).fetchone()[0],0)

    def test_signed_effect_reconstructs_receipt_excluded_database_row(self):
        # Receipt signing precedes its inclusion in the row; hash the stated
        # pre-receipt projection rather than the self-referential final row.
        with tempfile.TemporaryDirectory() as d:
            eng = OpenLineGenieEngine(state_dir=d, model_adapter=None)
            pid = eng.list_projects()[0]['project_id']
            with sqlite3.connect(eng.db_path) as db:
                db.row_factory = sqlite3.Row
                row = db.execute('SELECT * FROM genie_accepted WHERE project_id=?', (pid,)).fetchone()
                rec = json.loads(row['receipt_json'])['receipt']
                projected = dict(row)
                projected['receipt_json'] = '{}'
                self.assertEqual(sha256_hex(projected), rec['payload']['effect_sha256'])
                self.assertEqual(sha256_hex(json.loads(row['state_json'])), row['state_sha256'])
                self.assertEqual(verify_receipt_offline(rec, pinned_receiver_pub=eng.receiver_identity.public)['crypto'], 'VERIFIED')
                # The content/target/version all must bind to the signed request.
                req = dict(project_id=pid, version=int(row['version']), state_sha256=row['state_sha256'], amount=1)
                self.assertEqual(sha256_hex(req), rec['payload']['payload_sha256'])

    def test_exploratory_success_atomic_app_and_signed_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            eng = OpenLineGenieEngine(state_dir=d, model_adapter=None)
            pid = eng.list_projects()[0]['project_id']
            proposal = eng.propose_exploratory_change(pid, 'Change HTML',
                                {'app_content':'<html><body>new app</body></html>'})
            prop_id = proposal['exploratory'][0]['proposal_id']
            eng.accept_exploratory_change(pid, prop_id)
            row, apps = self.rows(eng, pid)
            self.assertEqual(len([a for a in apps if a[2]=='accepted']),1)
            self.assertEqual(json.loads(row[0])['app_sha256'], apps[0][1])
            self.assertEqual(json.loads(row[1])['status'], 'COMMITTED')

if __name__ == '__main__': unittest.main(verbosity=2)
