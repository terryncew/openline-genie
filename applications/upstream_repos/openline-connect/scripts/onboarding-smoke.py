"""Local stdio fallback demo; no official MCP SDK, networking, or money."""
import json,subprocess,sys,tempfile,time
from pathlib import Path
from openline_connect.signing import sign,digest

def main():
 with tempfile.TemporaryDirectory(prefix='ol-onboarding-') as root:
  home=Path(root)/'receiver';cmd=[sys.executable,'-m','openline_connect.cli']
  def call(*args):
   r=subprocess.run([*cmd,*args],capture_output=True,text=True)
   if r.returncode:raise RuntimeError(r.stdout+' '+r.stderr)
   return json.loads(r.stdout)
  def serve(request):
   p=subprocess.Popen([*cmd,'serve','--home',str(home),'--fallback-stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   sequence=[{'jsonrpc':'2.0','method':'initialize','id':1},
    {'jsonrpc':'2.0','method':'notifications/initialized'},
    {'jsonrpc':'2.0','method':'tools/list','id':2},
    {'jsonrpc':'2.0','method':'tools/call','id':3,'params':{'name':'openline_execute_protected_action','arguments':request}}]
   stdout,stderr=p.communicate(''.join(json.dumps(x)+'\n' for x in sequence),timeout=10)
   if p.returncode:raise RuntimeError(stderr)
   replies=[json.loads(s) for s in stdout.splitlines()]
   assert len(replies[1]['result']['tools'])==6
   return replies[-1]['result']['structuredContent']
  info=call('init','--home',str(home))
  assert info['default_deny'] and info['authorized_operations']==0
  buyer=(home/'keys/fictional-buyer.seed').read_text().strip()
  params={'target':'customer-1','value':'approved','amount_cents':100};now=int(time.time())
  claim={'kind':'openline.connect.mandate.v1','subject':'fictional-buyer','seller':'fictional-supplier','action':'record.update','target':'customer-1','parameters_sha256':digest(params),'max_amount_cents':100,'nbf':now-1,'exp':now+200,'jti':'preallow'}
  before=serve({'action':'record.update','params':params,'authorization':sign(claim,buyer,'fictional-buyer'),'nonce':'preallow'})
  assert before['state']=='REFUSED_PRE_EFFECT' and before['reason']=='receiver_allowlist_denied'
  grant=call('allow','--home',str(home),'--action','record.update','--target','customer-1','--value','approved','--amount-cents','100','--ttl-seconds','300')
  request=json.loads(Path(grant['fictional_agent_request']).read_text())
  success=serve(request);retry=serve(request)
  assert success['state']=='FULFILLED' and retry['replayed']
  verified=call('verify','--home',str(home),'--seller-public',info['seller_public'],'--expected-seq','2')
  assert verified['verified']
  print(json.dumps({'default_deny':True,'pre_grant':before['state'],'after_grant':success['state'],'replayed':True,'verified_signed_events':2,'transport':'test_only_json_rpc_stdio','official_sdk':'NOT_EXECUTED','network_listener':False},sort_keys=True))
if __name__=='__main__':main()
