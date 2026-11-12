"""Independent RC7 release falsifiers; expected FAIL on RC6 r5 (+ B2 preflight).

Run from a clean source directory with:
 PYTHONPATH=. python -m unittest -v /path/to/test_genie_rc7_release_falsifiers.py
Zero model calls. Every test runs in an isolated TemporaryDirectory.
"""
from __future__ import annotations
import json, os, tempfile, threading, unittest, uuid
from genie_engine import OpenLineGenieEngine
from core.model_adapter import SpendLedger, cost_usd

class GenieReleaseFalsifiers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='genie-rc7-falsifier-')
        self.engine = OpenLineGenieEngine(state_dir=self.temp.name, model_adapter=None)
        self.bundle = self.engine.build_from_prompt('Build a community garden crop rotation and volunteer tool', use_model=False)
        self.pid = self.bundle['project_id']
    def tearDown(self):
        self.temp.cleanup()
    def proposal(self, label, patch):
        out = self.engine.propose_exploratory_change(self.pid, label, patch)
        return next(p for p in out['exploratory'] if p['summary']==label)
    def test_reject_stale_competing_proposal(self):
        a = self.proposal('a-first', {'title':'A-accepted'})
        b = self.proposal('b-stale', {'title':'B-stale'})
        self.engine.accept_exploratory_change(self.pid,a['proposal_id'])
        before = self.engine.get_project_bundle(self.pid)['accepted']['state_sha256']
        with self.assertRaises((PermissionError,ValueError)):
            self.engine.accept_exploratory_change(self.pid,b['proposal_id'])
        self.assertEqual(before,self.engine.get_project_bundle(self.pid)['accepted']['state_sha256'])
    def test_stop_clear_does_not_resurrect_proposal(self):
        a = self.proposal('old-epoch', {'title':'OLD'})
        before = self.engine.get_project_bundle(self.pid)['accepted']['state_sha256']
        self.engine.trigger_stop('test_stop')
        self.engine.clear_stop('test_clear')
        with self.assertRaises((PermissionError,ValueError)):
            self.engine.accept_exploratory_change(self.pid,a['proposal_id'])
        self.assertEqual(before,self.engine.get_project_bundle(self.pid)['accepted']['state_sha256'])
    def test_cannot_change_project_identity(self):
        old = self.engine.get_project_bundle(self.pid)['accepted']['state_sha256']
        p=self.proposal('malicious-id', {'project_id':'other-internal-project-id'})
        self.assertFalse(p['validation_passed'], 'Identity change should fail verification, not enter promotable state')
        self.assertEqual(old,self.engine.get_project_bundle(self.pid)['accepted']['state_sha256'])
    def test_cannot_change_family_validator(self):
        p=self.proposal('malicious-family', {'project_family':'unknown_unvalidated_family'})
        self.assertFalse(p['validation_passed'], 'Unknown family must never silently drop into weak default verifier')
    def test_reject_preserves_accepted_sha(self):
        p=self.proposal('reject-me',{'title':'REJECT ME'})
        old=self.engine.get_project_bundle(self.pid)['accepted']['state_sha256']
        after=self.engine.reject_exploratory_change(self.pid,p['proposal_id'])
        self.assertEqual(old,after['accepted']['state_sha256'])
    def test_stop_blocks_new_proposals(self):
        self.engine.trigger_stop('test_stop')
        with self.assertRaises(Exception):
            self.engine.propose_exploratory_change(self.pid,'should-be-refused',{'title':'NEVER'})
    def test_concurrent_spend_reservations_do_not_exceed_single_budget(self):
        model='claude-haiku-5-5';cost=cost_usd(100,100,model)
        ledgers=[SpendLedger(self.temp.name),SpendLedger(self.temp.name)]
        ledgers[0].json_path.write_text(json.dumps({'total_usd':0,'cap_usd':5,'calls':[],'reservations':[]}))
        barrier=threading.Barrier(2)
        # Remove shared temporary-file collision from consideration, so this
        # test isolates the substantive read/check/write TOCTOU race.
        for ledger in ledgers:
            orig=ledger._read
            def captured_read(orig=orig):
                state=orig();barrier.wait(timeout=5);return state
            ledger._read=captured_read
            def unique_tmp_write(state,ledger=ledger):
                dest=ledger.json_path.with_name('spend.json.'+uuid.uuid4().hex+'.tmp')
                dest.write_text(json.dumps(state));os.replace(dest,ledger.json_path)
            ledger._write=unique_tmp_write
        results=[]
        def reserve(i):
            try:
                r=ledgers[i].reserve(model,100,100,'double-reservation-probe',cost*1.01)
                results.append(('ALLOWED',r['reservation_id']))
            except Exception as e:
                results.append(('REFUSED',str(e)))
        threads=[threading.Thread(target=reserve,args=(i,)) for i in range(2)]
        [t.start() for t in threads]; [t.join() for t in threads]
        allowed=[x[1] for x in results if x[0]=='ALLOWED']
        persisted=json.loads(ledgers[0].json_path.read_text())
        pinned={r['reservation_id'] for r in persisted['reservations'] if r['status']=='open'}
        self.assertLessEqual(len(allowed),1,'Two separately allowed calls exceed the one-call sub-budget')
        self.assertTrue(set(allowed).issubset(pinned),'Allowed call lost from persisted ledger')

if __name__=='__main__':unittest.main(verbosity=2)
