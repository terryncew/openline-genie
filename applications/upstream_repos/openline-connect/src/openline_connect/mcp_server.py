"""Six tools, same ConnectEngine. Official MCP SDK used when installed.

The JSON-RPC fallback is a limited local **test transport**, NOT certified MCP.
"""
import json,sys
from .engine import ProtectionError
from .verify import inspect

DEFS={
'openline_inspect_system':('Read local receiver policy and head',{},True,False,True),
'openline_check_authorization':('Dry-run authorization without executing',{'action':'string','params':'object','authorization':'string'},True,False,True),
'openline_verify_receipt':('Check signature with independently pinned key',{'entries':'array','seller_public':'string'},True,False,True),
'openline_list_unresolved':('List unresolved settlement/local execution',{},True,False,True),
'openline_execute_protected_action':('Execute fictional locally guarded action',{'action':'string','params':'object','authorization':'string','nonce':'string'},False,True,True),
'openline_recover_operation':('Read reconciliation status; NEVER re-settle payment automatically',{'scope':'string','nonce':'string'},False,True,True)
}

def invoke(engine,name,args):
    if name not in DEFS:raise ProtectionError('unknown_tool',404)
    if name=='openline_inspect_system':return engine.inspect()
    if name=='openline_check_authorization':return engine.dry_run(args['action'],args['params'],args['authorization'])
    if name=='openline_verify_receipt':return inspect(args['entries'],{'seller':args['seller_public']},expected_head=args.get('expected_head'),expected_seq=args.get('expected_seq'))
    if name=='openline_list_unresolved':return {'unresolved':engine.list_unresolved()}
    if name=='openline_execute_protected_action':return engine.execute(action=args['action'],params=args['params'],authorization=args['authorization'],nonce=args['nonce'],payment=args.get('payment'))
    if name=='openline_recover_operation':return engine.recover(args['scope'],args['nonce'])

def definitions():
    result=[]
    for name,(description,fields,read_only,destructive,idempotent) in DEFS.items():
        props={k:({'type':v}) for k,v in fields.items()}
        # optional payment and read-only expected checks
        if name=='openline_execute_protected_action':props['payment']={'type':'object'}
        if name=='openline_verify_receipt':props['expected_head']={'type':'string'};props['expected_seq']={'type':'integer'}
        result.append({'name':name,'description':description,'inputSchema':{'type':'object','properties':props,'required':list(fields),'additionalProperties':False},
                       'annotations':{'readOnlyHint':read_only,'destructiveHint':destructive,'idempotentHint':idempotent,'openWorldHint':False}})
    return result

def create_official_server(engine):
    from mcp.server import MCPServer
    from mcp.types import ToolAnnotations
    m=MCPServer('OpenLine Connect')
    for name,(_,fields,read_only,destructive,idempotent) in DEFS.items():
        # Explicitly advertised tool names and annotations. All tools funnel through invoke().
        # SDK derives typed JSON schema from the signatures; optional fields are JSON strings.
        if name=='openline_inspect_system':
            def fn()->dict:return invoke(engine,'openline_inspect_system',{})
        elif name=='openline_list_unresolved':
            def fn()->dict:return invoke(engine,'openline_list_unresolved',{})
        elif name=='openline_check_authorization':
            def fn(action:str,params:dict,authorization:str)->dict:return invoke(engine,'openline_check_authorization',locals())
        elif name=='openline_verify_receipt':
            def fn(entries:list,seller_public:str)->dict:return invoke(engine,'openline_verify_receipt',locals())
        elif name=='openline_execute_protected_action':
            def fn(action:str,params:dict,authorization:str,nonce:str,payment:dict|None=None)->dict:
                return invoke(engine,'openline_execute_protected_action',locals())
        else:
            def fn(scope:str,nonce:str)->dict:return invoke(engine,'openline_recover_operation',locals())
        m.add_tool(fn,name=name,annotations=ToolAnnotations(read_only_hint=read_only,destructive_hint=destructive,idempotent_hint=idempotent,open_world_hint=False))
    return m

def fallback_dispatch(engine,request):
    method=request.get('method');rid=request.get('id')
    if method=='notifications/initialized':return None
    if method=='initialize':
        return {'jsonrpc':'2.0','id':rid,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'openline-connect-fallback','version':'0.1rc1'}}}
    if method=='tools/list':return {'jsonrpc':'2.0','id':rid,'result':{'tools':definitions()}}
    if method=='tools/call':
        try:
            a=request.get('params') or {};v=invoke(engine,a['name'],a.get('arguments') or {})
            return {'jsonrpc':'2.0','id':rid,'result':{'content':[{'type':'text','text':json.dumps(v,sort_keys=True)}], 'isError':False,'structuredContent':v}}
        except (ProtectionError,KeyError,ValueError,TypeError) as e:
            return {'jsonrpc':'2.0','id':rid,'result':{'content':[{'type':'text','text':str(e)}], 'isError':True}}
    return {'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'method_not_found'}}

def run_mcp(engine,*,fallback=False):
    if not fallback:
        try:
            m=create_official_server(engine);m.run(transport='stdio');return
        except ImportError as e:raise RuntimeError('official MCP SDK unavailable; install openline-connect[mcp], or use --fallback-stdio (test only)') from e
    for line in sys.stdin:
        try:
            request=json.loads(line);result=fallback_dispatch(engine,request)
            if result is not None:print(json.dumps(result,separators=(',',':')),flush=True)
        except Exception:
            print(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'invalid_json_rpc'}}),flush=True)
