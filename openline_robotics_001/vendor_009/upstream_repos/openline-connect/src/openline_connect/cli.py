"""Local receiver CLI; no implicit grants or network listener."""
import argparse,importlib,json,tempfile,hashlib,sys,os
from pathlib import Path
from .engine import ConnectEngine
from .verify import inspect
from .onboarding import initialize, allow as allow_local, read_engine, verify_local
from .engine import ProtectionError


def main(argv=None):
    p=argparse.ArgumentParser(prog='openline-connect')
    sub=p.add_subparsers(dest='cmd',required=True)
    d=sub.add_parser('demo');d.add_argument('--output')
    v=sub.add_parser('verify');v.add_argument('packet',nargs='?');v.add_argument('--home',default='.openline');v.add_argument('--seller-public',required=True);v.add_argument('--expected-head');v.add_argument('--expected-seq',type=int)
    c=sub.add_parser('check');c.add_argument('app')
    m=sub.add_parser('mcp');m.add_argument('--fallback-stdio',action='store_true');m.add_argument('--home')
    init = sub.add_parser('init', help='Create receiver-owned keys and a default-deny local profile')
    init.add_argument('--home', default='.openline')
    grant = sub.add_parser('allow', help='Explicitly allow one bounded fictional operation')
    grant.add_argument('--home', default='.openline')
    grant.add_argument('--action', required=True, choices=['record.update'])
    grant.add_argument('--target', required=True)
    grant.add_argument('--value', required=True)
    grant.add_argument('--amount-cents', type=int, required=True)
    grant.add_argument('--ttl-seconds', type=int, default=300)
    grant.add_argument('--name')
    serve = sub.add_parser('serve', help='Local official MCP stdio server (no TCP listener)')
    serve.add_argument('--home', default='.openline')
    serve.add_argument('--fallback-stdio', action='store_true', help='TEST ONLY; not official MCP SDK')
    verify_home = sub.add_parser('verify-local', help='Read local ledger and independently validate signed claims')
    verify_home.add_argument('--home', default='.openline')
    verify_home.add_argument('--seller-public', required=True)
    verify_home.add_argument('--expected-head')
    verify_home.add_argument('--expected-seq', type=int)
    a=p.parse_args(argv)
    if a.cmd == 'init':
        print(json.dumps(initialize(a.home),sort_keys=True)); return
    if a.cmd == 'allow':
        print(json.dumps(allow_local(a.home, action=a.action, target=a.target, value=a.value,
            amount_cents=a.amount_cents, ttl_seconds=a.ttl_seconds, grant_name=a.name),sort_keys=True)); return
    if a.cmd == 'serve':
        from .mcp_server import run_mcp
        run_mcp(read_engine(a.home),fallback=a.fallback_stdio); return
    if a.cmd == 'verify-local':
        result=verify_local(a.home,seller_public=a.seller_public,
            expected_head=a.expected_head,expected_seq=a.expected_seq)
        print(json.dumps(result,sort_keys=True))
        if not result.get('verified'):raise SystemExit(1)
        return
    if a.cmd=='demo':
        home=Path(a.output or tempfile.mkdtemp(prefix='openline-connect-demo-'))
        setup=initialize(home)
        granted=allow_local(home, action='record.update', target='customer-123',value='approved',
                             amount_cents=100,ttl_seconds=300)
        request=json.loads(Path(granted['fictional_agent_request']).read_text())
        engine=read_engine(home)
        first=engine.execute(**request)
        replay=engine.execute(**request)
        verification=verify_local(home,seller_public=setup['seller_public'],expected_seq=1,
                                  expected_head=first['head_decision_hash'])
        print(json.dumps({'home':str(home),'state':first['state'],'replayed':replay['replayed'],
                          'verified':verification['verified'],'seller_public':setup['seller_public'],
                          'notice':'FICTIONAL SQLITE ONLY; NO REAL PAYMENT OR EXTERNAL EFFECT'},sort_keys=True))
        if not verification['verified']:raise SystemExit(1)
    elif a.cmd=='verify':
        if not a.packet:
            result=verify_local(a.home,seller_public=a.seller_public,expected_head=a.expected_head,expected_seq=a.expected_seq)
            print(json.dumps(result,sort_keys=True))
            if not result.get('verified'):raise SystemExit(1)
            return
        packet=json.loads(Path(a.packet).read_text());items=packet['results']
        # Outcomes may have seq 1 and 2; no trusted keys are ever sourced from the packet.
        result=inspect(items,{'seller':a.seller_public},expected_head=a.expected_head,expected_seq=a.expected_seq)
        print(json.dumps(result,sort_keys=True))
    elif a.cmd=='check':
        sys.path.insert(0,os.getcwd())
        module,symbol=a.app.split(':',1);obj=getattr(importlib.import_module(module),symbol)
        names={r.path for r in getattr(obj,'routes',[])}
        required={'/healthz','/.well-known/openline-connect.json','/v1/connect/execute'}
        missing=required-names
        forbidden={x for x in names if x in ('/v1/orders','/v1/fulfill','/v1/raw/execute')}
        print(json.dumps({'passed':not missing and not forbidden,'routes':sorted(names),'missing':sorted(missing),
             'suspect_routes':sorted(forbidden),'limit':'static_route_surface_only'},sort_keys=True))
        if missing or forbidden:raise SystemExit(1)
    elif a.cmd=='mcp':
        from .mcp_server import run_mcp
        run_mcp(read_engine(a.home or '.openline'),fallback=a.fallback_stdio)
if __name__=='__main__':main()
