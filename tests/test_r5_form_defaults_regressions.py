"""Regression tests for consecutive accepted changes and persisted form inputs."""
import unittest
from tests.test_final_release_boundaries import TestFinalReleaseBoundaries

class TestR5FormDefaults(TestFinalReleaseBoundaries):
    def test_07_sequential_accepts_restore_current(self):
        eng=self.server.genie_engine
        eng.ensure_five_products_initialized()
        pid=eng.FIVE_PRODUCT_SPECS['energy']['project_id']
        for inputs in ({'households':43},{'grid_tariff_usd_per_kwh':0.31}):
            proposal=eng.stage_five_product_proposal('energy',{'inputs':inputs})['proposal']
            eng.accept_exploratory_change(pid,proposal['proposal_id'])
        current=eng.get_project_bundle(pid)['accepted']
        self.assertEqual(eng.recall_ledger.standing(pid+':scenario_plan',now=260).status,'REOPEN')
        result=eng.confirm_five_product_local_basis_review('energy',expected_accepted_sha256=current['state_sha256'],human_reviewed=True)
        self.assertEqual(result['dnf_standing'],'CURRENT')
        eng.recall_living_project_dependency(pid,'workflow','independent_upstream_revocation')
        with self.assertRaises(PermissionError):
            eng.confirm_five_product_local_basis_review('energy',expected_accepted_sha256=current['state_sha256'],human_reviewed=True)

    def test_08_advocate_form_values_persist(self):
        eng=self.server.genie_engine
        eng.ensure_five_products_initialized()
        pid=eng.FIVE_PRODUCT_SPECS['advocate']['project_id']
        proposal=eng.stage_five_product_proposal('advocate',{'filing_date':'2026-11-19','appeal_window_days':45})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['filing_date'],'2026-11-19')
        self.assertEqual(app['assumptions']['appeal_window_days'],45)
        proposal=eng.stage_five_product_proposal('advocate',{'notice_date':'2026-11-02'})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['filing_date'],'2026-11-19')
        self.assertEqual(app['assumptions']['appeal_window_days'],45)

    def test_09_civic_form_values_persist(self):
        eng=self.server.genie_engine
        eng.ensure_five_products_initialized()
        pid=eng.FIVE_PRODUCT_SPECS['civic']['project_id']
        proposal=eng.stage_five_product_proposal('civic',{'max_property_line_noise_dba':55})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['max_property_line_noise_dba'],55)
        proposal=eng.stage_five_product_proposal('civic',{'max_72h_blackout_outage_hours':3.0})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['max_72h_blackout_outage_hours'],3.0)
        self.assertEqual(app['assumptions']['max_property_line_noise_dba'],55)

    def test_10_science_form_values_persist(self):
        eng=self.server.genie_engine
        eng.ensure_five_products_initialized()
        pid=eng.FIVE_PRODUCT_SPECS['science']['project_id']
        proposal=eng.stage_five_product_proposal('science',{'seed_offset_1':7})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['seed_offset_1'],7)
        proposal=eng.stage_five_product_proposal('science',{'seed_offset_2':200})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['seed_offset_2'],200)
        self.assertEqual(app['assumptions']['seed_offset_1'],7)

    def test_11_sync_accepted_forms_covers_civic_science(self):
        from pathlib import Path
        html=(Path(__file__).resolve().parent.parent/'openline_five_products.html').read_text()
        block=html.split('function syncAcceptedForms()',1)[1].split('function renderAll()',1)[0]
        for field in ('civic-population','civic-liters','civic-outage-hours',
                      'civic-capex-ceiling','civic-opex-ceiling','civic-flood-diesel',
                      'science-seed1','science-seed2','science-invalidate-batch02'):
            self.assertIn(field,block,field)
        for assumption in ('max_10yr_lifecycle_budget_musd','min_school_safety_setback_m',
                           'max_72h_blackout_outage_hours','max_property_line_noise_dba',
                           'max_low_income_bill_delta_usd_mo','drought_raw_water_turbidity_ntu',
                           'seed_offset_1','seed_offset_2','invalidate_batch_02'):
            self.assertIn(assumption,block,assumption)

    def test_12_early_stop_resume_stage_accept_without_reload(self):
        import json as _json, threading as _threading, urllib.request as _urlreq, urllib.error as _urlerr
        base=f"http://127.0.0.1:{self.port}"
        outs={}
        def fetch_state(name):
            req=_urlreq.Request(base+"/api/five_products/state",headers={"Host":f"127.0.0.1:{self.port}"})
            try:
                with _urlreq.urlopen(req,timeout=300) as res:
                    outs[name]=(res.status,_json.loads(res.read()))
            except _urlerr.HTTPError as exc:
                outs[name]=(exc.code,_json.loads(exc.read()))
        threads=[_threading.Thread(target=fetch_state,args=(f"state-{i}",)) for i in range(3)]
        for t in threads: t.start()
        import time as _time; _time.sleep(1)
        # STOP during first-use seeding, then Resume — the R7 D2 browser flow.
        self.assertEqual(self.request('/api/stop',method='POST',body={"reason":"user_paused_changes"})[0],200)
        self.assertEqual(self.request('/api/clear_stop',method='POST',body={"reason":"user_resumed_editing"})[0],200)
        for t in threads: t.join()
        # Closure fix: the in-flight state GETs are incidental concurrency noise,
        # not part of the product contract. Each may return 200 (init already done)
        # or a structured 400 fail-closed refusal, depending on the exact interleaving
        # with lazy init and the STOP window. Observed refusals across runs:
        # stopped_at_epoch, authority_unavailable_fail_closed, old_authority_dead,
        # stop_not_active — all guard fail-closed errors. What is contractual, and
        # stays strict below, is the post-Resume state (200, 5 products) and the
        # stage+accept flow. A 500, a hang, or a malformed body would still fail.
        for name,(code,body) in outs.items():
            if code==400:
                self.assertIsInstance(body,dict,(name,body))
                self.assertIsInstance(body.get("error"),str,(name,body))
            else:
                self.assertEqual(code,200,(name,body))
        code,raw=self.request('/api/five_products/state')
        self.assertEqual(code,200)
        self.assertEqual(len(_json.loads(raw).get("products",{})),5)
        code,raw=self.request('/api/five_products/stage',method='POST',
            body={"product_key":"energy","payload":{"inputs":{"households":43}}})
        self.assertEqual(code,200,(code,raw[:200]))
        prop=_json.loads(raw)["proposal"]
        eng=self.server.genie_engine
        pid=eng.FIVE_PRODUCT_SPECS['energy']['project_id']
        code,raw=self.request('/api/accept',method='POST',
            body={"project_id":pid,"proposal_id":prop["proposal_id"]})
        self.assertEqual(code,200,(code,raw[:200]))
        app=eng.get_project_bundle(pid)['accepted']['state']['civilization_app']
        self.assertEqual(app['assumptions']['household_units'],43)

    def test_14_api_household_domain_matches_browser_and_cannot_be_accepted(self):
        eng=self.server.genie_engine
        eng.ensure_five_products_initialized()
        pid=eng.FIVE_PRODUCT_SPECS['energy']['project_id']
        before=eng.get_project_bundle(pid)['accepted']
        for value in (0, 5001, 99999, 1.5, True, "nan", "inf"):
            code, raw=self.request('/api/five_products/stage', method='POST',
                body={"product_key":"energy","payload":{"inputs":{"households":value}}})
            self.assertEqual(code,400,(value,code,raw[:200]))
            after=eng.get_project_bundle(pid)['accepted']
            self.assertEqual(after['state_sha256'],before['state_sha256'])
        code,raw=self.request('/api/five_products/stage',method='POST',
            body={"product_key":"energy","payload":{"inputs":{"households":5000}}})
        self.assertEqual(code,200,(code,raw[:200]))

    def test_13_identical_source_event_reapply_is_noop_and_replay_still_rejected(self):
        import os as _os, tempfile as _tf
        from pathlib import Path as _Path
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as _Ed
        from core.recall import RecallLedger as _Ledger, Rejected as _Rejected, public_hex as _pub, signed_event as _ev
        import hashlib as _hl, json as _js
        def _sha(v): return _hl.sha256(_js.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        tmp=_Path(_tf.mkdtemp(prefix="genie-recall-idempotent-"))
        led=_Ledger(tmp/"recall.sqlite", _os.urandom(32))
        owner=_Ed.generate(); other=_Ed.generate()
        led.pin_source("test-source", _pub(owner))
        dig=_sha({"project_id":"p","station":"workflow","version":1})
        event=_ev(owner, source="test-source", revision=1, digest=dig, state="VALID", expires_at=2_000_000_000)
        led.apply_event(event, now=200)
        # Byte-identical re-application is a no-op, not a replay rejection.
        led.apply_event(event, now=200)
        led.apply_event(dict(event), now=200)
        # Same revision, different digest: still rejected.
        with self.assertRaises(_Rejected):
            led.apply_event(_ev(owner, source="test-source", revision=1, digest=_sha({"different":1}), state="VALID", expires_at=2_000_000_000), now=200)
        # Same revision and digest, different state: still rejected.
        with self.assertRaises(_Rejected):
            led.apply_event(_ev(owner, source="test-source", revision=1, digest=dig, state="REVOKED", expires_at=2_000_000_000), now=200)
        # Forged signature: still rejected.
        with self.assertRaises(_Rejected):
            led.apply_event(_ev(other, source="test-source", revision=1, digest=dig, state="VALID", expires_at=2_000_000_000), now=200)
        # Lower revision with different content: still rejected.
        led.apply_event(_ev(owner, source="test-source", revision=2, digest=_sha({"v":2}), state="VALID", expires_at=2_000_000_000), now=200)
        with self.assertRaises(_Rejected):
            led.apply_event(_ev(owner, source="test-source", revision=1, digest=_sha({"v":1}), state="VALID", expires_at=2_000_000_000), now=200)
        # Identical work re-registration (retry after an aborted create) is a
        # no-op; a different declaration for the same work_id still refused
        # (here: same support set, different completeness flag).
        group=[{"source":"test-source","revision":2,"digest":_sha({"v":2})}]
        led.register_work("test-work", support_sets=[group])
        led.register_work("test-work", support_sets=[group])
        with self.assertRaises(_Rejected):
            led.register_work("test-work", support_sets=[group], complete=False)

if __name__=='__main__': unittest.main()
