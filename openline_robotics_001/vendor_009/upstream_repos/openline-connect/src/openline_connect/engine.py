"""Receiver-owned guarded local transaction ledger, adapted from Accept PR95/96.

SQLite is the ONLY atomic effect boundary. External side effects require a separate,
carefully reviewed outbox/reconciliation integration, and are not claimed atomic here.
"""
from __future__ import annotations
import json,sqlite3,time,hashlib,functools,inspect
from pathlib import Path
from contextlib import closing
from .signing import sign,verify,digest,pub,canon

class ProtectionError(Exception):
    def __init__(self,code,status=403):self.code=code;self.status=status;super().__init__(code)

def _parse_db(d):
    if not isinstance(d,str) or not d.startswith('sqlite:///'):raise ValueError('sqlite:/// absolute or relative path required')
    return d[len('sqlite:///'):]

class ConnectEngine:
    """Local-only trusted receiver. The operator supplies its own private key.

    registered callbacks may only claim atomic local effects if *all* writes use the
    provided db connection. This cannot guard privileged direct DB/file access.
    """
    def __init__(self, database:str, policy:str|dict, *, seller_seed:str, seller_id='fictional-supplier', now=None):
        self.path=_parse_db(database);self.seed=seller_seed;self.seller_id=seller_id;self.clock=now or (lambda:int(time.time()))
        self.policy=json.loads(Path(policy).read_text()) if isinstance(policy,str) else policy
        self._handlers={}
        if not isinstance(self.policy,dict) or 'buyers' not in self.policy:raise ValueError('missing_receiver_policy')
        if not isinstance(self.policy.get('grants'), dict):
            raise ValueError('receiver_grants_required_default_deny')

        if len(bytes.fromhex(seller_seed))!=32:raise ValueError('bad_seed')
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with closing(self.db()) as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS operations(scope TEXT NOT NULL,nonce TEXT NOT NULL,request_sha TEXT NOT NULL,state TEXT NOT NULL,decision TEXT, outcome TEXT,body TEXT,settlement TEXT,created INTEGER,updated INTEGER,PRIMARY KEY(scope,nonce));
            CREATE TABLE IF NOT EXISTS decisions(seq INTEGER PRIMARY KEY AUTOINCREMENT,token TEXT NOT NULL,prev TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revocations(token_id TEXT PRIMARY KEY,at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS records(record_id TEXT PRIMARY KEY,content TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS key_epochs(seq INTEGER PRIMARY KEY,public TEXT NOT NULL,previous_key_hash TEXT,rotation TEXT);
            ''')
            db.execute('INSERT OR IGNORE INTO key_epochs(seq,public,previous_key_hash,rotation) VALUES(1,?,NULL,NULL)',(pub(seller_seed),))
            key=db.execute('SELECT public FROM key_epochs ORDER BY seq DESC LIMIT 1').fetchone()[0]
            if key!=pub(seller_seed):raise ValueError('active_seller_key_does_not_match_database')
    def db(self):
        c=sqlite3.connect(self.path,timeout=10,isolation_level=None,check_same_thread=False)
        c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL');c.execute('PRAGMA busy_timeout=10000')
        return c
    def protect(self,*,action,max_amount_cents=5000):
        def decorator(fn):
            @functools.wraps(fn)
            def run(*args,**kwargs):
                authorization=kwargs.pop('_authorization',None)
                nonce=kwargs.pop('_nonce',None)
                params=dict(zip(fn.__code__.co_varnames[:fn.__code__.co_argcount],args));params.update(kwargs)
                params.setdefault('target',str(params.get('order_id','local-only')))
                return self.execute(action=action,params=params,authorization=authorization,nonce=nonce)['body']
            allowed=set(inspect.signature(fn).parameters)
            # Pure computation only: its response is atomically committed to the SQLite
            # operation ledger. Do NOT perform external DB/API writes inside this fn.
            self.register(action,lambda params,db:fn(**{k:v for k,v in params.items() if k in allowed}),max_amount_cents=max_amount_cents,atomic=True)
            return run
        return decorator
    def register(self,action,handler,*,max_amount_cents=5000,atomic=True,payment_required=False):
        if not isinstance(action,str) or not action or action in self._handlers:raise ValueError('duplicate_or_bad_action')
        self._handlers[action]=(handler,max_amount_cents,atomic,payment_required)
    def public(self):
        with closing(self.db()) as db:
            rows=db.execute('SELECT seq,public,previous_key_hash,rotation FROM key_epochs ORDER BY seq').fetchall()
            head=self._head(db)
        return {'schema':'openline.connect.discovery.v1','seller':self.seller_id,'current_key':pub(self.seed),'key_epochs':[dict(zip(('sequence','public','previous_key_hash','rotation'),r)) for r in rows],**head,'discovered_key_is_not_independent_trust':True}
    def _head(self,db):
        row=db.execute('SELECT seq,token FROM decisions ORDER BY seq DESC LIMIT 1').fetchone()
        return {'decision_seq':row[0] if row else 0,'head_decision_hash':hashlib.sha256(row[1].encode()).hexdigest() if row else '0'*64}
    def _sign_outcome(self,db,claim,body,status):
        claim={**claim,'kind':'openline.connect.decision.v1','seller':self.seller_id}
        prev=self._head(db);claim['decision_seq']=prev['decision_seq']+1;claim['prev_decision_hash']=prev['head_decision_hash']
        token=sign(claim,self.seed,'seller')
        db.execute('INSERT INTO decisions(seq,token,prev) VALUES(?,?,?)',(claim['decision_seq'],token,prev['head_decision_hash']))
        outcome={'kind':'openline.connect.outcome.v1','seller':self.seller_id,'decision_sha256':hashlib.sha256(token.encode()).hexdigest(),
                 'request_sha256':claim['request_sha256'],'status':status,'body_sha256':digest(body) if body is not None else None,
                 'settlement_status':claim.get('settlement_status'),'settlement_tx':claim.get('settlement_tx'), 'at':claim['at'],
                 'claim_limit':'seller_attests_local_sqlite_effect_not_external_delivery'}
        signed=sign(outcome,self.seed,'seller')
        return {'decision':claim['decision'],'reason':claim['reason'],'body':body,'receipt':token,'outcome':signed,
                'decision_seq':claim['decision_seq'],'head_decision_hash':hashlib.sha256(token.encode()).hexdigest(),
                'seller_attestation_only':True,'state':status}
    def _authority(self,db,action,params,authorization,now):
        if not authorization:raise ProtectionError('authorization_required')
        claims=None
        for subject,key in self.policy['buyers'].items():
            try: c=verify(authorization,{subject:key},kind='openline.connect.mandate.v1')
            except ValueError:continue
            if c.get('subject')==subject:claims=c;break
        if not claims:raise ProtectionError('untrusted_buyer_proof')
        if claims.get('seller')!=self.seller_id or claims.get('action')!=action or claims.get('target')!=params.get('target') or claims.get('parameters_sha256')!=digest(params):raise ProtectionError('mandate_binding_mismatch')
        if type(claims.get('nbf')) is not int or type(claims.get('exp')) is not int or now<claims['nbf'] or now>=claims['exp']:raise ProtectionError('authorization_expired')
        if db.execute('SELECT 1 FROM revocations WHERE token_id=?',(claims.get('jti'),)).fetchone():raise ProtectionError('revoked_mandate')
        # Public distribution: a receiver-signed active grant is mandatory for every effect.
        permitted = False
        for grant in self.policy['grants'].get(action, []):
            try:
                signed = verify(grant['receiver_signature'],
                                {'seller':[r[0] for r in db.execute('SELECT public FROM key_epochs ORDER BY seq')]},
                                kind='openline.connect.receiver_grant.v1')
            except (KeyError, ValueError, TypeError):
                continue
            if any(signed.get(k) != v for k,v in grant.items() if k != 'receiver_signature'):
                continue
            if (grant.get('active') is True and grant.get('subject') == claims['subject']
                and grant.get('target') == params.get('target') and grant.get('expires_at',0) > now
                and type(grant.get('max_amount_cents')) is int
                and params.get('amount_cents',0) <= grant['max_amount_cents']):
                permitted = True
                break
        if not permitted:
            raise ProtectionError('receiver_allowlist_denied')
        limit=self._handlers[action][1]
        amount=params.get('amount_cents',0)
        if type(amount) is not int or amount<0 or amount>limit or amount>claims.get('max_amount_cents',0):raise ProtectionError('amount_exceeds_authority')
        return claims
    def dry_run(self,action,params,authorization):
        if action not in self._handlers:return {'allowed':False,'reason':'unknown_operation'}
        with closing(self.db()) as db:
            try:
                c=self._authority(db,action,params,authorization,self.clock())
                return {'allowed':True,'subject':c['subject'],'target':c['target']}
            except ProtectionError as e:return {'allowed':False,'reason':e.code}
    def _payment(self,action,params,payment,now):
        if payment is None:return {'state':'NOT_APPLICABLE','tx':None}
        if not isinstance(payment,dict):raise ProtectionError('invalid_payment_context')
        if payment.get('unknown') is True:return {'state':'UNKNOWN','tx':None}
        fac=self.policy.get('facilitator_public')
        if not fac:raise ProtectionError('no_pinned_facilitator')
        try: c=verify(payment.get('assertion'),{'facilitator':fac},kind='openline.connect.mock_settlement.v1')
        except (ValueError,KeyError,TypeError):raise ProtectionError('untrusted_settlement_assertion')
        amt=c.get('amount')
        if not isinstance(amt,str) or not amt.isdecimal() or len(amt)>78 or int(amt)<0:raise ProtectionError('invalid_atomic_amount')
        if (c.get('seller')!=self.seller_id or c.get('action')!=action or c.get('target')!=params.get('target') or
            c.get('request_sha256')!=digest(params) or c.get('status')!='SETTLED' or not c.get('tx')):raise ProtectionError('settlement_scope_mismatch')
        if type(c.get('nbf')) is not int or type(c.get('exp')) is not int or not c['nbf']<=now<c['exp']:raise ProtectionError('stale_settlement_assertion')
        return {'state':'ATTESTED_SETTLED','tx':c['tx'],'assertion':payment['assertion']}
    def execute(self,*,action,params,authorization,nonce,payment=None,fault=None):
        now=self.clock()
        if action not in self._handlers:raise ProtectionError('unsupported_operation',404)
        if self._handlers[action][3] and payment is None:raise ProtectionError('paid_operation_requires_verified_settlement_evidence',402)
        if not isinstance(nonce,str) or not 1<=len(nonce)<=128:raise ProtectionError('invalid_nonce',400)
        if not isinstance(params,dict) or 'target' not in params:raise ProtectionError('target_required',400)
        req_sha=digest({'action':action,'params':params,'authorization':authorization,'payment':payment})
        scope=self.seller_id+':'+action
        with closing(self.db()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row=db.execute('SELECT request_sha,state,body,decision,outcome FROM operations WHERE scope=? AND nonce=?',(scope,nonce)).fetchone()
                if row:
                    if row[0]!=req_sha:raise ProtectionError('idempotency_payload_mismatch',409)
                    if row[1] in ('FULFILLED','REFUSED_PRE_EFFECT','COMPENSATED'):
                        db.commit();return {**json.loads(row[2]),'replayed':True}
                    if row[1] in ('SETTLEMENT_UNKNOWN','SETTLED_UNFULFILLED_REFUND_DUE'):
                        db.commit();return {'state':row[1],'replayed':True,'reconciliation_required':True,'signed_record':row[3]}
                    if row[1]=='RESERVED':db.commit();return {'state':'IN_FLIGHT_PENDING','replayed':True}
                    if row[1]!='SETTLED_PENDING':raise ProtectionError('unexpected_durable_state',409)
                    previous_settled=True
                else:
                    previous_settled=False
                    db.execute('INSERT INTO operations(scope,nonce,request_sha,state,created,updated) VALUES(?,?,?,?,?,?)',(scope,nonce,req_sha,'RESERVED',now,now))
                try:c=self._authority(db,action,params,authorization,now)
                except ProtectionError as e:
                    # Must not rewrite recorded settlement if effect-time authority expired.
                    subject=None
                    if authorization:
                        for k,v in self.policy['buyers'].items():
                            try: body=verify(authorization,{k:v},kind='openline.connect.mandate.v1');subject=body.get('subject');break
                            except ValueError:pass
                    owed=previous_settled
                    state='SETTLED_UNFULFILLED_REFUND_DUE' if owed else 'REFUSED_PRE_EFFECT'
                    claim={'decision':'INDETERMINATE' if owed else 'DENY','reason':e.code,'subject':subject,'authenticated_subject':subject is not None,
                           'action':action,'target':params['target'],'request_sha256':req_sha,'parameters_sha256':digest(params),
                           'settlement_status':'ATTESTED_SETTLED' if owed else 'NOT_APPLICABLE','at':now}
                    r=self._sign_outcome(db,claim,None,state)
                    db.execute('UPDATE operations SET state=?,decision=?,outcome=?,body=?,updated=? WHERE scope=? AND nonce=?',(state,r['receipt'],r['outcome'],json.dumps(r),now,scope,nonce))
                    db.commit();return r
                payment_state=self._payment(action,params,payment,now)
                if payment_state['state']=='UNKNOWN':
                    claim={'decision':'INDETERMINATE','reason':'external_settlement_unobserved','subject':c['subject'],'authenticated_subject':True,'action':action,'target':params['target'],'request_sha256':req_sha,'parameters_sha256':digest(params),'settlement_status':'UNKNOWN','at':now}
                    r=self._sign_outcome(db,claim,None,'SETTLEMENT_UNKNOWN')
                    db.execute('UPDATE operations SET state=?,decision=?,outcome=?,body=?,updated=? WHERE scope=? AND nonce=?',('SETTLEMENT_UNKNOWN',r['receipt'],r['outcome'],json.dumps(r),now,scope,nonce))
                    db.commit();return r
                if payment is not None and not previous_settled:
                    db.execute('UPDATE operations SET state=?,settlement=?,updated=? WHERE scope=? AND nonce=?',('SETTLED_PENDING',payment_state.get('assertion'),now,scope,nonce))
                    db.commit()
                    if fault=='after_settlement':raise RuntimeError('SIMULATED_CRASH_AFTER_SETTLEMENT')
                    db.execute('BEGIN IMMEDIATE')
                    row=db.execute('SELECT state,request_sha FROM operations WHERE scope=? AND nonce=?',(scope,nonce)).fetchone()
                    if row!=('SETTLED_PENDING',req_sha):raise ProtectionError('operation_changed_during_settlement',409)
                if fault=='before_effect':raise RuntimeError('SIMULATED_CRASH_BEFORE_EFFECT')
                # Re-check right before the DB effect and signed record commit.
                effective=self.clock()
                try:self._authority(db,action,params,authorization,effective)
                except ProtectionError as exc:
                    state='SETTLED_UNFULFILLED_REFUND_DUE' if payment is not None else 'REFUSED_PRE_EFFECT'
                    claim={'decision':'INDETERMINATE' if payment is not None else 'DENY','reason':exc.code,
                           'subject':c['subject'],'authenticated_subject':True,'action':action,'target':params['target'],
                           'request_sha256':req_sha,'parameters_sha256':digest(params),
                           'settlement_status':payment_state['state'],'settlement_tx':payment_state.get('tx'),'at':effective}
                    r=self._sign_outcome(db,claim,None,state)
                    db.execute('UPDATE operations SET state=?,decision=?,outcome=?,body=?,updated=? WHERE scope=? AND nonce=?',(state,r['receipt'],r['outcome'],json.dumps(r),effective,scope,nonce))
                    db.commit();return r
                handler,limit,atomic,requires_payment=self._handlers[action]
                if not atomic:raise ProtectionError('unproven_external_effect_atomicity',503)
                db.execute('SAVEPOINT effect')
                try:
                    body=handler(params,db)
                    if fault=='effect_raises':raise RuntimeError('FICTIONAL_EFFECT_FAILURE')
                    db.execute('RELEASE effect')
                except Exception:
                    db.execute('ROLLBACK TO effect');db.execute('RELEASE effect')
                    claim={'decision':'INDETERMINATE','reason':'local_effect_failed','subject':c['subject'],'authenticated_subject':True,'action':action,'target':params['target'],
                           'request_sha256':req_sha,'parameters_sha256':digest(params),'settlement_status':payment_state['state'],'settlement_tx':payment_state.get('tx'),'at':effective}
                    state='SETTLED_UNFULFILLED_REFUND_DUE' if payment is not None else 'REFUSED_PRE_EFFECT'
                    r=self._sign_outcome(db,claim,None,state)
                    db.execute('UPDATE operations SET state=?,decision=?,outcome=?,body=?,updated=? WHERE scope=? AND nonce=?',(state,r['receipt'],r['outcome'],json.dumps(r),effective,scope,nonce))
                    db.commit();return r
                claim={'decision':'ALLOW','reason':'local_effect_committed','subject':c['subject'],'authenticated_subject':True,'action':action,'target':params['target'],
                       'request_sha256':req_sha,'parameters_sha256':digest(params),'settlement_status':payment_state['state'],'settlement_tx':payment_state.get('tx'),'at':effective}
                r=self._sign_outcome(db,claim,body,'FULFILLED')
                if payment is not None:
                    from .x402_wire import attach_offer_receipt
                    r['payment_response']=attach_offer_receipt({'x402Version':2,'transaction':payment_state.get('tx'),
                         'success':True,'scope':'mock_settlement_not_verified_by_x402_sdk'},r['outcome'])
                db.execute('UPDATE operations SET state=?,decision=?,outcome=?,body=?,updated=? WHERE scope=? AND nonce=?',('FULFILLED',r['receipt'],r['outcome'],json.dumps(r),effective,scope,nonce))
                db.commit();return r
            except BaseException:
                if db.in_transaction:db.rollback()
                raise
    def recover(self,scope,nonce):
        with closing(self.db()) as db:
            row=db.execute('SELECT state,request_sha,body FROM operations WHERE scope=? AND nonce=?',(scope,nonce)).fetchone()
            if not row:raise ProtectionError('unknown_operation',404)
            return {'state':row[0],'reconciliation_required':row[0] in ('SETTLEMENT_UNKNOWN','SETTLED_UNFULFILLED_REFUND_DUE','SETTLED_PENDING'),
                    'instruction':'do_not_retry_external_settlement_automatically','operation_scope':scope,'nonce':nonce}
    def record_mock_compensation(self,scope,nonce,compensation_assertion):
        """Operator-only local record of separately signed SIMULATED refund confirmation.

        This never initiates compensation; it also cannot prove real money refunded.
        """
        fac=self.policy.get('facilitator_public')
        if not fac:raise ProtectionError('no_pinned_facilitator')
        try:c=verify(compensation_assertion,{'facilitator':fac},kind='openline.connect.mock_compensation.v1')
        except ValueError:raise ProtectionError('invalid_compensation_attestation')
        with closing(self.db()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row=db.execute('SELECT state,request_sha,settlement FROM operations WHERE scope=? AND nonce=?',(scope,nonce)).fetchone()
                if not row or row[0]!='SETTLED_UNFULFILLED_REFUND_DUE':raise ProtectionError('not_compensable',409)
                original=verify(row[2],{'facilitator':fac},kind='openline.connect.mock_settlement.v1')
                if (c.get('scope')!=scope or c.get('nonce')!=nonce or c.get('original_tx')!=original['tx'] or
                    not isinstance(c.get('refund_tx'),str) or not c['refund_tx'] or c.get('status')!='MOCK_REFUNDED'):
                    raise ProtectionError('compensation_scope_or_evidence_mismatch')
                claim={'decision':'COMPENSATED','reason':'facilitator_mock_refund_attested','subject':None,'authenticated_subject':False,
                    'action':scope.split(':',1)[-1],'target':None,'request_sha256':row[1],
                    'parameters_sha256':None,'settlement_status':'MOCK_COMPENSATED_NOT_REAL','settlement_tx':original['tx'],'at':self.clock()}
                result=self._sign_outcome(db,claim,{'refund_tx':c['refund_tx']},'COMPENSATED')
                db.execute('UPDATE operations SET state=?,decision=?,outcome=?,body=?,updated=? WHERE scope=? AND nonce=?',
                          ('COMPENSATED',result['receipt'],result['outcome'],json.dumps(result),self.clock(),scope,nonce))
                db.commit();return result
            except BaseException:
                if db.in_transaction:db.rollback()
                raise
    def revoke(self,jti):
        with closing(self.db()) as db:
            db.execute('BEGIN IMMEDIATE');db.execute('INSERT OR IGNORE INTO revocations VALUES(?,?)',(jti,self.clock()));db.commit()
    def list_unresolved(self):
        with closing(self.db()) as db:
            return [dict(zip(('scope','nonce','state'),row)) for row in db.execute("SELECT scope,nonce,state FROM operations WHERE state IN ('SETTLED_PENDING','SETTLEMENT_UNKNOWN','SETTLED_UNFULFILLED_REFUND_DUE') ORDER BY created")]
    def inspect(self):return {'actions':sorted(self._handlers),'seller':self.seller_id,'policy_max':{a:v[1] for a,v in self._handlers.items()},'paid_actions':[a for a,v in self._handlers.items() if v[3]],**self.public()}
    def export(self):
        with closing(self.db()) as db:return [{'seq':a,'token':b} for a,b in db.execute('SELECT seq,token FROM decisions ORDER BY seq')]
    def rotate(self,new_seed):
        # Roots are pre-pinned externally; this is a signed migration record, NOT independent trust.
        with closing(self.db()) as db:
            db.execute('BEGIN IMMEDIATE')
            last=db.execute('SELECT seq,public FROM key_epochs ORDER BY seq DESC LIMIT 1').fetchone()
            if last[1]!=pub(self.seed):raise ProtectionError('stale_seller_key')
            sequence=last[0]+1
            previous_hash=hashlib.sha256(bytes.fromhex(last[1])).hexdigest()
            record={'kind':'openline.connect.key_succession.v1','sequence':sequence,'previous_key_hash':previous_hash,'new_public':pub(new_seed),'seller':self.seller_id}
            token=sign(record,self.seed,'seller')
            db.execute('INSERT INTO key_epochs VALUES(?,?,?,?)',(sequence,pub(new_seed),previous_hash,token));db.commit()
            self.seed=new_seed
            return token
