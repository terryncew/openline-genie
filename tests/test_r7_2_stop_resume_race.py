"""R7.2 regression: fast Resume must be bound to the acknowledged STOP epoch.

Browser sequencing is additionally covered by browser_stop_race_probe.py in the
independent handoff; the API/receiver proof here uses real local HTTP+SQLite.
"""
from __future__ import annotations
import json
from tests.test_final_release_boundaries import TestFinalReleaseBoundaries


class TestR72StopResumeRace(TestFinalReleaseBoundaries):
    def test_10_resume_pinned_to_own_stop_epoch(self):
        code, raw = self.request('/api/stop', method='POST', body={'reason':'first_owner_stop'})
        self.assertEqual(code, 200)
        stop = json.loads(raw)
        epoch = stop['new_epoch']
        self.assertGreaterEqual(epoch, 2)
        for stale in (epoch-1, epoch+1):
            code, raw = self.request('/api/clear_stop', method='POST', body={
                'reason':'unrelated_or_stale_resume', 'expected_epoch':stale
            })
            self.assertEqual(code,409,(stale,code,raw))
            self.assertIn(b'stale_owner_intent',raw)
            code, raw = self.request('/api/status')
            self.assertTrue(json.loads(raw)['stopped'])
        code, raw = self.request('/api/clear_stop', method='POST', body={
            'reason':'acknowledged_resume','expected_epoch':epoch
        })
        self.assertEqual(code,200,raw)
        self.assertEqual(json.loads(raw)['active_epoch'],epoch+1)
        code, raw = self.request('/api/status')
        self.assertFalse(json.loads(raw)['stopped'])

    def test_11_intervening_stop_cannot_be_cleared_by_queued_resume(self):
        code, raw = self.request('/api/stop',method='POST',body={'reason':'owner_stop_1'})
        self.assertEqual(code,200)
        first_epoch=json.loads(raw)['new_epoch']
        code, raw = self.request('/api/stop',method='POST',body={'reason':'independent_owner_stop_2'})
        self.assertEqual(code,200)
        latest_epoch=json.loads(raw)['new_epoch']
        self.assertGreater(latest_epoch,first_epoch)
        code, raw = self.request('/api/clear_stop',method='POST',body={
            'reason':'queued_resume_for_stop_1','expected_epoch':first_epoch
        })
        self.assertEqual(code,409,raw)
        self.assertIn(b'stale_owner_intent',raw)
        code, raw = self.request('/api/status')
        self.assertTrue(json.loads(raw)['stopped'])
        self.assertEqual(json.loads(raw)['stop_epoch'],latest_epoch)
        code, raw = self.request('/api/clear_stop',method='POST',body={
            'reason':'authorized_resume_stop_2','expected_epoch':latest_epoch
        })
        self.assertEqual(code,200,raw)

    def test_12_malformed_epoch_never_clears_receiver_stop(self):
        code, raw = self.request('/api/stop',method='POST',body={})
        self.assertEqual(code,200)
        for bad in (True,False,0,-1,1.5,'2',[],{}):
            code, raw = self.request('/api/clear_stop',method='POST',body={
                'reason':'bad_epoch_probe','expected_epoch':bad
            })
            self.assertEqual(code,400,(bad,code,raw))
            code, raw = self.request('/api/status')
            self.assertTrue(json.loads(raw)['stopped'])
        # Existing single-operator clients remain backward compatible.
        code, raw = self.request('/api/clear_stop',method='POST',body={})
        self.assertEqual(code,200,raw)
