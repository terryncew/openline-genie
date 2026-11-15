"""Offline: signatures establish seller assertions, NOT external fulfillment facts."""
import hashlib
from .signing import verify,digest

def inspect(receipts,pinned_keys,*,expected_head=None,expected_seq=None,request=None,body=None,buyer_proof=None,pinned_buyers=None):
    if isinstance(receipts,dict):receipts=[receipts]
    if not isinstance(receipts,list) or not receipts:raise ValueError('missing_receipts')
    prev='0'*64;seq=0
    for entry in receipts:
        r=verify(entry['receipt'],pinned_keys,kind='openline.connect.decision.v1')
        o=verify(entry['outcome'],pinned_keys,kind='openline.connect.outcome.v1')
        if r['decision_seq']!=seq+1 or r['prev_decision_hash']!=prev:raise ValueError('history_chain_gap_or_reorder')
        if o['decision_sha256']!=hashlib.sha256(entry['receipt'].encode()).hexdigest():raise ValueError('unbound_outcome')
        if o['request_sha256']!=r['request_sha256']:raise ValueError('unbound_request')
        if buyer_proof is not None:
            if pinned_buyers is None:raise ValueError('buyer_trust_missing')
            from .signing import verify as verify_jws
            try:buyer_claim=verify_jws(buyer_proof,pinned_buyers,kind='openline.connect.mandate.v1')
            except ValueError:
                if r.get('authenticated_subject') is True:raise ValueError('false_authenticated_subject_claim')
            else:
                if r.get('authenticated_subject') is True and r.get('subject')!=buyer_claim.get('subject'):raise ValueError('signed_denial_subject_mismatch')
        if r.get('decision')=='DENY':
            if o['status'] not in ('REFUSED_PRE_EFFECT',):raise ValueError('false_denial_outcome')
            if r.get('authenticated_subject') is True and not r.get('subject'):raise ValueError('invalid_authenticated_subject')
        if r.get('decision')=='ALLOW' and o['status']!='FULFILLED':raise ValueError('contradictory_allow')
        seq=r['decision_seq'];prev=hashlib.sha256(entry['receipt'].encode()).hexdigest()
        if request is not None and digest(request)!=r['request_sha256']:raise ValueError('request_digest_mismatch')
        if body is not None and digest(body)!=o['body_sha256']:raise ValueError('body_digest_mismatch')
    if expected_head and expected_head!=prev:raise ValueError('history_head_mismatch')
    if expected_seq is not None and expected_seq!=seq:raise ValueError('history_suffix_or_gap')
    return {'verified':True,'decision_seq':seq,'head_decision_hash':prev,
            'what_is_proven':'pinned seller signed these ordered claims and optional provided bytes match the claimed digests',
            'what_is_not_proven':'external settlement finality, delivery, full log completeness without an independently saved head'}
