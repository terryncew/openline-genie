import json,tempfile,unittest
from pathlib import Path
from openline_connect.engine import ConnectEngine,ProtectionError
from openline_connect.onboarding import initialize, read_engine, allow
from openline_connect.signing import sign,digest

class PublicExport(unittest.TestCase):
 def test_no_legacy_grant_free_acceptance(self):
  with tempfile.TemporaryDirectory() as d:
   for p in ({'buyers':{}}, {'buyers':{},'compatibility_legacy_trusted_buyers_without_grants':True}):
    with self.assertRaisesRegex(ValueError,'receiver_grants_required_default_deny'):
     ConnectEngine('sqlite:///'+str(Path(d)/'db.sqlite'),p,seller_seed=__import__('secrets').token_hex(32))
 def test_init_default_deny_and_allow_and_replay(self):
  with tempfile.TemporaryDirectory() as d:
   info=initialize(Path(d)/'home');self.assertEqual(info['authorized_operations'],0)
   obj=read_engine(Path(d)/'home');p={'target':'customer-1','value':'new','amount_cents':10}
   buyer=(Path(d)/'home/keys/fictional-buyer.seed').read_text().strip()
   from time import time
   t=int(time())
   token=sign({'kind':'openline.connect.mandate.v1','subject':'fictional-buyer','seller':'fictional-supplier','action':'record.update','target':'customer-1','parameters_sha256':digest(p),'max_amount_cents':10,'nbf':t-1,'exp':t+200,'jti':'abc'},buyer,'fictional-buyer')
   denied=obj.execute(action='record.update',params=p,authorization=token,nonce='no-grant')
   self.assertEqual(denied['state'],'REFUSED_PRE_EFFECT')
   grant=allow(Path(d)/'home',action='record.update',target='customer-1',value='new',amount_cents=10,ttl_seconds=120)
   req=json.loads(Path(grant['fictional_agent_request']).read_text());e=read_engine(Path(d)/'home')
   allowed=e.execute(**req);self.assertEqual(allowed['state'],'FULFILLED')
   self.assertTrue(e.execute(**req)['replayed'])
   with e.db() as db:self.assertEqual(db.execute('select count(*) from records').fetchone()[0],1)
