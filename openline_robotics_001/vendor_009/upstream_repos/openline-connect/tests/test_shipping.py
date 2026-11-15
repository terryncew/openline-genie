"""Local security shipping gate. No official MCP compatibility is asserted by fallback."""
import json, os, shutil, sqlite3, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from openline_connect.onboarding import initialize, read_engine, allow, verify_local
from openline_connect.engine import ProtectionError
from openline_connect.signing import sign, pub, digest, verify
from openline_connect.mcp_server import fallback_dispatch


class ShippingSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/'receiver'
        self.info=initialize(self.home)
        self.engine=read_engine(self.home)
        self.params={'target':'customer-one','value':'updated','amount_cents':100}
        buyer=(self.home/'keys/fictional-buyer.seed').read_text().strip()
        self.claims={'kind':'openline.connect.mandate.v1','subject':'fictional-buyer',
                     'seller':'fictional-supplier','action':'record.update',
                     'target':'customer-one','parameters_sha256':digest(self.params),
                     'max_amount_cents':100,'nbf':int(time.time())-1,'exp':int(time.time())+200,
                     'jti':'denied-before-grant'}
        self.auth=sign(self.claims,buyer,'fictional-buyer')

    def test_missing_grants_fails_closed_unless_explicit_legacy_fixture(self):
        from openline_connect.engine import ConnectEngine
        with self.assertRaisesRegex(ValueError,'receiver_grants_required_default_deny'):
            ConnectEngine('sqlite:///'+str(self.home/'bad.sqlite'),
                          {'buyers':{}},seller_seed='11'*32)

    def test_init_has_no_grants_and_secure_keys(self):
        self.assertEqual(json.loads((self.home/'policy.json').read_text())['grants'],{})
        self.assertEqual((self.home/'keys/receiver.seed').stat().st_mode & 0o777,0o600)
        self.assertEqual((self.home/'keys/fictional-buyer.seed').stat().st_mode & 0o777,0o600)
        with self.assertRaises(ProtectionError):initialize(self.home)
        self.assertEqual(self.engine.public()['decision_seq'],0)

    def test_empty_allowlist_signs_refusal_without_effect(self):
        r=self.engine.execute(action='record.update',params=self.params,authorization=self.auth,nonce='before')
        self.assertEqual(r['state'],'REFUSED_PRE_EFFECT')
        self.assertEqual(r['reason'],'receiver_allowlist_denied')
        self.assertEqual(verify(r['receipt'],{'seller':self.info['seller_public']})['subject'],'fictional-buyer')
        self.assertTrue(verify_local(self.home,seller_public=self.info['seller_public'])['verified'])
        with self.engine.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],0)

    def test_allow_one_scope_then_revoke_restart(self):
        grant=allow(self.home, action='record.update',target='customer-one',value='updated',amount_cents=100,ttl_seconds=120)
        body=json.loads(Path(grant['fictional_agent_request']).read_text())
        restarted=read_engine(self.home)
        r=restarted.execute(**body)
        self.assertEqual(r['state'],'FULFILLED')
        self.assertEqual(restarted.execute(**body)['replayed'],True)
        self.assertEqual(restarted.public()['decision_seq'],1)
        with restarted.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],1)
        # Token revoked before different nonce next effect, across process restart.
        restarted.revoke(grant['grant_id'])
        restarted2=read_engine(self.home)
        new_body={**body,'nonce':'another-valid-nonce'}
        refused=restarted2.execute(**new_body)
        self.assertEqual(refused['reason'],'revoked_mandate')
        self.assertEqual(refused['state'],'REFUSED_PRE_EFFECT')
        self.assertTrue(verify_local(self.home,seller_public=self.info['seller_public'],expected_seq=2)['verified'])
        with restarted2.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],1)

    def test_receiver_grant_exact_target_and_amount(self):
        grant=allow(self.home,action='record.update',target='customer-one',value='updated',amount_cents=100,ttl_seconds=120)
        token=json.loads(Path(grant['fictional_agent_request']).read_text())['authorization']
        reloaded=read_engine(self.home)
        p={**self.params,'target':'customer-two'}
        r=reloaded.execute(action='record.update',params=p,authorization=token,nonce='wrong-target')
        self.assertEqual(r['decision'],'DENY')
        self.assertEqual(reloaded.public()['decision_seq'],1)

    def test_expiry_and_key_rotation_survive_restart(self):
        grant=allow(self.home,action='record.update',target='customer-one',value='updated',amount_cents=100,ttl_seconds=120)
        body=json.loads(Path(grant['fictional_agent_request']).read_text())
        active=read_engine(self.home)
        new_seed=__import__('secrets').token_hex(32)
        active.rotate(new_seed)
        # Local operator's secret-file update simulates safe custody migration; no network key discovery.
        f=self.home/'keys/receiver.seed';f.write_text(new_seed+'\n');os.chmod(f,0o600)
        after=read_engine(self.home)
        self.assertEqual(after.execute(**body)['state'],'FULFILLED')
        with self.assertRaises(ValueError):
            from openline_connect.verify import inspect
            inspect([after.execute(**body)],{'seller':self.info['seller_public']})
        # Old key remains externally pinnable for earlier records; new key signs after rotation.
        new_pub=pub(new_seed)
        self.assertTrue(verify_local(self.home,seller_public=new_pub)['verified'])

    def test_grant_policy_tamper_denied_even_if_file_edited(self):
        grant=allow(self.home,action='record.update',target='customer-one',value='updated',amount_cents=100,ttl_seconds=120)
        pol=json.loads((self.home/'policy.json').read_text())
        pol['grants']['record.update'][0]['max_amount_cents']=5000
        (self.home/'policy.json').write_text(json.dumps(pol))
        body=json.loads(Path(grant['fictional_agent_request']).read_text())
        r=read_engine(self.home).execute(**body)
        self.assertEqual(r['reason'],'receiver_allowlist_denied')

    def test_mock_unknown_does_not_fulfill_paid(self):
        # A paid handler is registered but no payment/authority grant ever provided.
        p={'target':'report-1','amount_cents':100}
        r=self.engine.execute(action='report.generate',params=p,
              authorization=self.auth,nonce='paid-1',payment={'unknown':True})
        self.assertEqual(r['state'],'REFUSED_PRE_EFFECT')
        with self.engine.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],0)

    def test_stdio_fallback_is_no_socket_and_no_raw_entrypoint(self):
        with patch('socket.socket.bind',side_effect=AssertionError('TCP bind forbidden')):
            r=fallback_dispatch(self.engine,{'jsonrpc':'2.0','id':1,'method':'tools/list'})
            names={t['name'] for t in r['result']['tools']}
            self.assertEqual(len(names),6)
            self.assertNotIn('raw_execute',names)
            denied=fallback_dispatch(self.engine,{'jsonrpc':'2.0','id':2,'method':'tools/call',
              'params':{'name':'openline_execute_protected_action','arguments':
                {'action':'record.update','params':self.params,'authorization':self.auth,'nonce':'mcp-1'}}})
            self.assertEqual(json.loads(denied['result']['content'][0]['text'])['state'],'REFUSED_PRE_EFFECT')

    def test_replayed_refusal_keeps_single_decision(self):
        a=self.engine.execute(action='record.update',params=self.params,authorization=self.auth,nonce='X')
        b=self.engine.execute(action='record.update',params=self.params,authorization=self.auth,nonce='X')
        self.assertTrue(b['replayed']);self.assertEqual(self.engine.public()['decision_seq'],1)

    def test_no_grant_cannot_be_silent_allow(self):
        # Registered callbacks aren't exported as public tools.
        self.assertTrue(self.engine._handlers['record.update'])
        r=self.engine.execute(action='record.update',params=self.params,authorization=self.auth,nonce='Z')
        self.assertEqual(r['state'],'REFUSED_PRE_EFFECT')

if __name__=='__main__':unittest.main()
